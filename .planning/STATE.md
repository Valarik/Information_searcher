---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Профиль хирургических осложнений и клиническая де-ИИзация выводов
status: planning
stopped_at: Phase 17 context gathered
last_updated: "2026-11-17T18:12:00.000Z"
last_activity: 2026-11-17
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
Plan: Not started (context locked in `17-CONTEXT.md`)
Status: Ready to plan (`/gsd-plan-phase 17`)
Last activity: 2026-11-17 — Phase 17 context gathered (`D-01..D-09`)

Progress: `░░░░░░░░░░` 0%

## Accumulated Context

### Decisions

- **[v1.x]**: PRISMA-триаж + табличная Map-Reduce экстракция в SQLite вместо слепого RAG; 3 режима отчета + чистый OpenXML экспорт `.docx`.
- **[v2.0 Scope]**: Обновляем только код движка (`src/`, `app.py`, `tests/`) и агентские скиллы (`.agent/skills/`) для будущих нозологий; готовые папки `prom`, `metroplasty_pregnancy`, `trigger_finger` не пересобираются и сохраняют 100% обратную совместимость в UI.
- **[Phase 17 — D-01..D-03]**: Отдельный проход по осложнениям включен по умолчанию (`surgical_focus: true`), гибридная сборка запросов (`complications_queries` или автогенерация), сырой кэш `pubmed_complications.json` / `europepmc_complications.json` и маркер провенанса в `articles.sources`.
- **[Phase 17 — D-04..D-06]**: Двухконтурный учет (`N >= 20`, `Tier 1–3` для частотного профиля против казуистики `Tier 4`), комбинированный тег `complications_safety` и повышенный приоритет скачивания Full-Text XML в `src/triage.py`.
- **[Phase 17 — D-07..D-09]**: Таблица `extracted_complications` с двойной осью тяжести (`Clavien–Dindo` + `reversibility`) и полем `event_class` (`true_complication` vs `transient_postop_sequela`, без дублирования рецидивов); агрегация в `kb_index.json` (`frequent_complications >= 1%` + `rare_critical_red_flags < 1%`) с полной обратной совместимостью с базами `v1.x`.
- **[v2.0 Humanizer]**: Уход от искусственных ИИ-выводов «метод 1 → группа 1, метод 2 → группа 2» к модели конкурирующих сквозных методик и клинических компромиссов (`clinical_decision_nuances`) со структурным линтером в `src/verify_reports.py`.

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-11-17T18:12:00Z
Stopped at: Phase 17 context gathered
Resume file: `.planning/phases/INFO-SEARCH-17-prisma/17-CONTEXT.md`
