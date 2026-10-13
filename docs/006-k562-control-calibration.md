# K562 control-only count-generator calibration

Status: implemented and locally tested; the real K562 experiment has NOT run.
No empirical winner, K562 score, or new submission is claimed. Browser-control
tools were unavailable for this turn and the local AWS CLI had no credentials.

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

## Verification and next gate

Ten targeted tests passed locally: the three existing adapter tests plus seven new
numerical/split/selection tests. These used the available local Python 3.12.14 and
NumPy 2.3.5, not the pinned cloud scientific environment. The full pinned-environment
suite and real-file integration remain cloud-run gates. Syntax and whitespace
checks passed. A generated-data test confirms correction reduces mean error on
independent synthetic draws; that is not evidence of improvement on K562.

After this batch, inspect the frozen winner and all audit diagnostics. A setting
selected here is provisional: test fixed response models with K562 perturbation
folds (basis, priors and predictions fitted without fold targets) before freezing
the final count adapter. Do not infer transfer or DE quality from a null-only test,
or retune from the repeatedly inspected RPE1 panel.
