---
phase: 01
slug: harvesting-and-prisma-triage
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-11-04
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` + SQLite assertions (`uv run python`) |
| **Config file** | `configs/dupuytren.yaml` |
| **Quick run command** | `uv run python -c "import src.schema, src.harvester, src.triage; print('OK')"` |
| **Full suite command** | `uv run python src/triage.py --config configs/dupuytren.yaml --verify-only` |
| **Estimated runtime** | ~3 seconds (verification) |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -c "import sqlite3; conn=sqlite3.connect('data/dupuytren/literature.db'); print(conn.execute('SELECT count(*) FROM articles').fetchone()[0])"`
- **After every plan wave:** Run `uv run python src/triage.py --config configs/dupuytren.yaml --verify-only`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | HARV-01 | T-01-01 | Безопасная работа без утечки ключей `.env` и параметризованные SQL-запросы | integration | `uv run python src/harvester.py --help` | ✅ | ⬜ pending |
| 01-01-02 | 01 | 1 | HARV-02 | T-01-02 | Дедупликация записей в SQLite и соблюдение лимитов API (D-08) | integration | `uv run python src/harvester.py --config configs/dupuytren.yaml` | ✅ | ⬜ pending |
| 01-02-01 | 02 | 2 | HARV-03, HARV-04 | T-01-03 | Безопасный парсинг XML и защита от path traversal при сохранении PMCID | integration | `uv run python src/triage.py --config configs/dupuytren.yaml` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure (`uv`, `sqlite3`, `src/schema.py`, `configs/dupuytren.yaml`) covers all phase requirements.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-11-04
