---
phase: 17-prisma
verified: 2026-11-19T17:22:36Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 0
deferred:
  - truth: "Форма создания нозологии в app.py (вкладка 4) содержит интерактивный переключатель surgical_focus и автошаблон complications_queries (UI-часть COMP-01)"
    addressed_in: "Phase 19"
    evidence: "Phase 19 Success Criterion 2 in ROADMAP.md: 'Конфигуратор новой нозологии во вкладке 4 (app.py) содержит переключатель хирургического профиля (surgical_focus) и автошаблон запросов по осложнениям.' Backend persistence in src/universal_schema.py (save_new_nosology_config, discover_nosologies) called by app.py:989 already supports both fields."
---

# Phase 17: Сбор, PRISMA-триаж и реляционная схема частых осложнений лечения — Verification Report

**Phase Goal:** Научить сборщик, PRISMA-триаж, SQLite-ядро и универсальную схему `kb_index.json` прицельно собирать и структурированно хранить наиболее частые осложнения лечения (в первую очередь хирургических вмешательств) с сохранением 100% обратной совместимости с базами `v1.x`.
**Verified:** 2026-11-19T17:22:36Z
**Status:** passed
**Re-verification:** No — initial verification (post code-review fix commit `1a50e14`)

---

## Goal Achievement

### Observable Truths

Merged contract combining all 4 non-negotiable ROADMAP Success Criteria (`SC-1..SC-4`) and all 9 PLAN `must_haves.truths` (`17-01`, `17-02`, `17-03`):

| # | Source | Truth | Status | Evidence |
|---|--------|-------|--------|----------|
| 1 | ROADMAP SC-1 | `src/harvester.py` поддерживает флаг `surgical_focus` и блок `complications_queries` в YAML (а при их отсутствии у хирургической нозологии автоматически генерирует подзапрос по интра- и послеоперационным осложнениям для `PubMed` и `Europe PMC`). | ✓ VERIFIED | `src/harvester.py:47-157` (`resolve_treatment_profile`, `build_complications_queries`, `SURGICAL_*_COMP_BLOCK`), `src/harvester.py:981-995` (`main()`), `src/extractor_common.py:34-67` (`resolve_treatment_profile_and_focus`); verified by `test_harvester_profile_and_hybrid_queries` (PASSED). |
| 2 | ROADMAP SC-2 | `src/triage.py` выделяет тематический тег `complications_safety`, отражает его в `prisma_stats.md` и включает работы по осложнениям в загрузку полнотекстовых XML. | ✓ VERIFIED | `src/triage.py:226-259` (`should_tag_complications_safety`), `src/triage.py:528-545` (`assign_clusters`), `src/triage.py:570-674` (`download_fulltexts_tier1_to_3`), `src/triage.py:807-822, 883-891` (`generate_prisma_report`); verified by `test_triage_complications_safety_three_triggers_and_context` and `test_triage_xml_priority_queue_and_prisma_report` (PASSED). |
| 3 | ROADMAP SC-3 | `src/schema.py` и `src/extractor_common.py` создают и обслуживают таблицу `extracted_complications` (`Clavien–Dindo`, частота `%`, обратимость, сроки, анатомическая причина, профилактика и лечение), корректно работая и со старыми базами `v1.x` без падений. | ✓ VERIFIED | `src/schema.py:109-135` (20 columns, 4 indexes via `CREATE TABLE/INDEX IF NOT EXISTS`), `src/extractor_common.py:449-854` (`table_exists`, `insert_extracted_complication`, `fetch_extracted_complications` returning `[]` when table absent); verified by `test_schema_and_extractor_dual_axis_and_recurrence_guard` and `test_v1_backward_compat_prom_metroplasty_trigger_finger_readonly` (PASSED). |
| 4 | ROADMAP SC-4 | `src/universal_schema.py` валидирует структуру `frequent_complications` в режиме `v2.0` и безопасно обрабатывает ее отсутствие в существующих нозологиях `v1.x`. | ✓ VERIFIED | `src/universal_schema.py:1103-1338` (`validate_kb_complications_v2`, `verify_universal_schema(..., schema_version=...)`, `--schema-version {auto,v1,v2}`); live `--verify` PASSED on `prom`, `metroplasty_pregnancy`, `trigger_finger`, and `--schema-version v2` strictly exited `1` on legacy `prom`. |
| 5 | 17-01 Truth 1 | `init_db()` in `src/schema.py` idempotently creates `extracted_complications` and 4 indexes via `CREATE TABLE IF NOT EXISTS` while keeping all 4 existing tables intact (`COMP-03`, `D-07`, `D-08`). | ✓ VERIFIED | `src/schema.py:18-136` retains `articles`, `clinical_trials`, `extracted_clinical_evidence`, `extracted_mechanisms` and adds `extracted_complications` + `idx_ext_comp_{article,modality,grade,class}`; repeated `init_db()` tested in `test_schema_and_extractor_dual_axis_and_recurrence_guard`. |
| 6 | 17-01 Truth 2 | `src/extractor_common.py` enforces dual-axis severity (`Clavien–Dindo I..V` with `CTCAE Grade 1–5` + `reversibility`), separates `true_complication` vs `transient_postop_sequela` with mandatory `time_window`, rejects recurrence/incomplete release (`D-08`), flags Tier 4 / `N < 20` as `is_rare_casuistry = 1` nullifying `>= 50%` rates (`D-04`), and ignores `95% CI` decoys. | ✓ VERIFIED | `src/extractor_common.py:397-827` (`normalize_clavien_dindo`, `is_excluded_recurrence_event`, `extract_complication_frequency`, `extract_clavien_dindo_grade`, `extract_resolution_time_window`, `insert_extracted_complication`); verified by `test_schema_and_extractor_*` + `test_code_review_regressions_*` + adversarial checks (CTCAE 4.0/5.0 version safety, AMA/JAMA CI stripping, partial nerve injury exemption). |
| 7 | 17-01 Truth 3 | `src/universal_schema.py` aggregates `extracted_complications` into `frequent_complications` (`>= 1.0%`, Tier 1–3, `N >= 20`, descending `frequency_median_num` per modality) and `rare_critical_red_flags` (`< 1.0%`) for `schema_version: "2.0"`, validates on `--schema-version v2`, and reads frozen `v1.x` corpora strictly read-only via `_connect_sqlite_readonly()` + `sqlite_master` without disk mutations (`COMP-04`, `D-09`). | ✓ VERIFIED | `src/universal_schema.py:129-139` (`quote(...)` URI `?mode=ro` / `immutable=1` + `PRAGMA query_only = ON`), `src/universal_schema.py:242-478` (`aggregate_complications_from_sqlite`), `src/universal_schema.py:480-628` (`build_dynamic_fallback_kb`), `src/universal_schema.py:978-1056` (`query_complications_df`); verified on live `prom`, `metroplasty_pregnancy`, `trigger_finger` with unchanged `(st_mtime_ns, st_size)` and empty `git status --porcelain`. |
| 8 | 17-02 Truth 1 | `src/harvester.py` enables treatment-complications harvesting by default for surgical/mixed nosologies (`surgical_focus: true` / `surgical` \| `mixed`) and switches to adverse-effects/CTCAE block when `surgical_focus: false` or `treatment_profile: conservative` (`COMP-01`, `D-01`). | ✓ VERIFIED | `src/extractor_common.py:34-67` + `src/harvester.py:61-83, 113-114`; verified by `test_harvester_profile_and_hybrid_queries` and `test_code_review_regressions_*` (including top-level `surgical_focus: true` override precedence). |
| 9 | 17-02 Truth 2 | `src/harvester.py` performs hybrid query resolution (`complications_queries` override vs auto-generated `date_range`-bounded query), caches in `pubmed_complications.json` and `europepmc_complications.json` atomically without error-dict cache poisoning, and merges `PubMed:Complications` / `EuropePMC:Complications` into `articles.sources` via `upsert_article()` (`D-02`, `D-03`). | ✓ VERIFIED | `src/harvester.py:73-77, 86-157, 730-935`; atomic write via `_write_json_atomic`, error-dict guards on efetch/esummary/epmc (`CR-03`), verified by `test_harvester_complications_cache_and_provenance_merge` and `test_code_review_regressions_*`. |
| 10 | 17-02 Truth 3 | `src/triage.py` isolates Tier 4 case reports and clinical small series (`1 <= N < 20`) with `rare_catastrophic_case` without false Tier 2 demotion (`D-04`), tags `complications_safety` from all 3 `D-05` signals and reports in `prisma_stats.md` (`COMP-02`), and prioritizes Tier 1–3 `complications_safety` XML downloads with `PMCID_RE` path-traversal blocking (`D-06`, `T-17-04`). | ✓ VERIFIED | `src/triage.py:195-285, 304-674, 677-921`; verified by `test_triage_*` and `test_code_review_regressions_*` (multicenter/prospective cohort protection `WR-01`, missing-abstract marker `IN-01`, plural `rats` `IN-05`). |
| 11 | 17-03 Truth 1 | Offline mocked pytest suite verifies `src/harvester.py` (`D-01..D-03`, `COMP-01`, `T-17-03`). | ✓ VERIFIED | `tests/test_phase17_complications.py:41-306` (`-k "harvester"` -> 2 passed in 0.39s). |
| 12 | 17-03 Truth 2 | Offline mocked pytest suite verifies `src/triage.py` (`D-04..D-06`, `COMP-02`, `T-17-04`). | ✓ VERIFIED | `tests/test_phase17_complications.py:314-637` (`-k "triage"` -> 3 passed in 0.37s). |
| 13 | 17-03 Truth 3 | Automated pytest suite verifies `src/schema.py`, `src/extractor_common.py`, `src/universal_schema.py` v2.0 aggregation/validation, live read-only `v1.x` immutability (`prom`, `metroplasty_pregnancy`, `trigger_finger`), code review regressions, and `uv run app.py --self-test` (`COMP-03`, `COMP-04`, `D-07..D-09`, `T-17-01..T-17-05`). | ✓ VERIFIED | `tests/test_phase17_complications.py:645-1645` (`pytest tests/ -v` -> 11/11 passed in 1.28s) + `uv run app.py --self-test` (`[PASS]`, 0 exceptions). |

