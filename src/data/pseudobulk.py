"""Chunked Replogle deltas with controls matched within line and gem group.

Both raw-count and log1p-CP10k means are retained. Target cells weight the matched
control means; no RPE1 outcome is pooled with K562. Archives preserve original
single cells for later DE evaluation. This is a descriptive aggregation, not a
biological score or an inferred independent-replicate estimate.
"""
import argparse
from contextlib import contextmanager
import gzip
import hashlib
import json
from pathlib import Path
import time

import h5py
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy import sparse

from .replogle import ROOT, load_config


@contextmanager
def open_h5(path):
    if str(path).endswith('.gz'):
        with gzip.open(path, 'rb') as stream, h5py.File(stream, 'r') as f:
            yield f
    else:
        with h5py.File(path, 'r') as f:
            yield f


def column(group, name):
    """Read old AnnData 0.1 categorical references or modern categories."""
    item = group[name]
    if isinstance(item, h5py.Group):
        codes, cats = item['codes'][:], item['categories'][:]
    elif 'categories' in item.attrs:
        codes, cats = item[:], group.file[item.attrs['categories']][:]
    else:
        values = item[:]
        return np.array([x.decode() if isinstance(x, bytes) else x for x in values])
    if np.any(codes < 0):
        raise ValueError(f'Missing categorical values in {name}')
    cats = np.array([x.decode() if isinstance(x, bytes) else x for x in cats])
    return cats[codes]


def aggregate(path, cfg, source):
    started = time.monotonic()
    with open_h5(path) as f:
        obs, var, matrix = f['obs'], f['var'], f['X']
        if not isinstance(matrix, h5py.Dataset) or matrix.ndim != 2:
            raise ValueError('Expected the inspected dense raw-count X dataset')
        targets = column(obs, cfg['target_symbol_key']).astype(str)
        ids = column(obs, cfg['target_id_key']).astype(str)
        guides = column(obs, cfg['guide_key']).astype(str)
        batches = column(obs, cfg['batch_key']).astype(str)
        libraries = column(obs, cfg['library_size_key']).astype(np.float64)
        output_ids = column(var, var.attrs['_index']).astype(str)
        output_names = column(var, 'gene_name').astype(str)
        if len(set(output_ids)) != len(output_ids):
            raise ValueError('Duplicate output gene IDs')
        if matrix.shape != (len(targets), len(output_ids)):
            raise ValueError('Metadata shape mismatch')
        control = targets == cfg['control_label']
        if not np.array_equal(control, ids == cfg['control_label']):
            raise ValueError('Control symbol and ID disagree')
        if not np.all(np.isfinite(libraries) & (libraries > 0)):
            raise ValueError('Missing or nonpositive library sizes')
        if not np.all(np.char.startswith(ids[~control], 'ENSG')):
            raise ValueError('Unexpected target gene identifier')
        batch_names, batch_index = np.unique(batches, return_inverse=True)
        control_counts = np.bincount(batch_index[control], minlength=len(batch_names))
        if np.any(control_counts < cfg['minimum_controls_per_batch']):
            raise ValueError('Insufficient matched controls in at least one gem group')
        # Preserve symbol/ID pairs: the RPE1 source has aliases sharing Ensembl IDs.
        pairs = sorted(set(zip(ids[~control], targets[~control])))
        lookup = {pair: i for i, pair in enumerate(pairs)}
        target_index = np.array([-1 if c else lookup[(i, t)] for i, t, c in zip(ids, targets, control)])
        nt, ng, nb = len(pairs), len(output_ids), len(batch_names)
        n = np.bincount(target_index[~control], minlength=nt)
        weights = np.zeros((nt, nb), dtype=np.int64)
        np.add.at(weights, (target_index[~control], batch_index[~control]), 1)
        sums = np.zeros((2, nt + nb, ng), dtype=np.float64)
        row_group = np.where(control, nt + batch_index, target_index)
        max_count, min_library_fraction = 0., 1.
        for start in range(0, len(targets), cfg['chunk_cells']):
            end = min(start + cfg['chunk_cells'], len(targets))
            x = matrix[start:end].astype(np.float64)
            if not np.all(np.isfinite(x)) or np.any(x < 0) or np.any(x != np.floor(x)):
                raise ValueError('X must contain nonnegative finite integer raw counts')
            row_sum = x.sum(axis=1)
            if np.any(row_sum > libraries[start:end] + 0.01):
                raise ValueError('Matrix counts exceed total UMI metadata')
            min_library_fraction = min(min_library_fraction, float(np.min(row_sum / libraries[start:end])))
            max_count = max(max_count, float(x.max()))
            assignment = sparse.csr_matrix((np.ones(end-start), (row_group[start:end], np.arange(end-start))), shape=(nt+nb, end-start))
            # Sparse group aggregation avoids one dense (target,batch,gene) tensor.
            sums[0] += assignment @ x
            x *= cfg['normalization_target'] / libraries[start:end, None]
            np.log1p(x, out=x)
            sums[1] += assignment @ x
            if start % (cfg['chunk_cells'] * 50) == 0:
                print(json.dumps({'event': 'aggregate', 'line': source['line'], 'cells': end}), flush=True)
        control_means = sums[:, nt:] / control_counts[None, :, None]
        means = sums[:, :nt] / n[None, :, None]
        matched = np.stack([(weights / n[:, None]) @ c for c in control_means])
        support = [len(set(guides[target_index == i])) for i in range(nt)]
        qc = {'dataset': source['dataset'], 'line': source['line'], 'role': source['role'],
              'n_cells': len(targets), 'n_control_cells': int(control.sum()), 'n_target_cells': int((~control).sum()),
              'n_targets': nt, 'n_unique_target_ids': len(set(i for i, _ in pairs)),
              'n_output_genes': ng, 'n_gem_groups': nb, 'minimum_controls_per_gem': int(control_counts.min()),
              'min_target_cells': int(n.min()), 'min_guide_pairs_per_target': min(support),
              'all_X_counts_integer_nonnegative': True, 'maximum_count': max_count,
              'minimum_fraction_of_total_UMI_in_retained_genes': min_library_fraction,
              'expression_scale': cfg['normalization'], 'matching': 'dataset,line,assay_type,gem_group',
              'aggregation': 'cell-weighted target mean minus target-cell-weighted matched-gem control means',
              'no_target_cell_filtering': True, 'elapsed_seconds': time.monotonic()-started}
        return dict(pairs=pairs, output_ids=output_ids, output_names=output_names, means=means, matched=matched,
                    n=n, support=support, weights=weights, batch_names=batch_names, control_counts=control_counts,
                    control_means=control_means, qc=qc)


