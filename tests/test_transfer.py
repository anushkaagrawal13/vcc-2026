import numpy as np
import pandas as pd
import pytest
from src.models.ridge import fit, predict, select_alpha
from src.transfer import load_deltas, metrics, nearest_line


def test_ridge_matches_independent_regularized_normal_equations():
    x=np.array([1.,2.,np.nan,5.,9.]); y=np.arange(15.).reshape(5,3)**1.2
    model=fit(x,y,3.)
    filled=np.where(np.isfinite(x),x,3.5)
    design=np.column_stack([np.ones(5),(filled-filled.mean())/filled.std()])
    expected=np.linalg.solve(design.T@design+np.diag([0.,3.]),design.T@y)
    np.testing.assert_allclose(predict(model,x),design@expected)
    assert model['median']==3.5
    assert np.isfinite(predict(model,np.array([np.nan,1000.]))).all()


def test_cv_fits_preprocessing_only_on_fold_training(monkeypatch):
    import src.models.ridge as ridge
    original=ridge.fit; seen=[]
    def capture(x,y,alpha):
        model=original(x,y,alpha);seen.append((x.copy(),model['median']))
        return model
    monkeypatch.setattr(ridge,'fit',capture)
    x=np.arange(12,dtype=float);x[3]=np.nan;y=np.arange(24.).reshape(12,2)
    _,scores,folds=select_alpha(x,y,[1.,10.],3,44)
    assert len(seen)==6 and len(scores)==2
    for i,(values,median) in enumerate(seen):
        valid=folds[i%3];train=np.setdiff1d(np.arange(12),valid)
        np.testing.assert_equal(values,x[train])
        assert median==np.nanmedian(x[train])


def test_gene_alignment_and_duplicate_rejection(tmp_path):
    p=tmp_path/'table.parquet'
    f=pd.DataFrame({'target_gene_id':['B','A','A','B'], 'output_gene_id':['y','x','y','x'], 'delta_log1p_cp10k':[4.,1.,2.,3.]})
    f.to_parquet(p)
    np.testing.assert_equal(load_deltas(p,['A','B'],['x','y']),[[1.,2.],[3.,4.]])
    pd.concat([f,f.iloc[:1]]).to_parquet(p)
    with pytest.raises(ValueError,match='Duplicate'):load_deltas(p,['A','B'],['x','y'])


def test_unseen_transfer_fallback_and_undefined_zero_correlation():
    y=np.array([[1.,2.],[5.,8.]])
    np.testing.assert_equal(nearest_line(['A','B'],y,['B','C']),[[5.,8.],[3.,5.]])
    m=metrics(y,np.zeros_like(y))
    assert m['mse']==23.5 and m['mean_target_pearson'] is None
    assert metrics(y,y)['mean_target_pearson']==pytest.approx(1.)
