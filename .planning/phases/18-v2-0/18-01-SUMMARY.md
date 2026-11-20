---
phase: 18-v2-0
plan: 01
subsystem: skills-and-schema
tags: [humanizer-v2, clinical-decision-nuances, universal-schema, skills, backward-compatibility]

# Dependency graph
requires:
  - phase: 17-v2-0
    provides: "extracted_complications SQLite schema, validate_kb_complications_v2(), and read-only v1.x compatibility layer in src/universal_schema.py"
provides:
  - "ru-medical-humanizer v2.0 skill with non-linear clinical conclusion architecture, workhorse modalities vs gray zones/salvage niches, expanded banned AI cliché catalog, and bold_lead_bullet_ratio <= 0.35 prose budget"
  - "nosology-research-pipeline v2.0 skill documenting surgical_focus, complications_queries, complications_safety, extracted_complications, frequent_complications, rare_critical_red_flags, and clinical_decision_nuances"
  - "validate_kb_clinical_nuances_v2(), validate_kb_v2(), and clinical_decision_nuances schema constants & in-memory v1.x fallback in src/universal_schema.py"
affects: [18-02, 19-v2-0, verify-reports, app-ui, docx-exporter]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Combined v2.0 KB validation via validate_kb_v2() = validate_kb_complications_v2() + validate_kb_clinical_nuances_v2()"
    - "Strict T-18-01 validation: non-empty strings, >=2 case-insensitively distinct competing_modalities, non-null/non-blank/non-bool evidence_pmids"
    - "T-18-02 in-memory clinical_decision_nuances normalization for v1.x bundles without mutating frozen disk files or masking malformed v2.0 sub-objects"

key-files:
  created: []
  modified:
    - .agent/skills/ru-medical-humanizer/SKILL.md
    - .agent/skills/nosology-research-pipeline/SKILL.md
    - src/universal_schema.py

key-decisions:
  - "Preserve validate_kb_complications_v2() signature and semantics intact while introducing validate_kb_clinical_nuances_v2() and composite validate_kb_v2() so Phase 17 tests remain 100% untouched and green."
  - "Restrict in-memory sub-key normalization in load_nosology_bundle() to missing clinical_decision_nuances or non-2.0 bundles so malformed v2.0 sub-objects (e.g., missing strict_niche_or_salvage_indications) are never masked from verify_universal_schema(..., schema_version='v2')."
  - "Enforce strict all-elements evidence_pmids checks (rejecting None, empty strings, bools, and mixed [valid, None] arrays) alongside >= 2 case-insensitively distinct competing_modalities."

patterns-established:
  - "clinical_decision_nuances v2.0 contract: universal_workhorse_modalities (>=1), overlapping_indications_and_gray_zones (>=1, >=2 distinct competing_modalities), strict_niche_or_salvage_indications (>=0 validated entries)."
  - "Non-linear surgical/clinical synthesis standard banning stage-pigeonhole conclusions and enforcing bold_lead_bullet_ratio <= 0.35 in dissertation reports."

requirements-completed: [HUM2-01, HUM2-02]

# Metrics
duration: 24 min
completed: 2026-11-20
---

# Phase 18 Plan 01: Humanizer v2.0 Skills & `clinical_decision_nuances` Schema Contract Summary

**Upgraded `ru-medical-humanizer` and `nosology-research-pipeline` skills to `v2.0` and implemented strict `clinical_decision_nuances` validation (`validate_kb_clinical_nuances_v2`, `validate_kb_v2`) in `src/universal_schema.py` with 100% read-only `v1.x` backward compatibility.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-11-20T08:17:23Z
- **Completed:** 2026-11-20T08:41:37Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Upgraded `.agent/skills/ru-medical-humanizer/SKILL.md` to `v2.0`: removed legacy Japanese typo (`主に` -> `преимущественно`), expanded Section 2 banned AI cliché catalog with all 9 `v2.0` conclusion/structural clichés, and added Section 6 (`## 6. Хуманизация v2.0`) codifying the prohibition on pigeonhole routing, competing universal workhorse modalities (`universal_workhorse_modalities`), overlapping gray zones vs salvage niches, concrete Russian surgical bad-vs-good examples, and the `bold_lead_bullet_ratio <= 0.35` prose discipline.
- Upgraded `.agent/skills/nosology-research-pipeline/SKILL.md` to `v2.0`: documented `surgical_focus`, `treatment_profile`, `complications_queries`, `triage_rules.complication_terms` / `rare_complication_terms`, dedicated `PubMed:Complications` / `EuropePMC:Complications` harvesting caches, 3-trigger `complications_safety` tagging with `N >= 20` vs `Tier 4` `rare_catastrophic_case` two-contour split and priority XML queue, exact SQLite DDL tables (`extracted_mechanisms`, `extracted_clinical_evidence`, `extracted_complications`), mandatory complications section/module, `clinical_decision_nuances` contract, and `v2` verification commands.
- Extended `src/universal_schema.py` with `REQUIRED_CLINICAL_NUANCE_SECTIONS`, `REQUIRED_WORKHORSE_KEYS`, `REQUIRED_OVERLAP_KEYS`, `REQUIRED_NICHE_KEYS`, `validate_kb_clinical_nuances_v2()`, `validate_kb_v2()`, in-memory fallback defaults in `build_dynamic_fallback_kb()` and `load_nosology_bundle()`, and combined `v2` enforcement in `verify_universal_schema()`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Upgrade ru-medical-humanizer and nosology-research-pipeline skills to v2.0 (HUM2-01, HUM2-02)** - `62d93d4` (`feat`)
2. **Task 2: Add clinical_decision_nuances v2.0 contract & validator to src/universal_schema.py (HUM2-02)** - `96306bb` (`feat`)

