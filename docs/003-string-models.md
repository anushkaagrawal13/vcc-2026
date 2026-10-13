# Experiment 003: predeclared STRING feature comparison

This experiment is specified before re-reading RPE1 outcomes. It uses the same
K562 targets, RPE1 cohorts, gene axis and log1p-CP10k delta labels as experiment
002. RPE1 has already been evaluated once; this is repeated holdout use, not a
fresh untouched test set. No settings are chosen using RPE1 metrics.

Pinned human STRING v12.0 sources are the aliases and functional-links files,
CC BY 4.0, from https://version-12-0.string-db.org/cgi/download?species_text=Homo+sapiens.
The source URLs and expected byte lengths are in `config/003_string_models.yaml`.
Compute and retain SHA-256 receipts (not publisher-supplied checksums), and back
up the exact sources. Match exact Ensembl gene aliases only; discard ambiguous
protein-to-gene mappings. Merge protein isoform edges by maximum confidence,
remove self edges, make links symmetric, and retain combined scores >=700.
These are functional associations, not necessarily physical or causal effects.

Features: the target's control-only basal expression, a missingness indicator,
log(1 + number of measured training-fold neighbors), and weighted mean response
components among those neighbors. The graph is fixed external metadata; response
priors use only the current training fold. A target's own label is excluded even
for training rows. No neighbors gives the training response mean (zero centered
components). RPE1 controls can supply its basal-expression covariate; its
perturbation outcomes cannot supply priors. K562 is the only training line, so a
training-line mean expression duplicates the K562 basal feature and is not added
as a spurious independent covariate. Adamson integration is a separate data audit.

To bound CPU cost, ridge and LightGBM predict 16 components of the centered
response matrix, then reconstruct deltas across all 7,226 output genes. This is
an explicit low-rank model, not 7,226 independent tree ensembles. Fit the response
basis inside each training fold with seeded randomized SVD (8 oversampling
columns, two power iterations); fit again on all K562 only after selection.

Use five target folds with seed 2026, exactly the split rule from experiment 002.
Compare training mean, basal-only low-rank ridge, STRING low-rank ridge, and
STRING low-rank LightGBM. Ridge alpha candidates: 1, 100, 1000. Tree leaf counts:
7, 15; 60 rounds, learning rate 0.05, minimum leaf data 40, one CPU thread, fixed
seed, deterministic mode. Fit imputation and standardization on training folds
only. Choose each family's setting and the overall winner by pooled K562
out-of-fold MSE. No RPE1 early stopping or selection. CV estimates used to select
settings are selection estimates, not an unbiased final generalization score.

Persist fold IDs, selections, fitted basis/models and every selected prediction
before loading RPE1 labels. Report every predeclared family on shared, unseen and
all-mapped cohorts, along with zero delta, even if it performs poorly. Compare
MSE, MAE and per-target Pearson using experiment 002 definitions. These remain
pseudobulk diagnostics, not the six official challenge metrics. Low-rank
compression can limit fidelity, especially for sparse target-specific effects.

Execution: `timeout 2400 python3 scripts/run-rich-cloud.py` in the existing
CloudShell checkout with restored experiment 001 files. All tests must pass.
Scientific computation has a 30-minute limit; no EC2 is launched. Back up reports,
model state, predictions, exact STRING inputs, graph and config immediately,
streaming each S3 object back to verify SHA-256. Retained objects incur storage
charges. LightGBM is pinned to 4.6.0 in both environment manifests.
