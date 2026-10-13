# Bounded raw-count rehearsal

Experiment 005 freezes the experiment 003 LightGBM predictions and compares
zero-delta, K562 training-mean and LightGBM responses using the same count adapter.
Three shared and three unseen RPE1 targets are selected by ascending SHA-256 of
target IDs among targets with at least 128 observed cells. Selection uses metadata,
never response magnitude. Each has 128 randomly sampled reference/generated cells.
512 RPE1 controls fit the adapter; a disjoint 256 controls are used by the scorer.
The original model's basal features already used the full RPE1 control set.

The adapter samples empirical control profiles, shifts their log1p-CP10k values,
clips negative shifted values to zero, and draws fresh multinomial counts. An
outside-panel bucket accounts for UMI counts outside the 7,226 common genes.
This preserves some empirical control variability but does not identify the true
perturbed distribution. Requested-versus-achieved delta RMSE is reported per
model/target. No generator parameter is fitted or selected using RPE1 outcomes.

`cell-eval2==0.16.0`, the version used in the original contract review, runs the
`vcc2026` preset with the explicitly pinned CPU `pdex==0.3.0` backend. Outputs
include per-target values, native aggregates and metric-specific valid-cohort
sizes. Undefined metrics remain undefined. Generated H5AD files contain no
controls; scorer inputs get the same held-out real controls as the reference.

This is a public-data integration diagnostic, not a challenge submission, scaled
leaderboard score, full RPE1 estimate or an untouched holdout. It uses a small
six-target panel and pooled RPE1 controls without matching gem-group proportions.
Official context-specific baseline/replicate scaling anchors are unavailable.
The challenge gene axis and three-context panel still require a separate adapter.

Run `python -m src.count_rehearsal --config config/005_count_rehearsal.yaml` after
restoring the config's inputs and manifests from the recorded private S3 backups.
On CloudShell, `python3 scripts/run-count-rehearsal-cloud.py` runs tests, limits the
experiment to 45 minutes, and exports outputs with full S3 read-back SHA checks.
No EC2 instance is launched by this runner. A failure exports the log and aborts;
it does not report successful backup or continue to a submission.

## Observed result

| Raw metric | Zero delta | Training mean | LightGBM |
|---|---:|---:|---:|
| PDS cosine ↑ | 0.56667 | 0.53333 | 0.50000 |
| Expression error ↓ | 4.54529 | 4.93668 | 4.78661 |
| DE direction fidelity/yield ↑ | 0.70524 | 0.69566 | 0.69759 |
| DE direction reach ↑ | 0.14152 | 0.18818 | 0.07000 |
| DE Jaccard ↑ | 0.00226 | 0.00412 | 0.00291 |
| DE LFC NMAE ↓ | 0.94046 | 0.93999 | 0.95066 |

The official scorer ran successfully in 107.5 seconds after 34 tests passed.
LightGBM did not improve expression error or PDS over zero delta in this small
panel. DE Jaccard is very low for all models. Direction reach is defined on 5/6
targets and LFC NMAE on 3/6; consult the committed per-metric cohort counts.
Do not interpret these aggregates as six fully observed DE comparisons.

Mean requested-versus-achieved log-delta RMSE was 0.05839 for zero delta,
0.05474 for training mean and 0.05631 for LightGBM. Even the null transport
introduces measurable shift; diagnose resampling noise, clipping, normalization
and control/gem variation on K562 before changing the model. This experiment
does not isolate which of those effects causes the score gap.

Next: calibrate and ablate count-generation on K562 control splits and held-out
K562 perturbation folds. Freeze the adapter there; then perform one broader
predeclared cross-line diagnostic. Do not choose generator settings from this
RPE1 panel. Finish Adamson control/condition provenance before a pooling ablation.
