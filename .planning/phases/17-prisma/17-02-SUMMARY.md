---
phase: 17-prisma
plan: 02
subsystem: ingestion-and-triage
tags: [pubmed, europepmc, prisma, sqlite, complications, fulltext-xml, security]

# Dependency graph
requires:
  - phase: 17-prisma
    provides: SQLite articles schema and PEP 723 harvester/triage runtime
provides:
  - Treatment profile resolver (`resolve_treatment_profile`) defaulting to surgical/mixed with conservative CTCAE/adverse-events switch (COMP-01, D-01)
  - Hybrid complication query builder (`build_complications_queries` / `resolve_complications_queries`) honoring explicit YAML `complications_queries` or auto-generating date-bounded PubMed & Europe PMC queries (D-02)
  - Cached complication harvesting passes (`harvest_pubmed_complications`, `harvest_europepmc_complications`) writing fixed `pubmed_complications.json` and `europepmc_complications.json` and deduplicating via `upsert_article()` with `PubMed:Complications` / `EuropePMC:Complications` provenance (D-03)
  - Combined 3-signal `complications_safety` cluster tagging (`should_tag_complications_safety`, `assign_clusters`) and complication-aware PRISMA context matching (`classify_prisma_status`) (COMP-02, D-05)
  - Two-contour `N >= 20` cohort vs `Tier 4` / `1 <= N < 20` `rare_catastrophic_case` casuistry separation in `classify_evidence_tier()` with basic-science exemption (D-04)
  - Priority Europe PMC Full-Text XML download queue favoring `Tier 1-3` `complications_safety` articles while enforcing `PMCID_RE` path-traversal protection (D-06, T-17-04)
  - PRISMA report accounting for complication raw caches (`total_raw`, `duplicates_removed`) and mandatory `complications_safety` cluster statistics row (COMP-02)
affects: [17-03, 18-humanizer, 19-ui-export]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dual-level YAML metadata lookup (`cfg.get(k) or cfg.get('nosology', {}).get(k)`)"
    - "Fixed-filename raw JSON caching (`pubmed_complications.json`, `europepmc_complications.json`) isolated from `europepmc_page_*.json`"
    - "Two-contour evidence separation (`Tier 1-3` `N >= 20` vs `Tier 4` `rare_catastrophic_case`)"
    - "SQL CASE priority ordering in Europe PMC Full-Text XML queue with `PMCID_RE` pre-slice validation"

key-files:
  created: []
  modified:
    - src/harvester.py
    - src/triage.py

key-decisions:
  - "Defaulted treatment profile to `surgical` for surgical/mixed/unspecified configs and switched to `conservative` CTCAE/adverse-effects block only when `surgical_focus: false` or `treatment_profile: conservative` is explicitly set (D-01)."
  - "Cached PubMed and Europe PMC complication passes into dedicated fixed files (`pubmed_complications.json`, `europepmc_complications.json`) and merged `:Complications` provenance via existing `upsert_article()` (D-03, T-17-03)."
  - "Pre-filtered invalid PMCIDs with `PMCID_RE` before slicing `[:max_downloads]` in `download_fulltexts_tier1_to_3()` in addition to retaining the path-construction guard so malformed PMCIDs cannot starve legitimate `complications_safety` XML slots (T-17-04)."

patterns-established:
  - "Hybrid safety query resolution: explicit `complications_queries` overrides auto-generated MeSH/tiab + safety block within `date_range`."
  - "Three-signal safety cluster tagging (`:Complications` provenance OR built-in surgical/conservative/rare vocabularies OR YAML `complication_terms`/`rare_complication_terms`)."
  - "PRISMA `total_raw` reconciliation incorporating `pubmed_complications.json` and `europepmc_complications.json`."

requirements-completed: [COMP-01, COMP-02]

# Metrics
duration: 9 min
completed: 2026-11-19
---

# Phase 17 Plan 02: Targeted Complications Harvesting & Two-Contour PRISMA Safety Triage Summary