**Score:** 13/13 truths verified

---

### Deferred Items (Step 9b)

Items outside Phase 17's own `ROADMAP.md` Success Criteria and `17-CONTEXT.md` Phase Boundary that appear in milestone-level requirement wording (`COMP-01`) and are explicitly assigned to a later Milestone `v2.0` phase:

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | Interactive `surgical_focus` toggle and `complications_queries` auto-template UI widget in Tab 4 of `app.py` (UI portion of `COMP-01`) | Phase 19 | `ROADMAP.md` Phase 19 Success Criterion 2: *"Конфигуратор новой нозологии во вкладке 4 (`app.py`) содержит переключатель хирургического профиля (`surgical_focus`) и автошаблон запросов по осложнениям"*; `17-CONTEXT.md` Phase Boundary explicitly assigns `app.py` UI updates to Phase 19. Meanwhile, `src/universal_schema.py:save_new_nosology_config()` and `discover_nosologies()` (already wired into `app.py:44,51,989,1016`) fully support both fields today. |

---

### Required Artifacts (Levels 1–3)

| Artifact | Expected | Exists | Substantive | Wired | Status | Details |
|----------|----------|--------|-------------|-------|--------|---------|
| `src/schema.py` | SQLite DDL for `extracted_complications` (20 cols) + 4 indexes | ✓ | ✓ (139 lines, idempotent DDL) | ✓ (imported by `harvester.py`, `triage.py`, tests) | ✓ VERIFIED | `CREATE TABLE IF NOT EXISTS extracted_complications` (`L109-130`) + 4 `CREATE INDEX IF NOT EXISTS` (`L132-135`), 4 legacy tables intact. |
| `src/extractor_common.py` | `validate_nosology_id`, `resolve_treatment_profile_and_focus`, dual-axis severity normalizer, recurrence guard, CI-safe & JATS parsers, parameterized CRUD | ✓ | ✓ (854 lines, full validation & parsers) | ✓ (imported by `universal_schema.py`, `harvester.py`, `triage.py`, tests) | ✓ VERIFIED | All 8 planned exports + 2 review-hardening shared helpers present and tested. |
| `src/universal_schema.py` | Read-only SQLite URI connector, `query_complications_df`, `aggregate_complications_from_sqlite`, `validate_kb_complications_v2`, `--schema-version` CLI | ✓ | ✓ (1342 lines, full aggregator/validator) | ✓ (imported by `app.py` and CLI `--verify`) | ✓ VERIFIED | `_connect_sqlite_readonly()` uses percent-encoded `?mode=ro` + `PRAGMA query_only = ON`; `verify_universal_schema()` & `main()` support `{auto,v1,v2}`. |
| `src/harvester.py` | `resolve_treatment_profile`, `build_complications_queries` / `resolve_complications_queries`, `harvest_pubmed_complications`, `harvest_europepmc_complications` | ✓ | ✓ (1020 lines, 6-pass CLI + atomic JSON cache) | ✓ (`main()` invokes passes 5 & 6 and merges via `upsert_article`) | ✓ VERIFIED | `validate_nosology_id` + `is_relative_to(base_data)` in `main()`; error-dict guards + `_write_json_atomic` (`CR-03`). |
| `src/triage.py` | `should_tag_complications_safety`, two-contour `classify_evidence_tier`, `assign_clusters`, priority `download_fulltexts_tier1_to_3`, updated `generate_prisma_report` | ✓ | ✓ (1038 lines, full PRISMA pipeline) | ✓ (`main()` wires all functions end-to-end) | ✓ VERIFIED | `validate_nosology_id` + `is_relative_to` on `data/` and `reports/`; `PMCID_RE` enforced pre-slice and pre-write. |
| `tests/test_phase17_complications.py` | Offline unit, integration, security, review-regression, and live `v1.x` read-only test suite (`min_lines: 240`) | ✓ | ✓ (1645 lines, 11 test functions) | ✓ (exercises all 5 `src/` modules + live `v1.x` DBs) | ✓ VERIFIED | All 11 tests pass offline in `1.28s`; covers all 5 `17-VALIDATION.md` `-k` filters + `CR-01..05` / `WR-01..09` / `IN-01..05`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/extractor_common.py` | `src/schema.py` | Parameterized `INSERT INTO extracted_complications` (`L780`) / `SELECT * FROM extracted_complications` (`L849`) + `sqlite_master` `table_exists()` (`L451`) | ✓ WIRED | Exact 19 non-PK columns match `src/schema.py:109-130`; positional `?` parameters used exclusively. |
| `src/universal_schema.py` | `src/extractor_common.py` | Shared imports `VALID_CLAVIEN_DINDO`, `VALID_REVERSIBILITY`, `VALID_EVENT_CLASS`, `DEFAULT_SEQUELA_TIME_WINDOW`, `is_excluded_recurrence_event`, `resolve_treatment_profile_and_focus`, `table_exists`, `validate_nosology_id` (`L37-46`) | ✓ WIRED | Used directly in `discover_nosologies`, `get_sqlite_corpus_stats`, `aggregate_complications_from_sqlite`, `query_complications_df`, `save_new_nosology_config`, and `validate_kb_complications_v2`. |
| `src/harvester.py` | `articles.sources` | `harvest_pubmed_complications()` & `harvest_europepmc_complications()` writing `pubmed_complications.json` / `europepmc_complications.json` and merging `PubMed:Complications` / `EuropePMC:Complications` via `upsert_article()` (`L730-935`, `L981-995`) | ✓ WIRED | Verified by `test_harvester_complications_cache_and_provenance_merge` producing deduplicated `["PubMed", "PubMed:Complications", "EuropePMC:Complications"]`. |
| `src/triage.py` | `reports/<id>/prisma_stats.md` | `should_tag_complications_safety()` -> `assign_clusters()` -> `articles.clusters` -> `download_fulltexts_tier1_to_3()` `ORDER BY` -> `generate_prisma_report()` `total_raw` & `complications_safety` cluster table (`L226-259, L528-674, L713-891, L977-1026`) | ✓ WIRED | Verified by `test_triage_xml_priority_queue_and_prisma_report` confirming `N = 7`, `PubMed:Complications: 3 \| EuropePMC:Complications: 2`, and `complications_safety` row. |
| `tests/test_phase17_complications.py` | `src/{harvester,triage,schema,extractor_common,universal_schema}.py` | 11 pytest functions asserting `COMP-01..04`, `D-01..09`, `T-17-01..05`, and `CR-01..05`/`WR-01..09`/`IN-01..05` | ✓ WIRED | Executed live: `11 passed in 1.28s`. |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `src/universal_schema.py:get_sqlite_corpus_stats` | `stats["extracted_complications_rows"]` | Live read-only SQLite `SELECT COUNT(*) FROM extracted_complications` (guarded by `table_exists`) | Yes (`0` on `v1.x`, live count on `v2.0`) | ✓ FLOWING |
| `src/universal_schema.py:aggregate_complications_from_sqlite` | `frequent_complications`, `rare_critical_red_flags` | Live read-only SQLite `LEFT JOIN articles` with `COALESCE(c.pmid, a.pmid)` & `COALESCE(c.evidence_tier, a.evidence_tier)` + `statistics.median` | Yes (real grouped medians & PMIDs, zero hardcoded stubs) | ✓ FLOWING |
| `src/universal_schema.py:build_dynamic_fallback_kb` | `kb["frequent_complications"]`, `kb["rare_critical_red_flags"]` | Populated directly from `aggregate_complications_from_sqlite(db_path)` (`L558, L626-627`) | Yes | ✓ FLOWING |
| `src/triage.py:generate_prisma_report` | `raw_pubmed_comp`, `raw_epmc_comp`, `cluster_stats` (`complications_safety`) | Live JSON caches (`raw/*_complications.json`) and live SQLite `COUNT(*)` queries (`L713-822`) | Yes | ✓ FLOWING |

---

### Behavioral Spot-Checks (Step 7b)

All commands executed independently in this verification pass (Windows PowerShell with `$env:PATH = "$HOME\.local\bin;" + $env:PATH;`):

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full pytest suite | `uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/ -v` | `11 passed in 1.28s` (exit `0`) | ✓ PASS |
| All 5 `17-VALIDATION.md` `-k` filters | `pytest tests/test_phase17_complications.py -k "{harvester\|triage\|schema_and_extractor\|universal_schema\|v1_backward_compat}" -q` | `2`, `3`, `2`, `2`, `1` passed respectively (all exit `0`) | ✓ PASS |
| Frozen `v1.x` CLI schema verify (`prom`) | `uv run src/universal_schema.py --verify --nosology prom` | `[PASS] Universal schema verified for 'prom' [v1.x (compat)]`, `articles=2643, complications=0` (exit `0`) | ✓ PASS |
| Frozen `v1.x` CLI schema verify (`metroplasty_pregnancy`) | `uv run src/universal_schema.py --verify --nosology metroplasty_pregnancy` | `[PASS] Universal schema verified for 'metroplasty_pregnancy' [v1.x (compat)]`, `articles=506, complications=0` (exit `0`) | ✓ PASS |
| Frozen `v1.x` CLI schema verify (`trigger_finger`) | `uv run src/universal_schema.py --verify --nosology trigger_finger` | `[PASS] Universal schema verified for 'trigger_finger' [v1.x (compat)]`, `articles=1024, complications=0` (exit `0`) | ✓ PASS |
| Strict `v2` CLI rejection on legacy `v1.x` KB | `uv run src/universal_schema.py --verify --nosology prom --schema-version v2` | `[FAIL]` reporting missing `schema_version == '2.0'`, `frequent_complications`, `rare_critical_red_flags` (`EXIT=1`) | ✓ PASS |
| Streamlit app headless regression check | `uv run app.py --self-test` | `[PASS] Streamlit AppTest rendered all 4 tabs and all 3 report modes with 0 exceptions (metrics=6, dataframes=6, tabs=8)` (exit `0`) | ✓ PASS |
| Frozen `v1.x` disk immutability check | `git status --porcelain data/prom data/metroplasty_pregnancy data/trigger_finger reports/prom reports/metroplasty_pregnancy reports/trigger_finger` | Empty stdout (zero modified/untracked files, exit `0`) | ✓ PASS |
| CLI path traversal rejection (`CR-01`, `T-17-03`) | `uv run src/harvester.py --config <evil.yaml>` & `uv run src/triage.py --config <evil.yaml> --verify-only` (`nosology_id: '../../outside'`) | Both failed before directory/DB creation with `ValueError: Invalid nosology_id '../../outside'` (`HARV_EXIT=1`, `TRIAGE_EXIT=1`) | ✓ PASS |
| Adversarial edge-case verification | Inline Python check (`#`/`%` SQLite RO path, CTCAE `4.0`/`4.03`/`5.0` non-matching, `[0.2, 0.4, 1.5]` red-flag outlier, qualitative Tier 2 severe row, `/` EPMC date normalization, explicit `0` max_results, standalone DB without `articles` table) | `ALL ADVERSARIAL EDGE CHECKS PASSED` (exit `0`) | ✓ PASS |

---

### Probe Execution (Step 7c)

No `scripts/*/tests/probe-*.sh` files exist in the repository and no shell probes were declared in `17-01..03-PLAN.md` or `17-VALIDATION.md` (verified via recursive `Get-ChildItem -Filter "probe-*.sh"` returning empty).

---

### Requirements Coverage (`COMP-01..COMP-04`)

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| `COMP-01` | `17-02`, `17-03` | `configs/<id>.yaml` (and `app.py` form — UI toggle deferred to Phase 19 SC-2) support `surgical_focus: true/false` & `complications_queries`; `src/harvester.py` runs dedicated complication harvesting pass or auto-generates `Postoperative Complications / Intraoperative Complications / adverse effects` subquery. | ✓ SATISFIED (engine & config persistence complete; Tab 4 UI widget explicitly deferred to Phase 19 SC-2) | `src/harvester.py:47-157, 730-935, 981-995`; `src/universal_schema.py:167-179, 1076-1092`; `tests/test_phase17_complications.py:41-306, 1283-1324`. |
| `COMP-02` | `17-02`, `17-03` | `src/triage.py` tags safety/complications publications with `complications_safety`, accounts for them in `prisma_stats.md`, and includes them in Europe PMC Full-Text XML downloads. | ✓ SATISFIED | `src/triage.py:129-179, 226-259, 528-674, 713-891`; `tests/test_phase17_complications.py:314-637`. |
| `COMP-03` | `17-01`, `17-03` | `src/schema.py` & `src/extractor_common.py` provide `extracted_complications` table and read/write helpers with safe `CREATE TABLE IF NOT EXISTS` migration and `v1.x` compatibility. | ✓ SATISFIED | `src/schema.py:109-135`; `src/extractor_common.py:397-854`; `tests/test_phase17_complications.py:645-970`. |
| `COMP-04` | `17-01`, `17-03` | `src/universal_schema.py` supports `frequent_complications` in `kb_index.json` with strict `v2.0` validation and safe fallback on existing `v1.x` nosologies. | ✓ SATISFIED | `src/universal_schema.py:85-139, 242-478, 978-1056, 1103-1338`; `tests/test_phase17_complications.py:977-1399`; live `--verify` on all 3 `v1.x` nosologies. |

*Orphaned requirements check:* All 4 Phase 17 requirements in `.planning/REQUIREMENTS.md` (`COMP-01..COMP-04`) are claimed across Plans `17-01..17-03` and verified. Zero orphaned requirements.

---

### Locked Decisions Coverage (`D-01..D-09`)

| Decision | Summary | Status | Code Evidence |
|----------|---------|--------|---------------|
| `D-01` | Surgical/mixed default (`surgical_focus: true`), auto-switch to adverse-effects/CTCAE when `surgical_focus: false` or `treatment_profile: conservative` | ✓ VERIFIED | `src/extractor_common.py:34-67`, `src/harvester.py:61-83, 113-114`, `src/universal_schema.py:167, 1076-1079`. |
| `D-02` | Hybrid query assembly: explicit YAML `complications_queries` overrides auto-generated MeSH/tiab + safety block within `date_range` | ✓ VERIFIED | `src/harvester.py:86-157`. |
| `D-03` | Separate raw caches `pubmed_complications.json` & `europepmc_complications.json`, deduplicated into `articles` with `PubMed:Complications` / `EuropePMC:Complications` in `articles.sources` | ✓ VERIFIED | `src/harvester.py:730-935`, `upsert_article()` at `L223-355`. |
| `D-04` | Two-contour separation: frequent rates (`%`) from `Tier 1–3`, `N >= 20`; `Tier 4` / `N < 20` isolated as `rare_catastrophic_case` / `is_rare_casuistry = 1` with `1/1 (100%)` numeric nullification | ✓ VERIFIED | `src/triage.py:372-525`, `src/extractor_common.py:759-776`, `src/universal_schema.py:345-470`. |
| `D-05` | Combined 3-signal `complications_safety` cluster tag (`:Complications` provenance, universal vocabularies, YAML `complication_terms`/`rare_complication_terms`) + `prisma_stats.md` reporting | ✓ VERIFIED | `src/triage.py:129-179, 226-259, 542-544, 807-822, 883-891`. |
| `D-06` | Priority Europe PMC Full-Text XML queue for `Tier 1–3` `complications_safety` articles | ✓ VERIFIED | `src/triage.py:557-612` (SQL `CASE` priority ordering + `_has_epmc_source`). |
| `D-07` | Dual-axis severity: `clavien_dindo_grade` (`I..V`, with `CTCAE Grade 1–5` mapping) + `reversibility` enum | ✓ VERIFIED | `src/schema.py:120-124`, `src/extractor_common.py:397-417, 466-536, 709-717`. |
| `D-08` | `event_class` split (`true_complication` vs `transient_postop_sequela` with mandatory `time_window`) and exclusion of disease recurrence / incomplete release | ✓ VERIFIED | `src/extractor_common.py:406-430, 458-464, 697-730`, `src/universal_schema.py:295-296, 1129-1148`. |
| `D-09` | `schema_version: "2.0"` `frequent_complications` (`>= 1.0%`, descending median per modality) + `rare_critical_red_flags` (`< 1.0%`) + zero-mutation read-only `v1.x` fallback via `sqlite_master` | ✓ VERIFIED | `src/universal_schema.py:85-139, 242-478, 558-628, 1103-1322`. |

---

### Security Controls Verification (`T-17-01..T-17-05`)

| Threat ID | Mitigation Requirement | Status | Evidence |
|-----------|------------------------|--------|----------|
| `T-17-01` | Positional `?` SQLite parameters across all INSERT/SELECT/`sqlite_master` queries + strict enum allowlists | ✓ VERIFIED | `src/extractor_common.py:451-455, 704-717, 778-823, 839-852`; SQLi payload tests in `tests/test_phase17_complications.py:841-875`. |
| `T-17-02` | Strictly read-only SQLite access (`?mode=ro` / `immutable=1`, `PRAGMA query_only = ON`), `sqlite_master` check, zero `init_db()` calls in readers, frozen `v1.x` files untouched | ✓ VERIFIED | `src/universal_schema.py:129-139, 206, 228, 249-251, 492, 982-985`; `#`/`%` path RO test (`CR-02`), unchanged `(st_mtime_ns, st_size)`, clean `git status`. |
| `T-17-03` | `yaml.safe_load()`, validated `nosology_id` (`^[a-z0-9_]+$`) + `is_relative_to(base_data)` path containment, fixed cache filenames (`*_complications.json`), parameterized `upsert_article()` | ✓ VERIFIED | `src/extractor_common.py:21-31`, `src/harvester.py:741, 861, 952-961`, `src/triage.py:932-952`; live CLI traversal blocked (`HARV_EXIT=1`, `TRIAGE_EXIT=1`). |
| `T-17-04` | `PMCID_RE = re.compile(r"^PMC\d+$")` pre-slice and pre-write path-traversal guard + `b"<article"` XML header validation | ✓ VERIFIED | `src/triage.py:43, 603-606, 621-624, 648`; `../evil` adversarial test in `tests/test_phase17_complications.py:521-603`. |
| `T-17-05` | Strict `nosology_id` regex + resolved parent path containment + `yaml.safe_load()` / `yaml.safe_dump()` exclusively in `universal_schema.py` | ✓ VERIFIED | `src/universal_schema.py:151, 159-165, 1069-1073, 1095-1098`; `../escape` & `../../escape` blocked in `tests/test_phase17_complications.py:1322-1324, 1408-1421`. |

