---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Профиль хирургических осложнений и клиническая де-ИИзация выводов
status: planning
stopped_at: Milestone v2.0 initialized (Phases 17-19 defined)
last_updated: "2026-11-13T18:10:00.000Z"
last_activity: 2026-11-13
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-11-13)

**Core value:** Доказательный, 100% трассируемый по `PMID / DOI / NCT ID` синтез клинической и фундаментальной литературы без галлюцинаций, канцелярита и структурных ИИ-штампов, отражающий реальную неоднозначность хирургического и терапевтического выбора.
**Current focus:** Milestone `v2.0` — Phase 17: Сбор, PRISMA-триаж и реляционная схема частых осложнений лечения

## Current Position

Phase: 17 of 19 (1 of 3 in Milestone v2.0)
Plan: Not started
Status: Ready to plan (`/gsd-plan-phase 17`)
Last activity: 2026-11-13 — Milestone v2.0 initialized

Progress: `░░░░░░░░░░` 0%

## Accumulated Context

### Decisions

- **[v1.x]**: PRISMA-триаж + табличная Map-Reduce экстракция в SQLite вместо слепого RAG; 3 режима отчета + чистый OpenXML экспорт `.docx`.
- **[v2.0 Scope]**: Обновляем только код движка (`src/`, `app.py`, `tests/`) и агентские скиллы (`.agent/skills/`) для будущих нозологий; готовые папки `prom`, `metroplasty_pregnancy`, `trigger_finger` не пересобираются и сохраняют 100% обратную совместимость в UI.
- **[v2.0 Complications]**: Отдельный API-проход по осложнениям (`complications_queries`) + тег `complications_safety` + таблица SQLite `extracted_complications` (`Clavien–Dindo`, `%`, обратимость, профилактика/лечение) + графики в `app.py` и таблицы в `.docx`.
- **[v2.0 Humanizer]**: Уход от искусственных ИИ-выводов «метод 1 → группа 1, метод 2 → группа 2» к модели конкурирующих сквозных методик и клинических компромиссов (`clinical_decision_nuances`) со структурным линтером в `src/verify_reports.py`.

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-11-13T18:10:00Z
Stopped at: Milestone v2.0 roadmap ready for approval / Phase 17 planning
Resume file: `.planning/ROADMAP.md`
