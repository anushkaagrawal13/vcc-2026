"""Session 2/3 boundary; do not fit features using held-out perturbation outcomes.

Start with target-gene basal expression from target-line controls. Then add
target-gene mean expression across TRAINING lines and GO/STRING neighbor deltas
fit on TRAINING lines only. Version gene identifiers, graph release and units.
Target-line control profiles are allowed covariates; its perturbations are labels.
Norman 2019 is excluded (CRISPRa); adding it requires a separate task/assay model.
"""
import numpy as np


def neighbor_features(weights, query_ids, reference_ids, reference_scores, basal):
    """Only reference-fold labels allowed; exclude self even for training queries."""
    w=np.asarray(weights,dtype=float).copy()
    if w.shape!=(len(query_ids),len(reference_ids)) or len(reference_scores)!=len(reference_ids):
        raise ValueError('Neighbor axes disagree')
    w[np.equal.outer(query_ids,reference_ids)]=0
    support=(w>0).sum(axis=1)
    total=w.sum(axis=1)
    prior=w@reference_scores/np.maximum(total,1e-30)[:,None]
    # Centered reference scores => no neighbors means the training response mean.
    return np.column_stack([basal,~np.isfinite(basal),np.log1p(support),prior])


def standardize_fit(x):
    med=np.array([np.median(v[np.isfinite(v)]) if np.isfinite(v).any() else 0. for v in x.T])
    filled=np.where(np.isfinite(x),x,med)
    mean=filled.mean(axis=0);scale=filled.std(axis=0);scale[scale==0]=1.
    return dict(median=med,mean=mean,scale=scale)


def standardize(x,state):
    return (np.where(np.isfinite(x),x,state['median'])-state['mean'])/state['scale']
