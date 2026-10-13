"""Predeclared low-rank ridge/STRING/LightGBM ablation with fold-local priors."""
import argparse,json,subprocess,time,resource,sys
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import yaml
from src.transfer import ROOT,digest,load_deltas,metrics
from src.features import neighbor_features,standardize_fit,standardize
from src.data.string_prior import download,build_graph
from src.models.gbm import fit_components,predict_components


def response_basis(y,rank,seed):
    mean=y.mean(axis=0);centered=y-mean
    k=min(rank+8,*centered.shape)
    rng=np.random.default_rng(seed)
    q=np.linalg.qr(centered@rng.normal(size=(y.shape[1],k)),mode='reduced')[0]
    for _ in range(2):
        right=np.linalg.qr(centered.T@q,mode='reduced')[0]
        q=np.linalg.qr(centered@right,mode='reduced')[0]
    _,_,v=np.linalg.svd(q.T@centered,full_matrices=False)
    basis=v[:min(rank,len(v))]
    return mean,basis,centered@basis.T


def ridge_fit(x,z,alpha):
    xmean=x.mean(0);zmean=z.mean(0)
    coef=np.linalg.solve((x-xmean).T@(x-xmean)+alpha*np.eye(x.shape[1]),(x-xmean).T@(z-zmean))
    return coef,zmean-xmean@coef


def fold_predict(y,train_idx,query_idx,all_ids,w,basal,cfg):
    """No query outcomes accepted. Basis and priors see reference training y only."""
    mean,basis,z=response_basis(y,cfg['rank'],cfg['seed'])
    tr_ids=np.asarray(all_ids)[train_idx];qu_ids=np.asarray(all_ids)[query_idx]
    xt=neighbor_features(w[np.ix_(train_idx,train_idx)],tr_ids,tr_ids,z,basal[train_idx])
    xq=neighbor_features(w[np.ix_(query_idx,train_idx)],qu_ids,tr_ids,z,basal[query_idx])
    state=standardize_fit(xt);xt=standardize(xt,state);xq=standardize(xq,state)
    predictions={'training_mean':np.broadcast_to(mean,(len(query_idx),len(mean)))}
    saved=dict(mean=mean,basis=basis,**{'feature_'+k:v for k,v in state.items()})
    models={}
    for kind,cols in [('basal',slice(0,2)),('string',slice(None))]:
        for alpha in cfg['ridge_alphas']:
            name=f'ridge_{kind}_{alpha}';coef,intercept=ridge_fit(xt[:,cols],z,alpha)
            predictions[name]=mean+(xq[:,cols]@coef+intercept)@basis
            saved[name+'_coef']=coef;saved[name+'_intercept']=intercept
    for leaves in cfg['gbm_leaves']:
        name=f'gbm_string_{leaves}';model=fit_components(xt,z,leaves,cfg)
        predictions[name]=mean+predict_components(model,xq)@basis;models[name]=model
    saved['reference_ids']=tr_ids;saved['reference_scores']=z
    return predictions,saved,models


