---
phase: 03
slug: multi-mode-synthesis
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-11-04
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for Phase 3 (`03-multi-mode-synthesis`).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Custom Python CLI validator (`src/verify_reports.py`) |
| **Config file** | `configs/dupuytren.yaml` |
| **Quick run command** | `uv run src/verify_reports.py --verify` |
| **Full suite command** | `uv run src/verify_reports.py --compile-bibliography --verify` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Inspect generated `.md` files and run `uv run src/verify_reports.py --verify` once implemented.
- **After every plan wave:** Run `uv run src/verify_reports.py --compile-bibliography --verify`.
- **Before `/gsd-verify-work`:** Full suite must exit with code `0` (`0` missing PMIDs/DOIs/NCTs, `0` banned AI cliches, all 3 report modes present and populated).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | SYNT-01 | — | Chapters 1–2 of `dissertation_report.md` written with clinical focus, finger/Tubiana stats, and `[@PMID:...]` tags | file+script | `python -c "from pathlib import Path; assert Path('reports/dupuytren/dissertation_report.md').stat().st_size > 15000"` | ✅ | ⬜ pending |
| 03-01-02 | 01 | 1 | SYNT-01 | — | Chapters 3–4 + Conclusion of `dissertation_report.md` appended with all treatment methods (pros/cons) and 1–10 yr recurrence matrices | file+script | `python -c "from pathlib import Path; assert Path('reports/dupuytren/dissertation_report.md').stat().st_size > 35000"` | ✅ | ⬜ pending |
| 03-02-01 | 02 | 1 | SYNT-02 | — | `reports/dupuytren/executive_summary.md` generated with patient profile, affected fingers/stages, etiology/pathogenesis, methods pros/cons, and recurrence rates | file+script | `python -c "from pathlib import Path; assert Path('reports/dupuytren/executive_summary.md').stat().st_size > 12000"` | ✅ | ⬜ pending |
| 03-02-02 | 02 | 1 | SYNT-03 | — | 5 clinical modules in `reports/dupuytren/knowledge_base/` + `kb_index.json` created | file+script | `python -c "from pathlib import Path; assert len(list(Path('reports/dupuytren/knowledge_base').glob('*.md'))) >= 5"` | ✅ | ⬜ pending |
| 03-03-01 | 03 | 2 | SYNT-01, SYNT-02, SYNT-03 | — | `src/verify_reports.py` compiles numbered `[1]..[N]` dissertation bibliography from SQLite and passes Zero-Tolerance citation & `ru-medical-humanizer` audit | integration | `uv run src/verify_reports.py --compile-bibliography --verify` | ✅ | ⬜ pending |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready
