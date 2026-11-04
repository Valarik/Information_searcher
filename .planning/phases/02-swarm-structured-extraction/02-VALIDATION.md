---
phase: 02
slug: swarm-structured-extraction
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-11-04
---

# Phase 2 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python CLI `--verify` assertions + SQLite relational integrity checks |
| **Config file** | `configs/dupuytren.yaml` |
| **Quick run command** | `uv run src/extract_cluster_1.py --verify && uv run src/extract_cluster_2.py --verify && uv run src/extract_cluster_3.py --verify && uv run src/extract_cluster_4.py --verify` |
| **Estimated runtime** | ~5 seconds (verification mode) |

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Automated Command | Status |
|---------|------|------|-------------|------------|-----------------|-------------------|--------|
| 02-01-01 | 01 | 1 | EXTR-01 | T-02-01 | Parameterized SQL inserts + XML parsing | `uv run src/extract_cluster_1.py --help` | ⬜ pending |
| 02-01-02 | 01 | 1 | EXTR-01 | — | Verified PMID/DOI links in `extracted_mechanisms` & `cluster_1_etiology_genetics.md` | `uv run src/extract_cluster_1.py --verify` | ⬜ pending |
| 02-02-01 | 02 | 1 | EXTR-02 | T-02-01 | Parameterized SQL inserts + XML parsing | `uv run src/extract_cluster_2.py --help` | ⬜ pending |
| 02-02-02 | 02 | 1 | EXTR-02 | — | Verified PMID/DOI links in `extracted_mechanisms` & `cluster_2_pathogenesis.md` | `uv run src/extract_cluster_2.py --verify` | ⬜ pending |
| 02-03-01 | 03 | 1 | EXTR-03 | T-02-02 | Cross-linked NCT IDs and clinical outcomes | `uv run src/extract_cluster_3.py --help` | ⬜ pending |
| 02-03-02 | 03 | 1 | EXTR-03 | — | Verified rows in `extracted_clinical_evidence` & `cluster_3_conservative_minimally_invasive.md` | `uv run src/extract_cluster_3.py --verify` | ⬜ pending |
| 02-04-01 | 04 | 1 | EXTR-04 | T-02-02 | Separate MCP/PIP & recurrence definitions (`D-02`) | `uv run src/extract_cluster_4.py --help` | ⬜ pending |
| 02-04-02 | 04 | 1 | EXTR-04 | — | Verified rows in `extracted_clinical_evidence` & `cluster_4_surgical_and_outcomes.md` | `uv run src/extract_cluster_4.py --verify` | ⬜ pending |
