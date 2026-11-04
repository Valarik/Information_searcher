---
phase: 04
slug: interactive-application-and-verification
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-11-04
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for Phase 4 (`04-interactive-application-and-verification`).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python CLI + `streamlit.testing.v1.AppTest` (`uv run app.py --self-test`) |
| **Config file** | `configs/dupuytren.yaml` |
| **Quick run command** | `uv run src/universal_schema.py --verify` |
| **Full suite command** | `uv run app.py --self-test` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run src/universal_schema.py --verify` or `uv run app.py --self-test`.
- **After every plan wave:** Run `uv run app.py --self-test` + `uv run src/verify_reports.py --verify`.
- **Before `/gsd-verify-work`:** Full suite must pass with 0 errors.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | UI-01 | — | `src/universal_schema.py` and upgraded `reports/dupuytren/knowledge_base/kb_index.json` validate the universal disease-agnostic schema (staging, subtypes, etiology, pathogenesis phases, natural history, remission, recurrence, procediv, pros/cons) and HTML/CSV exporters | unit+schema | `uv run src/universal_schema.py --verify` | ✅ | ⬜ pending |
| 04-01-02 | 01 | 1 | UI-01 | — | `app.py` renders all 4 unified tabs without errors under `streamlit.testing.v1.AppTest` and passes CLI `--self-test`, with `README.md` documenting usage | integration | `uv run app.py --self-test` | ✅ | ⬜ pending |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready
