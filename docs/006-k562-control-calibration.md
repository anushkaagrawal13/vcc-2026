# K562 control-only count-generator calibration

Status: completed in AWS CloudShell on October 13, 2026, using source commit
`3ac2bd967adccbb65f47490bc7dc4d5059c6292f`. The pinned suite passed all 41 tests.
Calibration controls selected `mean_calibrated_16` before audit expression was
read. No perturbation prediction, official score, or new submission is claimed.

## Question and boundaries

Can the count generator reproduce unperturbed cells without introducing a mean
shift? Experiment 005 measured nonzero requested-versus-generated delta RMSE even
for its zero-delta generator. Experiment 006 isolates this null behavior before
spending on another model or treating small RPE1 results as tuning feedback.
It reads only non-targeting K562 expression rows; no perturbation expression rows,
RPE1 files, model predictions, or challenge data are inputs. Existing model
parameters stay fixed. This does not test response prediction or official metrics.

## Predeclared design

Use the exact verified `K562_essential_raw_singlecell_01.h5ad.gz` archive from
experiment 001 (1,963,059,148 bytes; SHA-256 in its committed backup manifest).
Read the full 8,563-gene K562 axis and total RNA library sizes from `obs.UMI_count`.
Within each of 48 gem groups, use a seeded permutation of non-targeting cells:

| Partition | Per gem group | Total | Purpose |
|---|---:|---:|---|
| Fit | 12 | 576 | Control distribution and Monte Carlo correction |
| Calibration | 4 | 192 | Select generator setting |
| Audit | 4 | 192 | Final diagnostic after selection is frozen |

All three partitions are disjoint with equal gem-group proportions. Simulated
cells have the same proportions (four per group), using fresh multinomial draws.
There are three independent generation seeds. This corrects the pooled batch
imbalance limitation of experiment 005 for the null comparison.

Compare the unchanged log-profile transport with 8 and 16 correction iterations.
Each iteration compares simulated mean log1p-CP10k expression to the fit-control
mean plus the requested delta, then applies a damped, bounded offset update.
No observed perturbation outcomes enter this calibration. Negative desired mean
expression is clipped to zero and reported. The outside-panel probability bucket
continues to preserve total-UMI accounting. The generator never simply relabels
real cells as synthetic cells.

Choose minimum mean log-expression RMSE on the calibration controls, averaged
over all three seeds; prefer the unchanged generator on an exact tie. Write
`frozen_selection.json` before reading audit expression. Report all predeclared
candidates on audit controls without changing the frozen choice. Also report
log-expression variance error, dropout error, offset bounds and iteration history.
Mean correction alone does not guarantee correct variance, DE, or gene dependence.
Repeated generated seeds do not constitute independent biological replicates.

## Bounded CloudShell run

Run from the existing authenticated AWS CloudShell session. The launcher preserves
untracked prior result files only when their bytes exactly match the incoming
GitHub version; other collisions or tracked edits abort the update.

```bash
cd /tmp/vcc-modeling && git fetch origin main && git show origin/main:scripts/run-control-calibration-cloud.py > /tmp/vcc-run006.py && python3 /tmp/vcc-run006.py --repo /tmp/vcc-modeling --update
```

The existing `.venv` is required. If CloudShell has discarded it, first rebuild
with `bash scripts/setup.sh`; the launcher stops with that instruction rather than
silently changing the environment. It checks relevant package pins and runs the
full test suite before the experiment. Direct scientific command:

```bash
.venv/bin/python -m src.control_calibration --config config/006_k562_control_calibration.yaml
```

Storage: approximately 1.83 GiB for the compressed raw archive, streamed without
expanding the 10.66 GB H5AD onto disk. Preflight reserves a further 1.5 GiB for
headroom. No other raw archives are downloaded. This dataset was already authorized
and backed up to the user's private S3 bucket.

Time: 45-minute wall-clock cap over update, restore, tests, calculation and artifact
export. On timeout the parent terminates the worker process group and its children.
A separate log-export attempt is capped at another 60 seconds. No EC2 API is called,
no EC2 machine is launched, and there is no EC2 shutdown to arrange. The CloudShell
session remains open; the batch process exits. Do not run this from the Mac's
nearly full disk. The launcher refuses to overwrite an earlier experiment attempt.

Outputs: fit/validation/audit indices, control reference arrays, calibrated offsets,
all generated samples, frozen selection and metrics. Artifacts go to
`public/replogle_2022/006_k562_control_calibration/` in the existing private bucket.
Each is uploaded with AES256 encryption and read back for SHA-256 verification;
a successful final manifest is written only after all checks pass. Failures leave
an identifiable local log and attempt to back it up. Log export failure is reported.
The existing S3 storage/request billing still applies; no new compute product is
provisioned. Retrieve exact metric reports and commit them after execution.

## Observed results

All entries below average the three predeclared generation seeds. Lower is better.
Only calibration mean error determined the frozen choice.

| Generator | Calibration mean-log RMSE | Audit mean-log RMSE | Audit variance-log RMSE | Audit dropout MAE |
|---|---:|---:|---:|---:|
| Legacy | 0.059402 | 0.057217 | 0.075210 | 0.101699 |
| 8 correction iterations | 0.048610 | 0.047399 | 0.065858 | 0.070475 |
| **16 correction iterations (selected)** | **0.046522** | **0.045400** | **0.058507** | **0.061400** |

Against legacy on audit controls, the selected correction reduced mean-log RMSE
20.7%, variance-log RMSE 22.2%, and dropout MAE 39.6%. No offset hit its bound and
no requested mean was negative. All generated counts passed nonnegative-integer
checks. The selected correction still clips a small fraction of shifted donor
log values at zero; exact QC and iteration histories are in the frozen report.

Fit-versus-audit real controls differed by 0.027451 mean-log RMSE, 0.015542
variance-log RMSE and 0.026513 dropout MAE. These describe this finite control
split; they are not a theoretical noise floor. Three generation seeds are not
three independent biological replicates. No perturbed K562 cells or RPE1 files
were read for this experiment, and the official scorer was not run.

The scientific command took 115.1 seconds with 439,209,984 bytes peak RSS
(about 419 MiB); this excludes environment setup, input restore and backup.
All 17 artifacts (11,085,979 bytes) were uploaded with AES256 encryption and fully
read back for SHA-256 verification. The final manifest was completed at
`2026-10-13T23:22:26.375515+00:00` and independently retrieved from S3.
Its SHA-256 is
`4c4b47ddbc7d7c35ca947f3698bacd8af061af8aebd7091d5a5f4f3d02c79a7f`.
No EC2 was launched; a read-only check found no running or pending instances in
us-east-2. The worker exited successfully.

Exact `metrics.json`, `frozen_selection.json` and `backup_manifest.json` are
committed under `results/006_k562_control_calibration/`. The first two were
verified against the final S3 manifest after retrieval. `metrics.csv` is a local
derived summary and `status.json` records completion; neither is part of the
original 17-artifact backup. The runbook above documents the completed procedure;
its overwrite guard prevents rerunning into these existing output directories.

## Verification and next gate

Ten targeted tests passed locally before launch. CloudShell then rebuilt the
pinned environment, verified package versions and ran all **41 tests successfully**
(the launcher's suite took 7.86 seconds). The real-file integration and complete
backup verification also passed. Documentation/results were updated afterward;
no scientific code or candidate-selection settings changed.

The 16-iteration correction is provisional. Next test fixed response models with
K562 perturbation folds (basis, priors and predictions fitted without fold targets),
comparing the selected correction with legacy count generation using official
expression/DE diagnostics. Calibration must use fit controls and requested deltas,
not held-out perturbation outcomes. Freeze the final adapter only after that gate.
Do not infer transfer or DE quality from this null-only test, or retune from the
repeatedly inspected RPE1 panel.