---

### Code Review Findings Resolution Audit (`17-REVIEW.md` -> Commit `1a50e14`)

Independently verified every finding from `.planning/phases/17-prisma/17-REVIEW.md` against current source on disk:

| ID | Severity | Finding | Status | Verified Location in Code |
|----|----------|---------|--------|---------------------------|
| `CR-01` | Critical | Unvalidated YAML `nosology_id` path traversal | ✓ FIXED | `src/extractor_common.py:21-31`, `src/harvester.py:954-961`, `src/triage.py:934-952`, `src/universal_schema.py:159-165`. |
| `CR-02` | Critical | `_connect_sqlite_readonly()` missing URI encoding & RW fallback | ✓ FIXED | `src/universal_schema.py:27, 129-139` (`quote(..., safe="/:")`, `mode=ro&immutable=1`, `PRAGMA query_only = ON`). |
| `CR-03` | Critical | `harvest_*_complications()` ignoring error dicts & cache poisoning | ✓ FIXED | `src/harvester.py:73-77, 772-782, 837, 874-884` (`RuntimeError` on error dicts + `_write_json_atomic`). |
| `CR-04` | Critical | CTCAE version numbers (`4.0`/`5.0`) misclassified as Grade IV/V | ✓ FIXED | `src/extractor_common.py:477-497, 628-640` (explicit grade marker + `(?!\.\d)`). |
| `CR-05` | Critical | `validate_kb_complications_v2()` passing `NaN`/`>100%`/empty modality/`[None]` PMIDs | ✓ FIXED | `src/universal_schema.py:1122-1240` (`math.isfinite`, `<= 100.0`, non-empty `modality`, `p is not None`). |
| `WR-01` | Warning | Tier 2 false demotion on arm counts / event numerators | ✓ FIXED | `src/triage.py:195-205, 500-520` (`EXPLICIT_COHORT_SAMPLE_SIZE_PATTERNS`, `large_design_tier2`). |
| `WR-02` | Warning | AMA/JAMA comma-delimited `95% CI` leak & `re.search` early abort | ✓ FIXED | `src/extractor_common.py:544-600` (`re.finditer`, bracketed & comma-delimited CI stripping). |
| `WR-03` | Warning | `aggregate_complications_from_sqlite()` missing `COALESCE`, dropped qualitative Tier 1–3, outlier label, case-sensitive sort | ✓ FIXED | `src/universal_schema.py:260-263, 346-370, 415-456, 471-476`. |
| `WR-04` | Warning | `save_new_nosology_config()` dropping max_results, keeping empty dict, mutating input, crashing on `nosology: None` | ✓ FIXED | `src/universal_schema.py:1061-1093` (`copy.deepcopy`, non-dict guard, allowlist includes `*_max_results`, `pop` on empty). |
| `WR-05` | Warning | String `"0"`/`"false"` truthy casuistry, missing numeric bounds, non-string `grade` crash, `CTCAE-3` mismatch | ✓ FIXED | `src/extractor_common.py:433-446, 477-489, 731-767`. |
| `WR-06` | Warning | `is_excluded_recurrence_event()` rejecting partial nerve/tendon injuries | ✓ FIXED | `src/extractor_common.py:423, 427` (anatomical injury negative lookahead in EN/RU). |
| `WR-07` | Warning | `parse_jats_xml()` routing `"Patient Safety"` to `methods_text` | ✓ FIXED | `src/extractor_common.py:156-175` (safety/results keywords checked before `"patient"`). |
| `WR-08` | Warning | Top-level `surgical_focus: true` override precedence & metadata consistency | ✓ FIXED | `src/extractor_common.py:34-67`, shared across `src/harvester.py:38,82` and `src/universal_schema.py:43,167,1076`. |
| `WR-09` | Warning | Overly broad `git status` scope in `v1.x` regression test | ✓ FIXED | `tests/test_phase17_complications.py:1381-1398` (explicitly scoped to `prom`, `metroplasty_pregnancy`, `trigger_finger`). |
| `IN-01..05` | Info | Missing-abstract marker, EPMC `/` dates & `0` limits, dynamic cluster count heading, standalone `query_complications_df`, plural `rats` | ✓ FIXED | `src/triage.py:285, 460, 883`, `src/harvester.py:125-145`, `src/universal_schema.py:987-1045`. |

