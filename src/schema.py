"""Read official references and inspect raw counts in bounded row chunks."""
import hashlib
import json
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_references(bundle, schema):
    bundle = Path(bundle)
    genes = pd.read_csv(bundle / 'gene_names.csv', header=None, dtype=str)
    perts = pd.read_csv(bundle / 'pert_counts.csv', dtype=str)
    if genes.shape[1] == 1 and len(genes) and genes.iloc[0, 0] == 'gene_name':
        genes = genes.iloc[1:]
    if genes.shape[1] != 1 or len(genes) != schema['n_genes']:
        raise ValueError('gene_names.csv must match n_genes (optional gene_name header).')
    if list(perts.columns) != ['target_gene']:
        raise ValueError('Expected official one-column target_gene perturbation list.')
    genes, perts = genes.iloc[:, 0], perts['target_gene']
    for name, values in [('genes', genes), ('perturbations', perts)]:
        if values.isna().any() or values.duplicated().any() or (values.str.strip() != values).any():
            raise ValueError(f'Missing, duplicate or whitespace-padded {name}.')
    if len(perts) != schema['n_perturbations'] or 'non-targeting' in set(perts):
        raise ValueError('Invalid perturbation panel.')
    return genes.tolist(), perts.tolist()


def validate_manifest(bundle, schema, phase):
    manifest = json.loads((Path(bundle) / 'manifest.json').read_text())
    expected = {'season': '2026', 'partition': {'validation': 'val', 'test': 'test'}[phase],
                'contexts': schema['contexts'], 'n_genes': schema['n_genes'],
                'n_constructs': schema['n_perturbations'],
                'cells_per_pert': schema['cells_per_perturbation'],
                'pert_col': 'target_gene', 'context_col': 'context', 'control_label': 'non-targeting'}
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f'Bundle manifest mismatch for {key}: expected {value!r}.')
    return manifest


def check_counts(matrix, max_counts):
    values = matrix.data if sparse.issparse(matrix) else np.asarray(matrix)
    if not np.isfinite(values).all() or (values < 0).any() or (values != np.floor(values)).any():
        raise ValueError('X must contain finite, non-negative, integer raw counts.')
    totals = np.asarray(matrix.sum(axis=1)).ravel()
    if (totals > max_counts).any():
        raise ValueError('A cell exceeds max_counts_per_cell.')
    return totals


def validate_prediction(path, genes, perts, schema, chunk_cells=100):
    data = ad.read_h5ad(path, backed='r')
    try:
        if list(data.var_names) != list(genes):
            raise ValueError('Prediction gene axis/order differs from official genes.')
        if not data.obs_names.is_unique:
            raise ValueError('Cell identifiers must be unique.')
        if not {'context', 'target_gene'} <= set(data.obs):
            raise ValueError('Missing context or target_gene column.')
        counts = data.obs.groupby(['context', 'target_gene'], observed=True).size()
        expected = {(ctx, pert) for ctx in schema['contexts'] for pert in perts}
        if set(counts.index) != expected or not (counts == schema['cells_per_perturbation']).all():
            raise ValueError('Incorrect context, perturbation panel or cell counts.')
        stored = 0
        for start in range(0, data.n_obs, chunk_cells):
            block = data.X[start:start + chunk_cells]
            check_counts(block, schema['max_counts_per_cell'])
            if not sparse.issparse(block):
                raise ValueError('Predictions must use sparse storage.')
            if (block.data == 0).any():
                raise ValueError('Sparse prediction contains explicit zeros.')
            stored += block.nnz
        if stored > schema['max_stored_entries']:
            raise ValueError('Prediction exceeds the stored-entry cap.')
        return {'n_cells': data.n_obs, 'n_genes': data.n_vars, 'stored_entries': stored}
    finally:
        data.file.close()
