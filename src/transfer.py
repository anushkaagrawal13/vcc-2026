"""Public pseudobulk transfer diagnostics, explicitly not official VCC metrics."""
import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml

from src.models.ridge import fit, predict, select_alpha

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_deltas(path, target_ids, gene_ids):
    """Stream only selected columns, bounding memory independently of tidy size."""
    ti = pd.Index(target_ids); gi = pd.Index(gene_ids)
    result = np.full((len(ti), len(gi)), np.nan)
    for batch in pq.ParquetFile(path).iter_batches(batch_size=32768, columns=['target_gene_id','output_gene_id','delta_log1p_cp10k'], use_threads=False):
        frame = batch.to_pandas()
        rows = ti.get_indexer(frame.target_gene_id); cols = gi.get_indexer(frame.output_gene_id)
        use = (rows >= 0) & (cols >= 0)
        rows, cols = rows[use], cols[use]
        keys = rows*len(gi)+cols
        if len(np.unique(keys)) != len(keys) or np.isfinite(result[rows, cols]).any():
            raise ValueError('Duplicate target/output mapping; aliases require explicit resolution')
        result[rows, cols] = frame.delta_log1p_cp10k.to_numpy()[use]
    if not np.isfinite(result).all():
        raise ValueError('Incomplete or nonfinite target/output matrix')
    return result


def metrics(observed, predicted):
    if observed.shape != predicted.shape or not np.isfinite(predicted).all():
        raise ValueError('Invalid prediction matrix')
    error = predicted-observed
    a = observed-observed.mean(axis=1, keepdims=True)
    b = predicted-predicted.mean(axis=1, keepdims=True)
    denom = np.linalg.norm(a, axis=1)*np.linalg.norm(b, axis=1)
    valid = denom > 1e-15
    correlations = np.full(len(a), np.nan)
    correlations[valid] = (a[valid]*b[valid]).sum(axis=1)/denom[valid]
    return dict(mse=float(np.square(error).mean()), mae=float(np.abs(error).mean()),
                mean_target_pearson=float(correlations[valid].mean()) if valid.any() else None,
                pearson_defined_targets=int(valid.sum()), n_targets=len(a), n_output_genes=observed.shape[1])


def nearest_line(train_ids, train_y, held_ids):
    """Only one training line: same-target K562 delta; unseen => K562 mean."""
    idx = pd.Index(train_ids).get_indexer(held_ids)
    out = np.broadcast_to(train_y.mean(axis=0), (len(held_ids), train_y.shape[1])).copy()
    shared = idx >= 0
    out[shared] = train_y[idx[shared]]
    return out


def run(config_path):
    started = time.monotonic()
    cfg = yaml.safe_load(Path(config_path).read_text())
    out = ROOT/cfg['results_dir']; out.mkdir(parents=True, exist_ok=True)
    artifact = ROOT/cfg['artifact_dir']; artifact.mkdir(parents=True, exist_ok=True)
    source = ROOT/cfg['input_dir']
    manifest = json.loads((ROOT/cfg['input_manifest']).read_text())
    used = []
    for line in ['K562','RPE1']:
        for suffix in ['control_baseline','matched_strata','pseudobulk']:
            path = source/f'{line}_{suffix}.parquet'
            record = next(x for x in manifest['files'] if x['path']==str(path.relative_to(ROOT)))
            if digest(path) != record['sha256']:
                raise ValueError('Input checksum mismatch: '+str(path))
            used.append(record)
    controls = {line: pd.read_parquet(source/f'{line}_control_baseline.parquet').set_index('output_gene_id') for line in ['K562','RPE1']}
    strata = {line: pd.read_parquet(source/f'{line}_matched_strata.parquet') for line in ['K562','RPE1']}
    ids = {line: sorted(i for i in set(frame.target_gene_id) if i.startswith('ENSG')) for line, frame in strata.items()}
    genes = sorted(set(controls['K562'].index)&set(controls['RPE1'].index))
    x = {line: controls[line].mean_log1p_cp10k.reindex(ids[line]).to_numpy() for line in ids}
    train = load_deltas(source/'K562_pseudobulk.parquet', ids['K562'], genes)
    print('Verified inputs and loaded K562; selecting alpha on K562 only', flush=True)
    alpha, scores, folds = select_alpha(x['K562'], train, cfg['alphas'], cfg['folds'], cfg['seed'])
    model = fit(x['K562'], train, alpha)
    # Persist training choices BEFORE reading RPE1 perturbation outcomes.
    frozen = dict(alpha=alpha, cv=scores, imputation_median=model['median'], feature_mean=model['mean'], feature_scale=model['scale'],
                  folds=[[ids['K562'][i] for i in group] for group in folds], config_sha256=digest(config_path),
                  feature='target-gene mean log1p CP10k in that line non-targeting controls',
                  missing_feature_policy='median of available K562 training-target features; refit within folds',
                  target_ids=ids, output_gene_ids=genes)
    (out/'frozen_model.json').write_text(json.dumps(frozen, indent=2)+'\n')
    np.savez_compressed(artifact/'ridge.npz', **model, output_gene_ids=genes)
    ridge = predict(model, x['RPE1'])
    np.savez_compressed(artifact/'ridge_predictions.npz', predictions=ridge, target_ids=ids['RPE1'], output_gene_ids=genes)
    held = load_deltas(source/'RPE1_pseudobulk.parquet', ids['RPE1'], genes)
    shared = np.isin(ids['RPE1'], ids['K562'])
    masks = {'all_mapped':np.ones(len(shared),dtype=bool), 'shared_targets':shared, 'unseen_targets':~shared}
    rows = []
    predictions = {'zero_delta': np.zeros_like(held), 'training_mean':np.broadcast_to(train.mean(axis=0), held.shape),
                   'ridge_one_feature':ridge, 'nearest_line_same_target_else_mean':nearest_line(ids['K562'],train,ids['RPE1'])}
    for name, pred in predictions.items():
        for cohort, mask in masks.items():
            rows.append(dict(model=name, cohort=cohort, **metrics(held[mask], pred[mask])))
    for row in rows:
        zero = next(r['mse'] for r in rows if r['model']=='zero_delta' and r['cohort']==row['cohort'])
        row['mse_relative_to_zero'] = row['mse']/zero
    report = dict(status='complete', completed_utc=datetime.now(timezone.utc).isoformat(),
                  source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  config_sha256=digest(config_path), inputs=used, selected_alpha=alpha, cv=scores,
                  training_preprocessing={k:model[k] for k in ['median','mean','scale']},
                  frozen_model_sha256=digest(out/'frozen_model.json'),
                  metrics_scope='Public pseudobulk diagnostics on log1p CP10k deltas; NOT official six-metric VCC score',
                  train_targets=len(ids['K562']), held_targets=len(ids['RPE1']), common_output_genes=len(genes),
                  unmapped_held_targets=sorted(set(strata['RPE1'].target_gene_id)-set(ids['RPE1'])),
                  missing_feature_counts={line:int((~np.isfinite(values)).sum()) for line,values in x.items()},
                  rows=rows, elapsed_seconds=time.monotonic()-started,
                  peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024))
    (out/'metrics.json').write_text(json.dumps(report,indent=2)+'\n')
    pd.DataFrame(rows).to_csv(out/'metrics.csv',index=False)
    print(json.dumps(report), flush=True)
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    run(parser.parse_args().config)
