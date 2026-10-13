import gzip
import numpy as np
from src.features import neighbor_features,standardize_fit,standardize
from src.rich_transfer import response_basis,ridge_fit
from src.data.string_prior import build_graph


def test_neighbor_prior_excludes_self_and_validation_labels():
    w=np.array([[1.,1.],[1.,1.],[0.,0.]])
    z=np.array([[2.,4.],[10.,20.]])
    x=neighbor_features(w,['A','V','I'],['A','B'],z,np.array([1.,2.,np.nan]))
    np.testing.assert_equal(x[0,3:],[10.,20.])
    np.testing.assert_equal(x[1,3:],[6.,12.])
    np.testing.assert_equal(x[2,3:],[0.,0.])
    assert x[0,2]==np.log(2) and x[1,2]==np.log(3)
    # Changing reference A cannot change A's own prior; no validation y exists in API.
    z[0]=1e9
    other=neighbor_features(w,['A','V','I'],['A','B'],z,np.array([1.,2.,np.nan]))
    np.testing.assert_equal(x[0],other[0])


def test_train_only_projection_reconstructs_low_rank_response():
    rng=np.random.default_rng(19);y=rng.normal(size=(30,3))@rng.normal(size=(3,25))+4
    mean,basis,z=response_basis(y,3,2026)
    np.testing.assert_allclose(mean+z@basis,y,atol=1e-10)
    np.testing.assert_allclose(basis@basis.T,np.eye(3),atol=1e-10)


def test_multifeature_ridge_and_imputer():
    x=np.array([[1.,np.nan],[3.,4.],[5.,8.],[7.,12.]])
    state=standardize_fit(x);xx=standardize(x,state);z=np.arange(12.).reshape(4,3)
    coef,intercept=ridge_fit(xx,z,2.)
    design=np.column_stack([np.ones(4),xx])
    expected=np.linalg.solve(design.T@design+np.diag([0.,2.,2.]),design.T@z)
    np.testing.assert_allclose(xx@coef+intercept,design@expected,atol=1e-10)
    assert state['median'][1]==8


def test_string_mapping_and_undirected_max(tmp_path):
    a,b,c='ENSG00000000001','ENSG00000000002','ENSG00000000003'
    with gzip.open(tmp_path/'9606.protein.aliases.v12.0.txt.gz','wt') as f:
        f.write(f'#protein\talias\tsource\np1\t{a}\tx\np2\t{b}\tx\np3\t{c}\tx\np3\tENSG00000009999\tx\n')
    with gzip.open(tmp_path/'9606.protein.links.v12.0.txt.gz','wt') as f:
        f.write('protein1 protein2 combined_score\np1 p2 800\np2 p1 900\np1 p1 999\np2 p3 999\n')
    w,qc=build_graph(tmp_path,[a,b,c],700)
    np.testing.assert_allclose(w,[[0,.9,0],[.9,0,0],[0,0,0]])
    assert qc['ambiguous_proteins_skipped']==1 and qc['undirected_edges']==1


def test_lightgbm_component_fit_is_deterministic():
    from src.models.gbm import fit_components,predict_components
    rng=np.random.default_rng(2);x=rng.normal(size=(60,3));z=np.column_stack([x[:,0]**2,x[:,1]])
    cfg=dict(gbm_learning_rate=.1,gbm_min_data=5,gbm_rounds=5,seed=2026)
    a=fit_components(x,z,7,cfg);b=fit_components(x,z,7,cfg)
    np.testing.assert_equal(predict_components(a,x),predict_components(b,x))


def test_chunked_metrics_equal_full_metrics():
    from src.rich_transfer import chunk_metrics
    from src.transfer import metrics
    rng=np.random.default_rng(4);y=rng.normal(size=(290,11));p=y+rng.normal(size=y.shape)
    mask=np.arange(len(y))%3!=0
    actual=chunk_metrics(y,p,mask);expected=metrics(y[mask],p[mask])
    for key in expected:np.testing.assert_allclose(actual[key],expected[key])


def test_disk_prediction_matches_memory(tmp_path):
    from src.rich_transfer import fold_predict
    rng=np.random.default_rng(6);y=rng.normal(size=(20,12));w=np.ones((25,25));ids=[str(i) for i in range(25)]
    cfg=dict(rank=3,seed=2026,ridge_alphas=[1],gbm_leaves=[],gbm_rounds=2,gbm_min_data=3,gbm_learning_rate=.1)
    a,_,_=fold_predict(y,np.arange(20),np.arange(20,25),ids,w,np.arange(25),cfg)
    b,_,_=fold_predict(y,np.arange(20),np.arange(20,25),ids,w,np.arange(25),cfg,tmp_path)
    for key in a:np.testing.assert_allclose(a[key],b[key])
