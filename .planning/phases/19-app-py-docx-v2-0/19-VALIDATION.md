---
phase: 19
slug: app-py-docx-v2-0
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-11-22
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest 9.2.0` + `streamlit.testing.v1.AppTest` (`Streamlit 1.67.0`) |
| **Config file** | None (`uv` PEP 723 standalone workspace) |
| **Quick run command** | `$env:PATH = "$HOME\.local\bin;" + $env:PATH; uv run --with pytest --with streamlit --with plotly --with pyyaml --with pandas --with markdown --with truststore pytest tests/test_v2_engine.py -v` |
| **Full suite command** | `$env:PATH = "$HOME\.local\bin;" + $env:PATH; uv run --with pytest --with streamlit --with plotly --with pyyaml --with pandas --with markdown --with truststore pytest tests/ -v; uv run app.py --self-test` |
| **Estimated runtime** | ~25 seconds (pytest ~12s + `app.py --self-test` ~13s) |

---

## Sampling Rate

- **After every task commit:** Run targeted smoke/pytest check + `pytest tests/test_phase17_complications.py tests/test_phase18_humanizer.py -q` (~3.5s)
- **After every plan wave:** Run full suite (`pytest tests/ -v` + `uv run app.py --self-test`) + frozen `v1.x` `git status --porcelain` check
- **Before `/gsd-verify-work`:** Full suite must be green with `0` exceptions and `0` mutations in all 6 frozen `v1.x` directories
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | EXPORT-02 (D-06, D-07) | T-19-01, T-19-02 | `docx_exporter.py`: strict ECMA-376 `<w:cantSplit/>` + `<w:tblHeader/>` + scoped `IIIb–V`/Red Flags `<w:shd>`, escaped Markdown/XML cells, `PermissionError` guard on frozen `v1.x` repo overwrites | unit + XML DOM | `uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/test_phase17_complications.py tests/test_phase18_humanizer.py -q` + inline XML check | ✅ | ⬜ pending |
| 19-01-02 | 01 | 1 | UI-02, EXPORT-02 (D-01, D-05, D-08) | T-19-01, T-19-05 | `universal_schema.py` (`INFO_SEARCHER_ROOT` + `discover_nosologies(configs_dir=None)` + frozen config overwrite guard) & `verify_reports.py` (`>= 5` modules for 6-module `v2.0` + `INFO_SEARCHER_ROOT`) | unit + integration | `uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/test_phase17_complications.py tests/test_phase18_humanizer.py -v` | ✅ | ⬜ pending |
| 19-02-01 | 02 | 2 | UI-02 (D-01, D-02, D-03) | T-19-02, T-19-05 | `app.py`: PEP 723 `truststore`, sidebar `Строк осложнений`, Tab 1 dynamic modules & unified `build_executive_docx_bytes` / `build_full_dossier_docx_bytes`, Tab 2 subtabs `2.5` (4 filters, 2 Plotly charts, CSV, Red Flags, `v1.x` fallback) & `2.6` (3 `clinical_decision_nuances` blocks, `v1.x` fallback), 0 `unsafe_allow_html` in new UI | smoke + AppTest | `uv run app.py --self-test` | ✅ | ⬜ pending |
| 19-02-02 | 02 | 2 | UI-02, EXPORT-02 (D-04, D-05, D-08) | T-19-01, T-19-03 | `app.py`: Tab 3 5th radio `extracted_complications` (filters, casuistry toggle, links, `.csv`, read-only `v1.x`), Tab 4 `surgical_focus` live preview above `st.form`, aligned `openalex_search` / `clinical_trials_condition`, safe default `carpal_tunnel_syndrome`, `--read-only` audit button, extended `run_self_test()`, `width="stretch"` | smoke + AppTest | `uv run app.py --self-test` | ✅ | ⬜ pending |
| 19-03-01 | 03 | 3 | UI-02, EXPORT-02 (D-06, D-07, D-08) | T-19-01..T-19-05 | `tests/test_v2_engine.py`: full E2E synthetic `v2.0` (SQLite -> aggregation -> 6-module `kb_index v2.0` -> `verify_reports --schema-version v2 --read-only` -> OpenXML `.docx` DOM assertions -> isolated `AppTest` Tabs 1–4) + frozen `v1.x` (`prom`, `metroplasty_pregnancy`, `trigger_finger`) SHA-256/`mtime_ns`/`git status` zero-mutation gate | e2e + regression | `uv run --with pytest --with streamlit --with plotly --with pyyaml --with pandas --with markdown --with truststore pytest tests/ -v` | ❌ Created in 19-03 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements (`pytest 9.2.0`, `streamlit 1.67.0` `AppTest`, `plotly 7.1.0`, `uv 0.13.7` verified; 17/17 baseline tests pass). `tests/test_v2_engine.py` is created as the dedicated verification deliverable in Plan `19-03`.

---

## Manual-Only Verifications

All phase behaviors have automated verification (`pytest` + `Streamlit AppTest` + `ET.fromstring` OpenXML DOM inspection + SHA-256/`mtime_ns`/`git status` immutability gate). Optional visual spot-check in a live browser (`uv run streamlit run app.py`) or MS Word is purely cosmetic.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (will be updated by planner & checker once PLAN files are finalized)