def write_outputs(result, cfg, source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / (source['line'] + '_pseudobulk.parquet')
    writer = None
    try:
        for t, (target_id, target_name) in enumerate(result['pairs']):
            frame = pd.DataFrame({'output_gene_id': result['output_ids'], 'output_gene': result['output_names'],
                                  'mean_raw_count': result['means'][0,t], 'matched_control_raw_count': result['matched'][0,t],
                                  'delta_raw_count': result['means'][0,t]-result['matched'][0,t],
                                  'mean_log1p_cp10k': result['means'][1,t], 'matched_control_log1p_cp10k': result['matched'][1,t],
                                  'delta_log1p_cp10k': result['means'][1,t]-result['matched'][1,t]})
            for key, val in {'dataset':source['dataset'], 'line':source['line'], 'assay_type':cfg['assay_type'],
                             'role':source['role'], 'target_gene_id':target_id, 'target_gene':target_name,
                             'n_cells':int(result['n'][t]), 'n_guide_pairs':result['support'][t],
                             'n_matched_gem_groups':int((result['weights'][t]>0).sum())}.items():
                frame[key] = val
            table = pa.Table.from_pandas(frame, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(output, table.schema, compression='zstd')
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()
    ctrl = np.average(result['control_means'], axis=1, weights=result['control_counts'])
    pd.DataFrame({'output_gene_id':result['output_ids'], 'output_gene':result['output_names'],
                  'mean_raw_count':ctrl[0], 'mean_log1p_cp10k':ctrl[1]}).to_parquet(destination / (source['line']+'_control_baseline.parquet'), index=False)
    strata = []
    for t, pair in enumerate(result['pairs']):
        for b in np.flatnonzero(result['weights'][t]):
            strata.append({'target_gene_id':pair[0], 'target_gene':pair[1], 'gem_group':result['batch_names'][b],
                           'n_target_cells':int(result['weights'][t,b]), 'n_control_cells':int(result['control_counts'][b])})
    pd.DataFrame(strata).to_parquet(destination / (source['line']+'_matched_strata.parquet'), index=False)
    result['qc']['tidy_rows'] = len(result['pairs']) * len(result['output_ids'])
    result['qc']['outputs'] = []
    for path in sorted(destination.glob(source['line']+'*.parquet')):
        h = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda:f.read(8 << 20), b''):
                h.update(chunk)
        result['qc']['outputs'].append({'name':path.name, 'bytes':path.stat().st_size, 'sha256':h.hexdigest()})


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    p.add_argument('--line', choices=['K562','RPE1'])
    args = p.parse_args()
    cfg = load_config(args.config)
    destination = ROOT / cfg['processed_dir']
    reports = ROOT / cfg['results_dir']
    reports.mkdir(parents=True, exist_ok=True)
    axes = {}
    for source in cfg['sources']:
        if args.line and args.line != source['line']:
            continue
        path = ROOT / cfg['raw_dir'] / (source['name']+'.gz')
        receipt = json.loads(path.with_suffix(path.suffix+'.json').read_text())
        result = aggregate(path, cfg, source)
        write_outputs(result, cfg, source, destination)
        axes[source['line']] = {'target_ids': sorted(set(i for i, _ in result['pairs'])),
                                'output_ids': result['output_ids'].tolist()}
        result['qc'].update(config_sha256=cfg['_sha256'], source=receipt)
        (reports / (source['line']+'_qc.json')).write_text(json.dumps(result['qc'], indent=2)+'\n')
        print(json.dumps({'event':'complete', 'line':source['line'], 'rows':result['qc']['tidy_rows']}), flush=True)
    if set(axes) == {'K562', 'RPE1'}:
        train, held = set(axes['K562']['target_ids']), set(axes['RPE1']['target_ids'])
        cohort = {'shared_target_ids': sorted(train & held), 'RPE1_unseen_target_ids': sorted(held-train),
                  'common_output_gene_ids': sorted(set(axes['K562']['output_ids']) & set(axes['RPE1']['output_ids'])),
                  'note': 'Metadata-only cohorts; no outcome-based selection or tuning.'}
        cohort['counts'] = {k: len(v) for k, v in cohort.items() if isinstance(v, list)}
        (reports / 'cohorts.json').write_text(json.dumps(cohort, indent=2)+'\n')


if __name__ == '__main__':
    main()
