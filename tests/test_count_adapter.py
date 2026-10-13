import numpy as np
import pytest
from src.count_adapter import ControlTransport


def test_counts_depth_and_determinism():
    x=np.array([[10,20,30],[30,10,20],[15,25,20]])
    model=ControlTransport(x,np.array([100,90,80]))
    a,d,q=model.generate(np.zeros(3),64,10)
    b,_,_=model.generate(np.zeros(3),64,10)
    assert np.array_equal(a,b)
    assert np.issubdtype(a.dtype,np.integer) and (a>=0).all()
    assert (a.sum(1)<=d).all()
    assert any(not np.any(np.all(row==x,axis=1)) for row in a)
    assert q['requested_delta_rmse']>=0


def test_transport_responds_to_direction_without_fitting_labels():
    model=ControlTransport(np.tile([30,30],(5,1)),np.full(5,100))
    up,_,_=model.generate(np.array([1.,-1.]),1000,22)
    base,_,_=model.generate(np.zeros(2),1000,22)
    assert up[:,0].mean()>base[:,0].mean()
    assert up[:,1].mean()<base[:,1].mean()


def test_fail_closed():
    with pytest.raises(ValueError):ControlTransport([[1,2],[1,2]],[2,2])
    m=ControlTransport([[1,2],[1,2]],[4,4])
    for delta in [[1],[float('nan'),0],[100,0]]:
        with pytest.raises(ValueError):m.generate(delta,2,1)
