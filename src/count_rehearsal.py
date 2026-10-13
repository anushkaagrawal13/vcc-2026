"""Bounded public RPE1 raw-count rehearsal; no challenge entry or scaled score."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import hashlib
import subprocess
import time

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse
import yaml
from src.count_adapter import ControlTransport
from src.data.pseudobulk import open_h5, column
from src.transfer import digest

ROOT=Path(__file__).resolve().parents[1]


def ann(counts, labels, genes, prefix):
    obs=pd.DataFrame({'target_gene':pd.Categorical(labels)},index=[f'{prefix}_{i}' for i in range(len(labels))])
    return ad.AnnData(sparse.csr_matrix(counts,dtype=np.int32),obs=obs,var=pd.DataFrame(index=genes))


def run(config):
    started=time.monotonic();cfg=yaml.safe_load(Path(config).read_text())
    art=ROOT/cfg['artifact_dir'];out=ROOT/cfg['results_dir']
    art.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    if (out/'metrics.json').exists():raise FileExistsError('Completed experiment exists')
    from cell_eval2 import EvalConfig, compute_metrics, aggregate_metrics
    from cell_eval2.run import metric_cohorts
    if version('cell-eval2')!=cfg['scorer_version']:raise ValueError('Scorer version mismatch')
    inputs=[]
    for mf,paths in [(cfg['input_manifest'],[cfg['raw']]),(cfg['model_manifest'],[cfg['model_dir']+'/'+n for n in ['gbm_string_predictions.npz','model_state.npz']])]:
        manifest=json.loads((ROOT/mf).read_text())
        for p in paths:
            record=next(r for r in manifest['files'] if r['path']==p)
            if digest(ROOT/p)!=record['sha256']:raise ValueError('Checksum mismatch '+p)
            inputs.append(record)
    prediction=np.load(ROOT/cfg['model_dir']/'gbm_string_predictions.npz')
    genes=prediction['output_gene_ids'].astype(str);model_ids=prediction['target_ids'].astype(str)
    cohorts=json.loads((ROOT/cfg['cohorts']).read_text())
    rng=np.random.default_rng(cfg['seed']);n=cfg['cells_per_target']
    with open_h5(ROOT/cfg['raw']) as f:
        ids=column(f['obs'],'gene_id').astype(str);symbols=column(f['obs'],'gene').astype(str)
        batches=column(f['obs'],'gem_group').astype(str)
        depth=column(f['obs'],'UMI_count').astype(float)
        available=column(f['var'],f['var'].attrs['_index']).astype(str)
        gi=pd.Index(available).get_indexer(genes)
        if np.any(gi<0):raise ValueError('Missing gene axis')
        selected=[];membership={}
        for cohort in ['shared_target_ids','RPE1_unseen_target_ids']:
            eligible=[i for i in cohorts[cohort] if (ids==i).sum()>=n and i in model_ids]
            chosen=sorted(eligible,key=lambda s:hashlib.sha256(s.encode()).hexdigest())[:cfg['targets_per_cohort']]
            if len(chosen)!=cfg['targets_per_cohort']:raise ValueError('Insufficient targets')
            selected+=chosen;membership.update({i:cohort for i in chosen})
        ctl=rng.permutation(np.flatnonzero(symbols=='non-targeting'))
        fit_ix=ctl[:cfg['fit_controls']];score_ix=ctl[cfg['fit_controls']:cfg['fit_controls']+cfg['score_controls']]
        target_ix=[rng.choice(np.flatnonzero(ids==i),n,replace=False) for i in selected]
        use=np.concatenate([fit_ix,score_ix,*target_ix]);order=np.argsort(use)
        # h5py requires increasing indices. Read chunks of selected rows only.
        counts=np.empty((len(use),len(genes)),dtype=np.int32)
        for start in range(0,len(order),128):
            ix=order[start:start+128];x=f['X'][use[ix],:][:,gi]
            if not np.isfinite(x).all() or np.any(x<0) or np.any(x!=np.floor(x)):raise ValueError('Invalid raw counts')
            counts[ix]=x
        libs=depth[use]
        selection=dict(targets=selected,cohorts=membership,cell_indices=use.tolist(),
                       fit_control_count=len(fit_ix),score_control_count=len(score_ix),
                       target_symbols={i:sorted(set(symbols[ids==i])) for i in selected},
                       gem_groups={i:dict(zip(*[a.tolist() for a in np.unique(batches[ix],return_counts=True)])) for i,ix in zip(selected,target_ix)},
                       selection=cfg['selection'],config_sha256=digest(config))
    (out/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    fit_n=len(fit_ix);score_n=len(score_ix)
    controls=counts[fit_n:fit_n+score_n];real_counts=counts[fit_n:]
    labels=['non-targeting']*score_n+[t for t in selected for _ in range(n)]
    real=ann(real_counts,labels,genes,'real');real.write_h5ad(art/'real.h5ad',compression='gzip')
    np.savez_compressed(art/'adapter_fit.npz',counts=counts[:fit_n],libraries=libs[:fit_n],output_gene_ids=genes)
    adapter=ControlTransport(counts[:fit_n],libs[:fit_n],cfg['normalization'])
    state=np.load(ROOT/cfg['model_dir']/'model_state.npz')
    if not np.array_equal(state['output_gene_ids'],genes):raise ValueError('Model mean axis mismatch')
    pred=prediction['predictions'][pd.Index(model_ids).get_indexer(selected)]
    deltas={'zero_delta':np.zeros_like(pred),'training_mean':np.broadcast_to(state['mean'],pred.shape),'gbm_string':pred}
    rows=[];diagnostics={}
    for model in cfg['models']:
        generated=[];diagnostics[model]=[]
        for j,target in enumerate(selected):
            x,d,q=adapter.generate(deltas[model][j],n,cfg['seed']+j)
            generated.append(x);diagnostics[model].append(dict(target=target,**q))
        synthetic=ann(np.vstack(generated),labels[score_n:],genes,'synthetic_'+model)
        synthetic.write_h5ad(art/(model+'_generated.h5ad'),compression='gzip')
        # Local scorer gets the SAME held-out real controls; upload artifact does not.
        score_pred=ann(np.vstack([controls,*generated]),labels,genes,'scorer_'+model)
        preset=EvalConfig.from_preset('vcc2026')
        ec=replace(preset,pert_col='target_gene',device='cpu',num_threads=1,
                   de=replace(preset.de,backend=cfg['backend']),outdir=str(art/model))
        print('Scoring '+model,flush=True)
        frame=compute_metrics(score_pred,real,config=ec)
        frame.write_csv(out/(model+'_per_target.csv'))
        metric_cohorts(frame).write_csv(out/(model+'_metric_cohorts.csv'))
        summary=aggregate_metrics(frame)
        summary.write_csv(out/(model+'_aggregate.csv'))
        rows.extend(dict(model=model,**{k:(None if isinstance(v,float) and not np.isfinite(v) else v) for k,v in r.items()}) for r in summary.to_dicts())
    report=dict(status='complete',scope='Six-target public RPE1 diagnostic using official raw metrics; not a challenge score or a new untouched holdout',
                limitations=['No context-specific replicate/baseline scaling anchors','Mean-log delta transport is approximate; no RPE1 tuning','7226 common output genes only','Pooled RPE1 controls; gem-group imbalance is not corrected','Six-target PDS has coarse ranks; do not use for model selection'],
                completed_utc=datetime.now(timezone.utc).isoformat(),config_sha256=digest(config),
                source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                inputs=inputs,targets=selected,rows=rows,adapter_diagnostics=diagnostics,
                versions={p:version(p) for p in ['cell-eval2','pdex','numpy','anndata']},elapsed_seconds=time.monotonic()-started)
    (out/'metrics.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':'complete','rows':rows}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);run(p.parse_args().config)
