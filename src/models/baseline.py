"""A fitted multinomial null: no perturbation-specific response in expectation.

Fit probabilities to pooled control counts. Generate NEW cells; never relabel
experimental cells for upload. Fixed library depth and multinomial variance are
deliberately simple and will not reproduce biological overdispersion.
"""
import anndata as ad
import numpy as np

from src.schema import check_counts


def fit_control_null(path, context, genes, max_counts, chunk_cells=100):
    data = ad.read_h5ad(path, backed='r')
    try:
        if list(data.var_names) != list(genes):
            raise ValueError(f'{context}: control gene axis/order mismatch.')
        if data.n_obs == 0:
            raise ValueError(f'{context}: no control cells.')
        if not {'context', 'target_gene'} <= set(data.obs):
            raise ValueError(f'{context}: missing control metadata.')
        if set(data.obs['context'].astype(str)) != {context}:
            raise ValueError(f'{context}: context identity mismatch; never relabel controls.')
        if set(data.obs['target_gene'].astype(str)) != {'non-targeting'}:
            raise ValueError(f'{context}: expected only non-targeting input cells.')
        totals = np.zeros(len(genes), dtype=np.float64)
        for start in range(0, data.n_obs, chunk_cells):
            block = data.X[start:start + chunk_cells]
            check_counts(block, max_counts)
            totals += np.asarray(block.sum(axis=0)).ravel()
        if totals.sum() <= 0:
            raise ValueError(f'{context}: all-zero controls.')
        return totals / totals.sum()
    finally:
        data.file.close()
