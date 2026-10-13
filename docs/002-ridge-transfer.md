# Experiment 002: one-feature K562 → RPE1 transfer

Run `make transfer` after restoring experiment 001's six Parquet files. Input
SHA-256 hashes must match the committed experiment 001 manifest. In CloudShell,
`timeout 2400 python3 scripts/run-transfer-cloud.py` runs all tests, executes the
experiment (30-minute subprocess limit), and backs up reports, model coefficients,
predictions and configuration with streaming S3 checksum verification. No EC2 is
needed. The scientific subprocess uses the pinned `.venv`; system Python needs
boto3 and the existing CloudShell AWS session.

Each target is one equally weighted training example; each output gene has its
own slope/intercept. The only feature is the target gene's mean log1p-CP10k
expression in its line's non-targeting controls. Missing features use the median
of observed K562 training-target features. Imputation, centering and scaling are
refit inside each of five shuffled, seeded K562 target folds. Select one global
alpha by held-out mean squared error across targets and output genes, breaking
exact ties toward stronger regularization. No RPE1 perturbation values enter
fitting, preprocessing or alpha selection. Persist `frozen_model.json` and
predictions before reading held-out perturbation values.

The output axis is the 7,226 genes measured in both lines, determined from
control metadata. All mapped targets remain eligible, including targets with
few cells or missing basal features. Three RPE1 targets without Ensembl IDs
remain preserved in experiment 001 but are excluded from this gene-ID-based
experiment. Duplicate mapped target/output pairs cause a failure rather than an
implicit merge. This experiment does not weight targets by cell count.

Compare four models on identical all-mapped, shared-target and unseen-target
cohorts:

- Zero delta.
- K562 mean perturbation response, the same vector for every held-out target.
- One-feature ridge with an unpenalized intercept.
- Nearest-line transfer: K562 is the sole training line, so copy its same-target
  response where available; use the K562 mean response for unseen targets. This
  does not perform a meaningful line-neighbor search with only one training line.

MSE and MAE average over target/output pairs on log1p-CP10k deltas. Pearson is
calculated across output genes per target, then averaged over targets with a
nonzero denominator; undefined correlations are omitted and their count is
reported. Zero-delta correlation is undefined, not zero. MSE relative to zero
is a diagnostic ratio, not the challenge's reference scaling.

These are descriptive public-data transfer diagnostics, **not the six official
VCC metrics or a leaderboard score**. The mean expression response alone cannot
validate single-cell variance or differential-expression calibration. K562 and
RPE1 differ in biological context and sampling time; this pair does not guarantee
transfer to anonymous challenge contexts. RPE1 is now an evaluation set: subsequent
model changes should be chosen on K562 validation, with any repeated RPE1 use
disclosed. Add more held-out contexts before claiming broad zero-shot performance.
