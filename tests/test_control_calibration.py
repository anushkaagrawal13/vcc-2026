"""Small numerical tests also runnable with Python unittest and NumPy alone."""
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from src.count_adapter import MeanCalibratedTransport
from src.control_calibration import split_controls, balanced_donors, distribution_metrics, select_candidate, evaluate_candidates


class ControlCalibrationTests(unittest.TestCase):
    def test_disjoint_balanced_splits(self):
        batches=np.repeat(['a','b','c'],30)
        parts=split_controls(batches,12,4,4,21)
        self.assertEqual(len(set(np.concatenate(parts))),60)
        for part,n in zip(parts,[12,4,4]):
            self.assertEqual(np.unique(batches[part],return_counts=True)[1].tolist(),[n]*3)
        for a,b in zip(parts,split_controls(batches,12,4,4,21)):
            np.testing.assert_array_equal(a,b)
        with self.assertRaises(ValueError):split_controls(['a']*10,12,4,4,1)

    def test_donor_balance_and_depth(self):
        batches=np.repeat(['a','b'],[8,20])
        donors=balanced_donors(batches,16,2)
        self.assertEqual(np.unique(batches[donors],return_counts=True)[1].tolist(),[16,16])
        x=np.tile([1,3,6],(28,1));d=np.arange(28)+20
        m=MeanCalibratedTransport(x,d)
        a,depth,_=m.generate(np.zeros(3),32,7,donors)
        np.testing.assert_array_equal(depth,d[donors])
        self.assertTrue(np.all(a.sum(1)<=depth))
        self.assertTrue(np.issubdtype(a.dtype,np.integer))
        with self.assertRaises(ValueError):m.generate(np.zeros(3),2,1,[0,100])
        with self.assertRaises(ValueError):m.generate(np.zeros(3),2,1,[0.,1.])

    def test_mean_correction_on_independent_draws(self):
        # Deliberately sparse controls expose the extra multinomial sampling bias.
        rng=np.random.default_rng(42)
        x=rng.poisson(np.linspace(.1,2,12),size=(160,12));d=np.full(160,100)
        m=MeanCalibratedTransport(x,d,100)
        state=m.calibrate(np.zeros(12),16,2000,11)
        before=[];after=[]
        for seed in [90,91,92]:
            a,da,_=m.generate(np.zeros(12),3000,seed)
            b,db,q=m.generate_calibrated(state,3000,seed)
            before.append(distribution_metrics(a,da,x,d,100)['mean_log_rmse'])
            after.append(distribution_metrics(b,db,x,d,100)['mean_log_rmse'])
            expected=np.sqrt(np.mean((np.log1p(b*100/db[:,None]).mean(0)-m.mean_log)**2))
            self.assertAlmostEqual(q['requested_delta_rmse'],expected)
        self.assertLess(np.mean(after),.75*np.mean(before))

    def test_nonzero_delta_and_physical_floor(self):
        x=np.tile([2,5,8],(100,1));d=np.full(100,100)
        m=MeanCalibratedTransport(x,d,100)
        delta=np.array([.1,-.1,-3.])
        state=m.calibrate(delta,8,200,101)
        self.assertEqual(state['qc']['impossible_negative_mean_genes'],1)
        counts,depth,_=m.generate_calibrated(state,200,222)
        self.assertTrue((counts>=0).all())
        self.assertTrue((counts.sum(1)<=depth).all())
        self.assertLess(counts[:,2].mean(),.1)
        with self.assertRaises(ValueError):m.calibrate([float('nan')]*3,8,20,1)
        with self.assertRaises(ValueError):m.calibrate(delta,0,20,1)

    def test_selection_uses_equal_seed_sets_and_mean_not_best_seed(self):
        rows=[dict(candidate='legacy',seed=1,mean_log_rmse=.2),dict(candidate='legacy',seed=2,mean_log_rmse=.2),
              dict(candidate='new',seed=1,mean_log_rmse=.01),dict(candidate='new',seed=2,mean_log_rmse=.5)]
        self.assertEqual(select_candidate(rows)[0],'legacy')
        with self.assertRaises(ValueError):select_candidate(rows[:-1])
        with self.assertRaises(ValueError):select_candidate(rows+[rows[0]])

    def test_small_selection_persists_artifacts_without_audit_inputs(self):
        rng=np.random.default_rng(7);x=rng.poisson(1,size=(40,5));d=np.full(40,30)
        cfg=dict(normalization=100,mc_cells_per_batch=12,mc_seed=4,learning_rate=.5,maximum_step=.25,
                 maximum_offset=4,evaluation_cells_per_batch=8,evaluation_seeds=[8,9],
                 candidates=[dict(name='legacy',iterations=0),dict(name='calibrated',iterations=4)])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            result=evaluate_candidates(x[:20],d[:20],np.repeat(['a','b'],10),x[20:],d[20:],cfg,path,path)
            saved=json.loads((path/'frozen_selection.json').read_text())
            self.assertEqual(saved,result)
            self.assertEqual(len(saved['calibration_rows']),4)
            self.assertEqual(len(list(path.glob('*_seed_*.npz'))),4)

    def test_identical_distributions_and_bad_axis(self):
        x=np.array([[1,2],[3,0],[1,1]]);d=np.full(3,6)
        self.assertEqual(distribution_metrics(x,d,x,d,100),dict(mean_log_rmse=0.,variance_log_rmse=0.,dropout_mae=0.))
        with self.assertRaises(ValueError):distribution_metrics(x,d,x[:,:1],d,100)
        with self.assertRaises(ValueError):distribution_metrics(x,[0,0,0],x,d,100)


if __name__=='__main__':unittest.main()