**Hybrid surgical/conservative complication harvesting (`PubMed:Complications` & `EuropePMC:Complications`) in `src/harvester.py` paired with two-contour `N >= 20` vs `Tier 4` `rare_catastrophic_case` PRISMA triage, 3-signal `complications_safety` tagging, and prioritized Europe PMC Full-Text XML queuing in `src/triage.py`.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-11-19T16:34:18Z
- **Completed:** 2026-11-19T16:43:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Implemented `resolve_treatment_profile()`, `build_complications_queries()` (`resolve_complications_queries` alias), `harvest_pubmed_complications()`, and `harvest_europepmc_complications()` in `src/harvester.py` with dedicated fixed-name JSON caches (`pubmed_complications.json`, `europepmc_complications.json`), `upsert_article()` provenance merging (`PubMed:Complications`, `EuropePMC:Complications`), dual-level YAML lookup, and summary reporting in `main()`.
- Implemented `should_tag_complications_safety()`, universal surgical/conservative safety vocabularies, complication-aware `classify_prisma_status()`, two-contour `1 <= N < 20` / `Tier 4` `rare_catastrophic_case` separation in `classify_evidence_tier()` (with basic-science exemption), prioritized `download_fulltexts_tier1_to_3()` (`Tier 1-3` `complications_safety` ahead of general `Tier 1-3` while preserving `PMCID_RE` + `b"<article"` validation), and updated `generate_prisma_report()` / `main()` in `src/triage.py`.
- Verified all automated assertions, mocked caching/deduplication, XML priority ordering, path-traversal blocking, and zero modifications to frozen `v1.x` corpora (`data/`, `reports/`).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add surgical_focus profile resolver, hybrid complication query builder, and cached complication passes in harvester.py** - `56ca9ab` (feat)
2. **Task 2: Add complications_safety cluster tagging, two-contour N<20 casuistry separation, priority XML queue, and PRISMA stats in triage.py** - `6503114` (feat)

## Files Created/Modified
- `src/harvester.py` - Added 4 safety query blocks (`SURGICAL_*`, `CONSERVATIVE_*`), `resolve_treatment_profile()`, `build_complications_queries()` / `resolve_complications_queries`, `harvest_pubmed_complications()`, `harvest_europepmc_complications()`, and integrated passes [5/6]–[6/6] into `main()`.
- `src/triage.py` - Added `UNIVERSAL_SURGICAL_COMPLICATION_TERMS`, `UNIVERSAL_CONSERVATIVE_ADVERSE_TERMS`, `should_tag_complications_safety()`, `_extract_clinical_sample_size()`, `_is_basic_science_study()`, `_has_epmc_source()`, updated `classify_prisma_status()`, `classify_evidence_tier()`, `assign_clusters()`, `download_fulltexts_tier1_to_3()`, `generate_prisma_report()`, and `main()`.

## Decisions Made
- Pre-filtered invalid PMCIDs against `PMCID_RE` before slicing `[:max_downloads]` in `download_fulltexts_tier1_to_3()` (while retaining the explicit `PMCID_RE` guard before constructing `fulltext_dir / f"{pmcid}.xml"`), preventing malformed PMCID records from consuming download quota slots.
- Added fallback support for `explicit.get("max_results")` alongside `pubmed_max_results` / `europepmc_max_results` in `build_complications_queries()` (defaults remain `800` and `1000`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Pre-slice `PMCID_RE` validation in `download_fulltexts_tier1_to_3()`**
- **Found during:** Task 2 (`src/triage.py` priority XML queue verification)
- **Issue:** When a malicious/malformed PMCID (e.g. `../evil`) ranked high in SQL `ORDER BY`, slicing `candidates = (epmc_rows + other_pmc_rows)[:max_downloads]` before filtering `PMCID_RE` allowed the invalid row to consume a `max_downloads` slot before being skipped.
- **Fix:** Added `PMCID_RE.match()` filtering while partitioning `epmc_rows`/`other_pmc_rows` in addition to keeping the explicit `PMCID_RE.match()` guard before file path construction (`T-17-04`).
- **Files modified:** `src/triage.py`
- **Verification:** Offline mock test with `max_downloads=1`, malformed `../evil` (Tier 1, cited=999), and valid `PMC22222` (Tier 3, `complications_safety`) fetched `PMC22222` cleanly and never touched `../evil`.
- **Committed in:** `6503114` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical security/quota hardening)
**Impact on plan:** Hardens `T-17-04` mitigation without changing public interfaces or scope.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `src/harvester.py` (`COMP-01`) and `src/triage.py` (`COMP-02`) are ready for Wave 2 integration and comprehensive pytest coverage in Plan `17-03` (`tests/test_phase17_complications.py`).
- Frozen `v1.x` directories (`data/prom`, `data/metroplasty_pregnancy`, `data/trigger_finger`, `reports/`) remain completely untouched.

## Self-Check: PASSED

- Verified modified files exist on disk: `src/harvester.py` (FOUND), `src/triage.py` (FOUND).
- Verified task commits exist in git history: `56ca9ab` (FOUND), `6503114` (FOUND).
- Verified all `<verify><automated>` checks and extended offline caching/dedup/priority/traversal checks passed (`ALL 17-02 CHECKS PASSED`).
- Verified stub scan (`TODO|FIXME|placeholder|coming soon`) returned zero matches in `src/harvester.py` and `src/triage.py`.
- Verified `git status --short data/ reports/` returned empty output and `.planning/STATE.md` / `.planning/ROADMAP.md` were not modified by this executor.

---
*Phase: 17-prisma*
*Completed: 2026-11-19*
