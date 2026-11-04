---
phase: 02-swarm-structured-extraction
verified: 2026-11-04T18:21:00+03:00
status: passed
score: 10/10 must-haves verified
---

# Phase 2: Swarm Structured Extraction — Verification Report

**Phase Goal:** Параллельное извлечение структурированных биомедицинских и клинических данных из аннотаций и полных текстов по 4 аналитическим кластерам (этиология/генетика, патогенез, консервативное/инъекционное лечение, хирургия и отдаленные исходы).
**Verified:** 2026-11-04
**Status:** passed

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `src/extractor_common.py` provides WAL SQLite access, JATS XML `<sec>`/`<table-wrap>` parsing, JSON author formatting, sample-size/statistical-metrics regex, and joint-stratified (`MCP`/`PIP`) + recurrence-definition extraction | ✓ VERIFIED | `src/extractor_common.py` implemented and imported across all 4 cluster extractors |
| 2 | `src/extract_cluster_1.py` populates `extracted_mechanisms` across all 7 Cluster 1 categories (`Epidemiology & Prevalence`, `Genetics & GWAS`, `Wnt Signaling Genetics`, `Metabolic & Lifestyle Risk Factors`, `Occupational & Vibration Exposure`, `Dupuytren Diathesis & Associated Fibromatoses`, `Epigenetics & Non-coding RNA`) while excluding `Narrative Review [D-06]` | ✓ VERIFIED | **484 rows** inserted across all 7 Cluster 1 categories (`--verify` passed) |
| 3 | `data/dupuytren/extractions/cluster_1_etiology_genetics.md` synthesizes 2016–2026 findings on global prevalence, 61–85 GWAS loci, Neandertal `EPDR1` introgression, Wnt signaling, diabetes/alcohol/smoking/inverse BMI, vibration/HAVS, and diathesis with 100% verified `[PMID: ...]` citations | ✓ VERIFIED | `cluster_1_etiology_genetics.md` (29,744 bytes, 27 unique PMIDs, 0 missing from `literature.db`) |
| 4 | `src/extract_cluster_2.py` populates `extracted_mechanisms` across all 6 Cluster 2 categories (`Myofibroblast Biology & Cellular Origin`, `TGF-beta / Smad Canonical & Non-canonical Signaling`, `Mechanotransduction & YAP/TAZ`, `Immune Microenvironment, Macrophages & TNF`, `Extracellular Matrix, Collagen III/I & MMPs/TIMPs`, `Single-Cell & Spatial Multi-Omics`) | ✓ VERIFIED | **578 rows** inserted across all 6 Cluster 2 categories (total `extracted_mechanisms` = **1,062 rows**, `--verify` passed) |
| 5 | `data/dupuytren/extractions/cluster_2_pathogenesis.md` synthesizes scRNA-seq/CyTOF atlases (`ICAM1+`, `PDPN+/CD82+`, pericytes, `TPPP3+`), `TNF-α/TNFR2/IL-33` vs autonomous Collagen I homotrimer `α1(I)₃`, `TGF-β1/Smad` & pirfenidone, and `YAP/TAZ` mechanotransduction | ✓ VERIFIED | `cluster_2_pathogenesis.md` (24,628 bytes, 15 unique PMIDs, 0 missing from `literature.db`) |
| 6 | `src/extract_cluster_3.py` populates `extracted_clinical_evidence` across all 6 `[Cluster3]` conservative & minimally invasive intervention groups with separate `mcp_outcome`, `pip_outcome`, and `recurrence_definition` (`D-02`, `D-03`) | ✓ VERIFIED | **481 rows** inserted across all 6 `[Cluster3]` groups (`--verify` passed) |
| 7 | `data/dupuytren/extractions/cluster_3_conservative_minimally_invasive.md` evaluates `CCH` (`DISC`, `DETECT`, post-2020 EU withdrawal), `PNF +/- steroids`, Adalimumab (`RIDD`), Radiotherapy (`DEPART`), `ESWT`, night splinting RCTs, and cross-links all 80 `ClinicalTrials.gov` studies (`NCT ID <-> PMID`) | ✓ VERIFIED | `cluster_3_conservative_minimally_invasive.md` (28,686 bytes, 25 unique PMIDs, 0 missing from `literature.db`) |
| 8 | `src/extract_cluster_4.py` populates `extracted_clinical_evidence` across all 8 `[Cluster4]` surgical & long-term outcome groups, keeping all 23 `Tier 4` rare complication cases isolated under `[Cluster4] Rare Severe Complication [D-05]` | ✓ VERIFIED | **732 rows** inserted across all 8 `[Cluster4]` groups, including exactly 23 `[Cluster4] Rare Severe Complication [D-05]` rows (total `extracted_clinical_evidence` = **1,213 rows**, `--verify` passed) |
| 9 | `data/dupuytren/extractions/cluster_4_surgical_and_outcomes.md` synthesizes `LF`, `DF + FTSG`, `McCash`, `WALANT`, `PALF`, `Digit Widget`, the 1–3–5–10 yr `MCP` vs `PIP` recurrence matrix by definition (`≥20° Kan` vs `≥30°` vs `re-intervention`), PROMs (`URAM`/`DASH`/`PEM`), and the isolated 23-case `D-05` complication registry | ✓ VERIFIED | `cluster_4_surgical_and_outcomes.md` (30,893 bytes, 29 unique PMIDs, 0 missing from `literature.db`) |
| 10 | Zero orphan `article_id` references exist in `extracted_mechanisms` or `extracted_clinical_evidence`, and all Russian prose strictly follows `ru-medical-humanizer` | ✓ VERIFIED | `0` orphan rows in both SQLite tables; all 4 dossiers verified |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| `EXTR-01`: Structured extraction for Cluster 1 (Etiology, Epidemiology, Genetics, Risk Factors) | ✓ SATISFIED | — |
| `EXTR-02`: Structured extraction for Cluster 2 (Molecular & Cellular Pathogenesis) | ✓ SATISFIED | — |
| `EXTR-03`: Structured extraction for Cluster 3 (Conservative & Minimally Invasive Treatments + ClinicalTrials.gov) | ✓ SATISFIED | — |
| `EXTR-04`: Structured extraction for Cluster 4 (Surgical Treatments, Complications & Long-Term Outcomes/Recurrence) | ✓ SATISFIED | — |