def run(config_path):
    start=time.monotonic();cfg=yaml.safe_load(Path(config_path).read_text())
    out=ROOT/cfg['results_dir'];out.mkdir(parents=True,exist_ok=True)
    art=ROOT/cfg['artifact_dir'];art.mkdir(parents=True,exist_ok=True)
    receipts=download(cfg,ROOT)
    source=ROOT/cfg['input_dir'];manifest=json.loads((ROOT/cfg['input_manifest']).read_text());used=[]
    for record in manifest['files']:
        if record['path'].startswith(cfg['input_dir']+'/') and record['path'].endswith('.parquet'):
            if digest(ROOT/record['path'])!=record['sha256']:raise ValueError('Input hash mismatch')
            used.append(record)
    if len(used)!=6:raise ValueError('Expected six verified input tables')
    controls={line:pd.read_parquet(source/f'{line}_control_baseline.parquet').set_index('output_gene_id') for line in ['K562','RPE1']}
    ids={line:sorted(i for i in set(pd.read_parquet(source/f'{line}_matched_strata.parquet').target_gene_id) if i.startswith('ENSG')) for line in controls}
    genes=sorted(set(controls['K562'].index)&set(controls['RPE1'].index))
    # Duplicate a gene's query row to allow distinct line-specific basal expression.
    all_ids=ids['K562']+ids['RPE1'];unique_ids=sorted(set(all_ids))
    graph,qc=build_graph(ROOT/cfg['raw_dir'],unique_ids,cfg['string_score_threshold'])
    ix=pd.Index(unique_ids).get_indexer(all_ids);w=graph[np.ix_(ix,ix)]
    np.savez_compressed(art/'graph.npz',weights=graph,target_ids=unique_ids)
    basal=np.concatenate([controls[line].mean_log1p_cp10k.reindex(ids[line]).to_numpy() for line in ['K562','RPE1']])
    train=load_deltas(source/'K562_pseudobulk.parquet',ids['K562'],genes)
    folds=np.array_split(np.random.default_rng(cfg['seed']).permutation(len(train)),cfg['folds'])
    losses={};fold_rows=[]
    for f,valid in enumerate(folds):
        tr=np.setdiff1d(np.arange(len(train)),valid)
        pred,_,_=fold_predict(train[tr],tr,valid,all_ids,w,basal,cfg)
        for name,p in pred.items():
            sse=float(np.square(p-train[valid]).sum());losses[name]=losses.get(name,0.)+sse
            fold_rows.append(dict(fold=f,model=name,mse=sse/train[valid].size))
        print(json.dumps({'fold_complete':f+1}),flush=True)
        del pred
    cv={name:value/train.size for name,value in losses.items()}
    def choose(prefix):return min((n for n in cv if n.startswith(prefix)),key=lambda n:(cv[n],n))
    selected={'training_mean':'training_mean','ridge_basal':choose('ridge_basal'),'ridge_string':choose('ridge_string'),'gbm_string':choose('gbm_string')}
    winner=min(selected,key=lambda name:(cv[selected[name]],name))
    frozen=dict(selected=selected,cv_mse=cv,fold_metrics=fold_rows,winner=winner,
                folds=[[ids['K562'][i] for i in f] for f in folds],graph_qc=qc,
                sources=receipts,config_sha256=digest(config_path),target_ids=ids,output_gene_ids=genes,
                note='K562-only selection; RPE1 outcomes not yet loaded; RPE1 was evaluated previously in experiment 002.')
    (out/'frozen_selection.json').write_text(json.dumps(frozen,indent=2)+'\n')
    # Fit only selected settings, not the whole grid, on all K562 targets.
    final_cfg={**cfg,'ridge_alphas':sorted(set(int(selected[k].rsplit('_',1)[1]) for k in ['ridge_basal','ridge_string'])),
               'gbm_leaves':[int(selected['gbm_string'].rsplit('_',1)[1])]}
    preds,state,models=fold_predict(train,np.arange(len(train)),np.arange(len(train),len(all_ids)),all_ids,w,basal,final_cfg)
    np.savez_compressed(art/'model_state.npz',**state,output_gene_ids=genes)
    for name,ensemble in models.items():
        for i,m in enumerate(ensemble):m.save_model(str(art/f'{name}_{i}.txt'))
    for name in selected:
        if name!='training_mean':np.savez_compressed(art/f'{name}_predictions.npz',predictions=preds[selected[name]],target_ids=ids['RPE1'],output_gene_ids=genes)
    # Freeze all predictions before the single held-out evaluation pass.
    held=load_deltas(source/'RPE1_pseudobulk.parquet',ids['RPE1'],genes)
    shared=np.isin(ids['RPE1'],ids['K562']);masks={'all_mapped':np.ones(len(held),bool),'shared_targets':shared,'unseen_targets':~shared}
    rows=[]
    for name in ['zero_delta']+list(selected):
        pred=np.zeros_like(held) if name=='zero_delta' else preds[selected[name]]
        for cohort,mask in masks.items():rows.append(dict(model=name,cohort=cohort,**metrics(held[mask],pred[mask])))
    for row in rows:
        zero=next(x['mse'] for x in rows if x['model']=='zero_delta' and x['cohort']==row['cohort'])
        row['mse_relative_to_zero']=row['mse']/zero
    report=dict(status='complete',completed_utc=datetime.now(timezone.utc).isoformat(),
                source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                config_sha256=digest(config_path),frozen_selection_sha256=digest(out/'frozen_selection.json'),
                selected=selected,cv_mse=cv,k562_selected_winner=winner,graph_qc=qc,sources=receipts,inputs=used,
                metrics_scope='Repeated RPE1 public pseudobulk diagnostics, not official VCC metrics; no RPE1-based selection',
                missing_basal_features={'K562':int(np.isnan(basal[:len(train)]).sum()),'RPE1':int(np.isnan(basal[len(train):]).sum())},
                rows=rows,elapsed_seconds=time.monotonic()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024))
    (out/'metrics.json').write_text(json.dumps(report,indent=2)+'\n');pd.DataFrame(rows).to_csv(out/'metrics.csv',index=False)
    print(json.dumps({'status':'complete','selected':selected,'winner':winner,'cv_mse':cv}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);run(p.parse_args().config)
