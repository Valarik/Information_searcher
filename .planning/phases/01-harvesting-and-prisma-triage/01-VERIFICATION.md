---
phase: 01-harvesting-and-prisma-triage
verified: 2026-11-04T17:17:00+03:00
status: passed
score: 9/9 must-haves verified
---

# Phase 1: Harvesting & PRISMA Triage — Verification Report

**Phase Goal:** Собрать полный корпус публикаций и клинических исследований по контрактуре Дюпюитрена (2016–2026), дедуплицировать записи и стратифицировать их по уровню доказательности и кластерам.
**Verified:** 2026-11-04
**Status:** passed

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `src/harvester.py` queries PubMed, Europe PMC, OpenAlex, and ClinicalTrials.gov for 2016–2026 Dupuytren literature without API keys (`D-08`) | ✓ VERIFIED | Raw files saved in `data/dupuytren/raw/`: PubMed (1,132), Europe PMC (537), OpenAlex (1,694), ClinicalTrials.gov (80) |
| 2 | Cascade deduplication (`PMID -> DOI -> normalized title`) merges records into `data/dupuytren/literature.db` without duplicate PMIDs or DOIs | ✓ VERIFIED | 3,363 raw records deduplicated to 2,209 unique rows in `articles`; `UNIQUE` constraints enforced on `pmid` and `doi` |
| 3 | Preprints (2023–2026) are merged into journal versions if published, or kept with `is_preprint = 1` and `[Preprint]` tag (`D-02`) | ✓ VERIFIED | 144 included preprints tagged with `is_preprint = 1` and `[Preprint]` in `pub_types` |
| 4 | ClinicalTrials.gov studies for Dupuytren contracture are stored in `clinical_trials` with NCT ID, phase, status, interventions, and outcomes | ✓ VERIFIED | 80 clinical trials imported into `clinical_trials` table (44 `COMPLETED`, 12 `RECRUITING`, 7 `NOT_YET_RECRUITING`, 3 `ACTIVE_NOT_RECRUITING`) |
| 5 | `src/triage.py` filters out eponymous Dupuytren ankle/fibular fractures (`D-04`), isolated Peyronie/Ledderhose studies (`D-03`), and foreign articles lacking EN/RU abstracts (`D-01`) | ✓ VERIFIED | 434 records excluded (`excluded_ankle_fracture`: 8, `excluded_isolated_peyronie_ledderhose`: 16, `excluded_foreign_no_abstract`: 115, `excluded_offtopic`/`out_of_date_range`: 295) |
| 6 | Included articles are stratified into `Tier 1–4` (`D-05`, `D-06`), with narrative reviews separated from systematic reviews/meta-analyses into `Tier 3` (`Narrative Review [D-06]`) | ✓ VERIFIED | 1,775 included articles stratified into `Tier 1` (181), `Tier 2` (192), `Tier 3` (942, including 133 narrative reviews), and `Tier 4` (460, including 23 rare complication cases) |
| 7 | Included articles are tagged across the 5 clusters (`etiology`, `pathogenesis`, `conservative`, `surgical`, `outcomes`) | ✓ VERIFIED | `etiology`: 433, `pathogenesis`: 649, `conservative`: 683, `surgical`: 526, `outcomes`: 769 |
| 8 | Open-access full-text XMLs are downloaded from Europe PMC for `Tier 1–3` articles (`D-07`) and linked via `has_fulltext_xml = 1` | ✓ VERIFIED | 233 full-text XML files saved in `data/dupuytren/raw/fulltext_xml/` (`Tier 1`: 59, `Tier 2`: 47, `Tier 3`: 127; `Tier 4`: 0) |
| 9 | `reports/dupuytren/prisma_stats.md` presents the complete PRISMA flow diagram, breakdown by source, exclusion reasons, year (2016–2026), evidence tier (`Tier 1–4`), and 5 clusters | ✓ VERIFIED | `reports/dupuytren/prisma_stats.md` generated and verified |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| `HARV-01`: Multi-source literature harvesting (PubMed, Europe PMC, OpenAlex, ClinicalTrials.gov) | ✓ SATISFIED | — |
| `HARV-02`: Cascade deduplication (`PMID -> DOI -> normalized Title`) | ✓ SATISFIED | — |
| `HARV-03`: PRISMA screening, `Tier 1–4` hierarchy, and 5-cluster tagging | ✓ SATISFIED | — |
| `HARV-04`: Open-access Full-Text XML download for `Tier 1–3` | ✓ SATISFIED | — |
