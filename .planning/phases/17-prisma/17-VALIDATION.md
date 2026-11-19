---
phase: 17
slug: prisma
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-11-19
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest 9.2.0` (via `uv run --with pytest ...` under PEP 723 inline-script architecture) |
| **Config file** | None (`pyproject.toml` omitted by project convention; inline dependencies passed via `--with`) |
| **Quick run command** | `$env:PATH = "$HOME\.local\bin;" + $env:PATH; uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/test_phase17_complications.py -q` |
| **Full suite command** | `$env:PATH = "$HOME\.local\bin;" + $env:PATH; uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/ -q; uv run app.py --self-test` |
| **Estimated runtime** | ~4 seconds (`pytest` offline mocked) + ~6 seconds (`app.py --self-test`) |

---

## Sampling Rate

- **After every task commit:** Run `$env:PATH = "$HOME\.local\bin;" + $env:PATH; uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/test_phase17_complications.py -q` (or targeted `-c` smoke assertions while Wave 1 builds modules before test suite completion)
- **After every plan wave:** Run full suite (`pytest tests/ -q` + `uv run src/universal_schema.py --verify --nosology prom` / `metroplasty_pregnancy` / `trigger_finger`)
- **Before `/gsd-verify-work`:** Full suite + `uv run app.py --self-test` must be green and `git status` must show zero mutations to `data/prom`, `data/metroplasty_pregnancy`, `data/trigger_finger`, and `reports/`
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 1 | COMP-03 | T-17-01 | Parameterized SQL (`?`), enum validation (`Clavien–Dindo`, `reversibility`, `event_class`), recurrence exclusion (`D-07`, `D-08`) | unit | `uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/test_phase17_complications.py -k "schema_and_extractor" -x` | ❌ W0 | ⬜ pending |
| 17-01-02 | 01 | 1 | COMP-04 | T-17-02 | Read-only `sqlite_master` table guard on `v1.x` DBs without DDL/DML mutation (`D-09`) | unit + regression | `uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/test_phase17_complications.py -k "universal_schema or v1_backward_compat" -x` | ❌ W0 | ⬜ pending |
| 17-02-01 | 02 | 1 | COMP-01 | T-17-03 | `yaml.safe_load`, separate raw cache files `*_complications.json`, provenance merge in `articles.sources` (`D-01..D-03`) | unit + integration | `uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/test_phase17_complications.py -k "harvester" -x` | ❌ W0 | ⬜ pending |
| 17-02-02 | 02 | 1 | COMP-02 | T-17-04 | Preserve `PMCID_RE` (`^PMC\d+$`) path traversal check while boosting `complications_safety` XML queue (`D-04..D-06`) | unit + integration | `uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/test_phase17_complications.py -k "triage" -x` | ❌ W0 | ⬜ pending |
| 17-03-01 | 03 | 2 | COMP-01, COMP-02, COMP-03, COMP-04 | T-17-01..04 | End-to-end offline pipeline test + live read-only `v1.x` integrity check (`git status` clean) | integration + regression | `uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/test_phase17_complications.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase17_complications.py` — automated offline unit/integration test suite covering `COMP-01..COMP-04`, `D-01..D-09`, mocked API harvesting/XML fetching, JATS XML complication extraction, `kb_index.json` v2 validation, and read-only backward compatibility against `prom`, `metroplasty_pregnancy`, and `trigger_finger`.

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-11-19
