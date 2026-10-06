import gzip
import shutil

import h5py
import numpy as np
import pytest

from src.data.pseudobulk import aggregate, write_outputs


CFG = dict(target_symbol_key='gene', target_id_key='gene_id', guide_key='sgID_AB',
           batch_key='gem_group', library_size_key='UMI_count', control_label='non-targeting',
           minimum_controls_per_batch=1, normalization_target=10000, chunk_cells=2,
           normalization='log1p_counts_per_10000_total_UMI', assay_type='CRISPRi')
SOURCE = dict(dataset='fixture', line='K562', role='train')


def fixture(path, bad=False):
    # Unequal target counts by batch make a pooled-control baseline incorrect.
    x = np.array([[1, 9], [8, 2], [2, 8], [3, 7], [9, 1]], dtype='float32')
    if bad:
        x[0, 0] = .5
    with h5py.File(path, 'w') as f:
        f['X'] = x
        obs = f.create_group('obs')
        for name, vals in {'gene':['non-targeting','non-targeting','A','A','A'],
                           'gene_id':['non-targeting','non-targeting','ENSG1','ENSG1','ENSG1'],
                           'sgID_AB':['nt1','nt2','g1','g2','g1']}.items():
            obs.create_dataset(name, data=vals, dtype=h5py.string_dtype())
        obs['gem_group'] = [1,2,1,1,2]
        obs['UMI_count'] = [10.]*5
        var = f.create_group('var');var.attrs['_index']='gene_id'
        var.create_dataset('gene_id', data=['ENSG1','ENSG2'], dtype=h5py.string_dtype())
        var.create_dataset('gene_name', data=['A','B'], dtype=h5py.string_dtype())
    return x


def test_matched_controls_chunking_and_archive(tmp_path):
    path=tmp_path/'x.h5ad';x=fixture(path)
    gz=tmp_path/'x.h5ad.gz'
    with path.open('rb') as f, gzip.open(gz,'wb') as g:
        shutil.copyfileobj(f,g)
    r=aggregate(gz,CFG,SOURCE)
    expected=x[2:].mean(0)-(2*x[0]+x[1])/3
    np.testing.assert_allclose(r['means'][0,0]-r['matched'][0,0],expected,atol=1e-6)
    y=np.log1p(x*1000)
    np.testing.assert_allclose(r['means'][1,0]-r['matched'][1,0],y[2:].mean(0)-(2*y[0]+y[1])/3,atol=1e-6)
    assert r['support']==[2]
    assert r['qc']['n_control_cells']==2
    write_outputs(r,CFG,SOURCE,tmp_path/'out')
    import pyarrow.parquet as pq
    assert pq.read_metadata(tmp_path/'out/K562_pseudobulk.parquet').num_rows==2
    other=aggregate(path,{**CFG,'chunk_cells':5},SOURCE)
    np.testing.assert_allclose(r['means'],other['means'])


def test_missing_control_batch_fails(tmp_path):
    path=tmp_path/'x.h5ad';fixture(path)
    with h5py.File(path,'r+') as f:
        f['obs/gem_group'][4]=3
    with pytest.raises(ValueError,match='matched controls'):
        aggregate(path,CFG,SOURCE)


def test_noninteger_counts_fail(tmp_path):
    path=tmp_path/'x.h5ad';fixture(path,bad=True)
    with pytest.raises(ValueError,match='integer raw counts'):
        aggregate(path,CFG,SOURCE)