## Files Created/Modified
- `.agent/skills/ru-medical-humanizer/SKILL.md` - Upgraded to Humanizer `v2.0` (fixed `主に` typo, expanded Section 2 banned clichés, added Section 6 non-linear clinical conclusion architecture & prose budget).
- `.agent/skills/nosology-research-pipeline/SKILL.md` - Upgraded to Pipeline `v2.0` (complications harvesting/triage/SQLite schema, `frequent_complications`/`rare_critical_red_flags`, `clinical_decision_nuances` contract, `v2` CLI verification).
- `src/universal_schema.py` - Added `clinical_decision_nuances` schema constants, `validate_kb_clinical_nuances_v2()`, `validate_kb_v2()`, in-memory `v1.x` fallback normalization (`T-18-02`), strict PMID/competing-modality checks (`T-18-01`), and `v2` enforcement in `verify_universal_schema()`.

## Verification Results
- **Task 1 check (`OK 18-01-T1`):** Confirmed zero occurrences of `主に`, presence of `## 6. Хуманизация v2.0`, all 9 banned `v2.0` clichés, `bold_lead_bullet_ratio`, and all pipeline `v2.0` contract keys across both skill files.
- **Phase 17 regression suite:** `pytest tests/test_phase17_complications.py -q` -> **11 passed in 1.47s** (including live read-only immutability checks on `prom`, `metroplasty_pregnancy`, `trigger_finger`).
- **Live `v1.x` CLI verifiers:** `uv run src/universal_schema.py --verify --nosology <id>` returned `[PASS] [v1.x (compat)]` (exit `0`) for all 3 frozen corpora (`prom`, `metroplasty_pregnancy`, `trigger_finger`).
- **Task 2 contract & threat checks (`OK 18-01-T2`):** Verified rejection of missing `clinical_decision_nuances`, missing sections, empty `universal_workhorse_modalities`, `< 2` or duplicate `competing_modalities`, `[None]`/blank/`bool`/mixed `evidence_pmids`, combined `validate_kb_v2()` reporting, and byte-identical `(st_mtime_ns, st_size)` immutability on all 3 frozen `v1.x` `kb_index.json` files.
- **Git hygiene check:** Zero changes in `data/`, `reports/`, `.planning/STATE.md`, and `.planning/ROADMAP.md`.

## Decisions Made
- Kept `validate_kb_complications_v2()` standalone for Phase 17 callers while routing `verify_universal_schema(..., schema_version="v2")` through `validate_kb_v2()`.
- Applied `load_nosology_bundle()` sub-key defaults only when `clinical_decision_nuances` is absent or `schema_version != "2.0"`, ensuring malformed `v2.0` `kb_index.json` files are strictly rejected rather than silently patched.
- Validated every element of `evidence_pmids` (rejecting `[None]`, `["  "]`, `[True]`, and `["12345", None]`) to harden `T-18-01`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Wave 1 (`18-01`) complete and verified.
- Ready for Wave 2 (`18-02`): implement structural anti-AI linter `v2.0` in `src/verify_reports.py` and test suite `tests/test_phase18_humanizer.py`, consuming `validate_kb_v2()` and the `ru-medical-humanizer v2.0` rules established here.

## Self-Check: PASSED

- Verified `.agent/skills/ru-medical-humanizer/SKILL.md`, `.agent/skills/nosology-research-pipeline/SKILL.md`, and `src/universal_schema.py` exist on disk and contain zero stub/placeholder markers.
- Verified atomic task commits `62d93d4` and `96306bb` exist in git history with zero unintended deletions.
- Verified all automated checks (`OK 18-01-T1`, `11 passed` in `tests/test_phase17_complications.py`, 3/3 `v1.x` CLI verifiers, `OK 18-01-T2`) passed and frozen `v1.x` folders + `.planning/STATE.md` / `.planning/ROADMAP.md` remain untouched.

---
*Phase: 18-v2-0*
*Completed: 2026-11-20*