---

### Anti-Patterns Found

Scanned `src/schema.py`, `src/extractor_common.py`, `src/universal_schema.py`, `src/harvester.py`, `src/triage.py`, and `tests/test_phase17_complications.py` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER|coming soon|not yet implemented` and hollow stub returns:

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| *(none)* | — | 0 matches across all 6 Phase 17 files | — | No unresolved debt markers or stub implementations found. |

---

### Human Verification Required

None. All Phase 17 engine behaviors (`harvester.py`, `triage.py`, `schema.py`, `extractor_common.py`, `universal_schema.py`, and `v1.x` read-only backward compatibility) are backend data/pipeline contracts fully verified by automated offline tests, CLI probes, and headless `app.py --self-test` (`17-VALIDATION.md` confirms zero manual-only checks; UI widgets belong to Phase 19).

---

### Gaps Summary

No blocking gaps or warnings remain. All 4 ROADMAP Success Criteria, all 9 PLAN `must_haves` truths, all 4 Phase 17 requirements (`COMP-01..COMP-04`, with the Tab 4 `app.py` UI widget explicitly scoped to Phase 19 SC-2), all 9 locked decisions (`D-01..D-09`), all 5 ASVS L1 security controls (`T-17-01..T-17-05`), and all 19 code-review findings (`CR-01..05`, `WR-01..09`, `IN-01..05`) from `17-REVIEW.md` are verified against actual code and live command execution on disk. Frozen Milestone `v1.x` corpora (`prom`, `metroplasty_pregnancy`, `trigger_finger`) remain byte-identical and pass all schema and Streamlit self-tests.

---

_Verified: 2026-11-19T17:22:36Z_
_Verifier: the agent (gsd-verifier)_
