"""Session 2 boundary; deliberately unimplemented until schema round-trip.

Input: counts + dataset, assay_type, line, batch, guide, target_gene metadata.
Match controls within dataset/line/batch/assay BEFORE aggregation. Retain cell
counts, guide support, expression units and control keys in a tidy Parquet table.
Key: (dataset, assay_type, line, target_gene, output_gene); value: mean delta.
Retain original single cells: pseudobulk alone cannot reproduce the DE rubric.
"""
