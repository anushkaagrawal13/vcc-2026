"""One-feature multi-output ridge with train-only preprocessing and an intercept."""
import numpy as np


def fit(x, y, alpha):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.ndim != 1 or y.ndim != 2 or len(x) != len(y) or alpha < 0:
        raise ValueError('Invalid ridge inputs')
    observed = x[np.isfinite(x)]
    if not len(observed) or not np.isfinite(y).all():
        raise ValueError('No observed feature or invalid outcomes')
    median = float(np.median(observed))
    x = np.where(np.isfinite(x), x, median)
    mean, scale = float(x.mean()), float(x.std())
    scale = scale if scale > 0 else 1.0
    z = (x-mean)/scale
    intercept = y.mean(axis=0)
    denominator = float(z @ z + alpha)
    slope = z @ (y-intercept) / denominator if denominator else np.zeros(y.shape[1])
    return dict(median=median, mean=mean, scale=scale, intercept=intercept, slope=slope, alpha=alpha)


def predict(model, x):
    x = np.asarray(x, dtype=float)
    z = (np.where(np.isfinite(x), x, model['median'])-model['mean'])/model['scale']
    return model['intercept'][None, :] + z[:, None]*model['slope'][None, :]


def select_alpha(x, y, alphas, folds=5, seed=2026):
    """Target-level folds; every fold fits its own imputer and standardizer."""
    if not 2 <= folds <= len(x):
        raise ValueError('Invalid fold count')
    groups = np.array_split(np.random.default_rng(seed).permutation(len(x)), folds)
    scores = []
    for alpha in alphas:
        errors = []
        for valid in groups:
            train = np.setdiff1d(np.arange(len(x)), valid)
            model = fit(x[train], y[train], alpha)
            errors.append(float(np.square(predict(model, x[valid])-y[valid]).sum()))
        scores.append(dict(alpha=float(alpha), mse=sum(errors)/y.size))
    chosen = min(scores, key=lambda row: (row['mse'], -row['alpha']))['alpha']
    return chosen, scores, groups
