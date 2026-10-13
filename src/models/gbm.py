"""Single-thread LightGBM per training-only response component."""
import lightgbm as lgb
import numpy as np


def fit_components(x,z,leaves,cfg):
    params=dict(objective='regression',metric='l2',learning_rate=cfg['gbm_learning_rate'],
                num_leaves=leaves,min_data_in_leaf=cfg['gbm_min_data'],verbosity=-1,
                num_threads=1,seed=cfg['seed'],deterministic=True,force_col_wise=True)
    return [lgb.train(params,lgb.Dataset(x,label=z[:,j]),num_boost_round=cfg['gbm_rounds']) for j in range(z.shape[1])]


def predict_components(models,x):
    return np.column_stack([m.predict(x,num_threads=1) for m in models])
