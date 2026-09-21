"""Fit a zero-response null to controls and stream generated CSR cells to H5AD."""
import argparse
import json
import shutil
from importlib.metadata import version
from pathlib import Path

import anndata as ad
import h5py
import numpy as np
import pandas as pd
from scipy import sparse

from src.config import load_config
from src.models.baseline import fit_control_null
from src.schema import read_references, sha256, validate_prediction, validate_manifest


def generate(cfg):
    schema, paths = cfg['schema'], cfg['paths']
    manifest = validate_manifest(paths['bundle'], schema, cfg['phase'])
    genes, perts = read_references(paths['bundle'], schema)
    output = Path(paths['prediction'])
    report_path = Path(paths['report'])
    if output.exists() or report_path.exists():
        raise FileExistsError('Experiment already has output; use a new experiment config.')
    chunk = cfg['generation']['chunk_cells']
    depth = cfg['generation']['library_size']
    if not isinstance(chunk, int) or chunk < 1 or not isinstance(depth, int) or not 0 < depth <= schema['max_counts_per_cell']:
        raise ValueError('Invalid chunk size or library depth.')
    profiles, hashes = {}, {}
    for context in schema['contexts']:
        path = paths['bundle'] / f'context_{context}.h5ad'
        profiles[context] = fit_control_null(path, context, genes, schema['max_counts_per_cell'], chunk)
        hashes[path.name] = sha256(path)
    for name in ['gene_names.csv', 'pert_counts.csv', 'manifest.json']:
        path = paths['bundle'] / name
        if not path.is_file():
            raise FileNotFoundError(f'Missing official bundle file: {path}')
        hashes[name] = sha256(path)
    # Reserve conservatively before starting a long write. Compression is not a
    # reliable capacity promise, so plan for uncompressed expected sparse bytes.
    expected_nnz = sum(np.sum(-np.expm1(depth * np.log1p(-p))) for p in profiles.values())
    expected_nnz *= len(perts) * schema['cells_per_perturbation']
    planned_disk = int(expected_nnz * 8 * 1.1) + 512 * 1024**2
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < planned_disk:
        raise RuntimeError(f'Generation disk preflight needs about {planned_disk / 1024**3:.1f} GiB free '
                           '(conservative sparse estimate). Use a larger disk/host.')
    # Metadata is small; the expression matrix is never materialized in full.
    n = schema['cells_per_perturbation']
    obs = pd.DataFrame([(c, p) for c in schema['contexts'] for p in perts for _ in range(n)],
                       columns=['context', 'target_gene'])
    obs.index = pd.Index([f'pred_{i:09d}' for i in range(len(obs))])
    for column in obs:
        obs[column] = obs[column].astype('category')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.partial.h5ad')
    if temporary.exists():
        raise FileExistsError(f'Inspect/remove interrupted output first: {temporary}')
    ad.AnnData(sparse.csr_matrix((len(obs), len(genes)), dtype=np.int32), obs=obs,
               var=pd.DataFrame(index=genes)).write_h5ad(temporary)
    rng = np.random.default_rng(cfg['seed'])
    try:
        with h5py.File(temporary, 'r+') as handle:
            x = handle['X']
            for name in ('data', 'indices', 'indptr'):
                del x[name]
            values = x.create_dataset('data', (0,), maxshape=(None,), dtype='int32', compression='gzip')
            indices = x.create_dataset('indices', (0,), maxshape=(None,), dtype='int32', compression='gzip')
            indptr = x.create_dataset('indptr', (len(obs) + 1,), dtype='int64')
            indptr[0] = 0
            offset = row = 0
            for context in schema['contexts']:
                remaining = len(perts) * n
                while remaining:
                    if shutil.disk_usage(output.parent).free < 512 * 1024**2:
                        raise RuntimeError('Less than 512 MiB free disk; stopping generation.')
                    size = min(chunk, remaining)
                    block = sparse.csr_matrix(rng.multinomial(depth, profiles[context], size=size), dtype=np.int32)
                    end = offset + block.nnz
                    if end > schema['max_stored_entries']:
                        raise ValueError('Generation exceeds stored-entry cap.')
                    values.resize((end,)); indices.resize((end,))
                    values[offset:end] = block.data
                    indices[offset:end] = block.indices
                    indptr[row + 1:row + size + 1] = block.indptr[1:].astype(np.int64) + offset
                    offset, row, remaining = end, row + size, remaining - size
                print(f'Generated context {context}: {row:,} total cells', flush=True)
        summary = validate_prediction(temporary, genes, perts, schema, chunk)
        temporary.rename(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    report = {
        'experiment': cfg['experiment'], 'status': 'generated_locally_not_submitted',
        'model': cfg['model'], 'seed': cfg['seed'], 'library_size': depth,
        'official_score': None, 'input_sha256': hashes, 'panel_id': manifest['panel_id'],
        'config_sha256': sha256(cfg['_config_path']), 'prediction_sha256': sha256(output),
        'versions': {p: version(p) for p in ['numpy', 'scipy', 'anndata', 'vcc-cli']}, **summary,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    print(json.dumps(generate(load_config(args.config)), indent=2))


if __name__ == '__main__':
    main()
