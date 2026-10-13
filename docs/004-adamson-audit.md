# Adamson audit: keep separate pending provenance gates

GSE90546 contains three K562 CRISPRi expression panels, not one interchangeable
training dataset. The [authors' analysis notebook](https://github.com/thomasmaxwellnorman/perturbseq_demo/blob/master/perturbseq_demo.ipynb)
identifies the epistasis panel's single/double/triple perturbations and three
chemical conditions: DMSO, tunicamycin and thapsigargin. Exclude this panel from
the initial single-target transfer task.

Experiment 004 downloads the identity, expression-barcode and gene-axis metadata
for each panel directly from NCBI GEO and records SHA-256 hashes. Conservative
assignment filtering requires good guide coverage, exactly one assigned cell,
a unique barcode assignment and a barcode present in the expression matrix.
This leaves 5,321 pilot, 13,503 epistasis and 50,467 UPR assignments. These are
metadata eligibility counts, not expression-QC-passing training cells.

UPR controls `63(mod)_pBA580` and `Gal4-4(mod)_pBA582` remain **candidates**. Their
names and abundance alone are insufficient to establish negative-control status.
Confirm the primary guide table and UPR conditions/time before reading its
expression matrix, checking integer counts, deriving RNA library sizes, resolving
gene IDs and computing deltas within matched dataset/condition/gem strata.
The identity CSV's UMI count is guide capture support, not RNA library size.

Decision: no Adamson rows enter experiments 002, 003 or 005. Keep dataset identity
and assay type explicit in any later pooling ablation. Norman CRISPRa stays
excluded. The full machine-readable audit, including candidate control support
per gem, is in `results/004_adamson_audit/audit.json`.

Reproduce with `python -m src.data.adamson_audit --config config/004_adamson_audit.yaml`.
