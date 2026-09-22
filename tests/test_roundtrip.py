import json
import subprocess
from copy import deepcopy
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from src.evaluate import prep_command
from src.predict import generate
from src.schema import check_counts, validate_prediction


@pytest.fixture
def experiment(tmp_path):
    genes, perts = ['GENE1', 'GENE2', 'GENE3'], ['GENE1', 'GENE2']
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    pd.Series(genes, name='gene_name').to_csv(bundle / 'gene_names.csv', index=False)
    pd.DataFrame({'target_gene': perts}).to_csv(bundle / 'pert_counts.csv', index=False)
    (bundle / 'manifest.json').write_text(json.dumps({
        'season': '2026', 'partition': 'val', 'contexts': ['A', 'B', 'C'],
        'n_genes': 3, 'n_constructs': 2, 'cells_per_pert': 4,
        'pert_col': 'target_gene', 'context_col': 'context', 'control_label': 'non-targeting',
        'panel_id': 'synthetic_fixture_only'}))
    for context, counts in zip('ABC', [[9, 1, 0], [0, 9, 1], [1, 0, 9]]):
        obs = pd.DataFrame({'context': [context] * 4, 'target_gene': ['non-targeting'] * 4},
                           index=[f'{context}_{i}' for i in range(4)])
        ad.AnnData(sparse.csr_matrix([counts] * 4), obs=obs, var=pd.DataFrame(index=genes)).write_h5ad(bundle / f'context_{context}.h5ad')
    config_path = tmp_path / 'fixture.yaml'
    config_path.write_text('synthetic fixture only\n')
    return {
        'experiment': 'synthetic', 'phase': 'validation', 'model': 'multinomial_control_null', 'seed': 2026,
        '_config_path': config_path,
        'paths': {'bundle': bundle, 'prediction': tmp_path / 'prediction.h5ad',
                  'submission': tmp_path / 'prediction.vcc', 'report': tmp_path / 'report.json'},
        'schema': {'contexts': list('ABC'), 'n_genes': 3, 'n_perturbations': 2,
                   'cells_per_perturbation': 4, 'max_stored_entries': 72, 'max_counts_per_cell': 100},
        'generation': {'chunk_cells': 3, 'library_size': 10},
    }


def test_roundtrip_through_official_cli(experiment):
    report = generate(experiment)
    assert report['n_cells'] == 24
    assert report['official_score'] is None
    data = ad.read_h5ad(experiment['paths']['prediction'])
    assert sparse.isspmatrix_csr(data.X)
    assert (np.asarray(data.X.sum(axis=1)).ravel() == 10).all()
    # Contexts remain attached to their distinct learned basal profiles.
    for context, absent in zip('ABC', [2, 0, 1]):
        assert data[data.obs.context == context].X[:, absent].sum() == 0
    result = subprocess.run(prep_command(experiment, package=True), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert experiment['paths']['submission'].is_file()


def test_reproducibility_and_no_overwrite(experiment):
    generate(experiment)
    first = ad.read_h5ad(experiment['paths']['prediction']).X
    with pytest.raises(FileExistsError):
        generate(experiment)
    other = deepcopy(experiment)
    other['paths']['prediction'] = other['paths']['prediction'].with_name('second.h5ad')
    other['paths']['report'] = other['paths']['report'].with_name('second.json')
    generate(other)
    second = ad.read_h5ad(other['paths']['prediction']).X
    assert (first != second).nnz == 0


def test_context_swap_fails(experiment):
    path = experiment['paths']['bundle'] / 'context_A.h5ad'
    control = ad.read_h5ad(path)
    control.obs['context'] = 'B'
    control.write_h5ad(path)
    with pytest.raises(ValueError, match='identity mismatch'):
        generate(experiment)


@pytest.mark.parametrize('bad', [[-1, 2], [0.5, 2], [np.nan, 2], [101, 0]])
def test_invalid_counts_fail(bad):
    with pytest.raises(ValueError):
        check_counts(sparse.csr_matrix([bad]), 100)


def test_wrong_gene_order_fails(experiment):
    generate(experiment)
    with pytest.raises(ValueError, match='gene axis'):
        validate_prediction(experiment['paths']['prediction'], ['GENE2', 'GENE1', 'GENE3'],
                            ['GENE1', 'GENE2'], experiment['schema'])


def test_wrong_phase_bundle_fails(experiment):
    experiment['phase'] = 'test'
    with pytest.raises(ValueError, match='manifest mismatch'):
        generate(experiment)


def test_resource_preflight_rejects_insufficient_host(experiment, monkeypatch):
    from src.resources import require_prep_resources
    generate(experiment)
    monkeypatch.setattr('src.resources.physical_memory_bytes', lambda: 1)
    with pytest.raises(RuntimeError, match='larger host'):
        require_prep_resources(experiment['paths']['prediction'], package=True)


def test_container_memory_limit(monkeypatch):
    from src.resources import memory_limit_bytes
    from pathlib import Path
    monkeypatch.setattr('src.resources.physical_memory_bytes', lambda: 64 * 1024**3)
    def read_limit(path, *args, **kwargs):
        if str(path) == '/sys/fs/cgroup/memory.max':
            return str(30 * 1024**3)
        raise FileNotFoundError(path)
    monkeypatch.setattr(Path, 'read_text', read_limit)
    assert memory_limit_bytes() == 30 * 1024**3
