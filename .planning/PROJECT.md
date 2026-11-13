# Information Searcher: Универсальная платформа доказательного синтеза по медицинским нозологиям

## What This Is

Универсальный конфигурационно-зависимый конвейер на Python + SQLite + Streamlit + OpenXML (`.docx`), который по YAML-профилю нозологии (`configs/<id>.yaml`) собирает литературу из `PubMed`, `Europe PMC`, `OpenAlex` и `ClinicalTrials.gov`, проводит автоматический PRISMA-скрининг (`Tier 1–4`), извлекает структурированные патогенетические и клинические данные в реляционную базу `data/<id>/literature.db` и формирует верифицированные отчеты в 3 режимах (`dissertation_report`, `executive_summary`, `knowledge_base`) в форматах `.md`, `.html` и `.docx`.

## Current Milestone: v2.0 Профиль хирургических осложнений и клиническая де-ИИзация выводов

**Goal:** Модернизировать код движка, схему БД, верификатор, веб-интерфейс и агентские скиллы для будущих нозологий: внедрить прицельный сбор и табличную аналитику частых хирургических осложнений (`Clavien–Dindo`) и устранить шаблонные «коробочные» выводы ИИ в пользу реальной клинической логики перекрывающихся показаний и компромиссов (без пересборки ранее выпущенных отчетов `v1.x`).

**Target features:**
- Прицельный API-сбор публикаций по интра- и послеоперационным осложнениям (`complications_queries`), тегирование в PRISMA-триаже и новая таблица SQLite `extracted_complications` (частота `%`, тяжесть `Clavien–Dindo`, обратимость, анатомический субстрат, профилактика и лечение).
- Глубокая структурная хуманизация (`ru-medical-humanizer v2.0` + `clinical_decision_nuances` + структурный линтер в `src/verify_reports.py`): отказ от искусственной схемы «метод 1 — строго для стадии А, метод 2 — для стадии Б» в пользу анализа сквозных базовых методик, конкурирующих на всем спектре стадий со своими практическими нюансами.
- Визуализация профиля осложнений (`Clavien–Dindo`, обратимые vs стойкие осложнения) и матрицы клинических компромиссов в `app.py` и `src/docx_exporter.py` с полной обратной совместимостью для существующих нозологий `v1.x` (`prom`, `metroplasty_pregnancy`, `trigger_finger`).

## Core Value

Доказательный, 100% трассируемый по `PMID / DOI / NCT ID` синтез клинической и фундаментальной литературы без галлюцинаций, канцелярита и структурных ИИ-штампов, отражающий реальную неоднозначность хирургического и терапевтического выбора.

## Requirements

### Validated

- ✓ Локальная установка фреймворка GSD и создание базовых скиллов `ru-medical-humanizer` и `nosology-research-pipeline` — Milestone 1 (Phase 0)
- ✓ Универсальный сборщик `src/harvester.py`, PRISMA-триаж `src/triage.py`, ядро экстракции `src/extractor_common.py`, анти-галлюцинаторный аудит `src/verify_reports.py` и веб-платформа `app.py` — Milestone 1–2 (Phases 1–8)
- ✓ Выпуск изолированных нозологических баз и отчетов `v1.x`: `prom` (O42), `metroplasty_pregnancy` (O34.2/O71/Q51), `trigger_finger` (M65.3) — Milestones 2–4 (Phases 5–16)
- ✓ Чистый OpenXML-экспортер `src/docx_exporter.py` с версткой диссертационных отчетов, кратких руководств и сводных досье в `.docx` — Milestone 4 (`EXPORT-01`)

### Active (Milestone v2.0)

- [ ] **COMP-01..04**: API-сбор по осложнениям лечения, PRISMA-тегирование `complications_safety`, таблица `extracted_complications` (`Clavien–Dindo`) и секция `frequent_complications` в `kb_index.json`
- [ ] **HUM2-01..03**: Обновление `ru-medical-humanizer` и `nosology-research-pipeline` против «коробочных» выводов, внедрение схемы `clinical_decision_nuances` (сквозные конкурирующие методы + нюансы выбора) и структурного анти-ИИ линтера в `src/verify_reports.py`
- [ ] **UI-02, EXPORT-02**: Графики осложнений `Clavien–Dindo` и витрина клинических компромиссов в `app.py` + поддержка таблиц осложнений в `.docx` с сохранением обратной совместимости со старыми нозологиями `v1.x`

### Out of Scope

- Пересборка и перезапись уже готовых отчетов `v1.x` (`prom`, `metroplasty_pregnancy`, `trigger_finger`) в рамках этого майлстоуна — изменения вносятся в движок, схемы, верификатор, UI и скиллы для всех последующих нозологий.
- Парсинг закрытых пейволлов в обход официальных API (`NCBI E-utilities`, `Europe PMC`, `OpenAlex`, `ClinicalTrials.gov`).

## Constraints

- **Обратная совместимость (`v1.x` + `v2.0`)**: `app.py`, `src/universal_schema.py` и `src/docx_exporter.py` обязаны корректно открывать уже существующие базы `prom`, `metroplasty_pregnancy`, `trigger_finger` (где нет таблицы `extracted_complications` и новых полей `v2.0`) и одновременно требовать полный стандарт `v2.0` при проверке новых нозологий (`--schema-version v2`).
- **Де-ИИзация логики и стиля**: никаких механических выводов «1 → А, 2 → Б, 3 → В», никаких шаблонных комплиментов в диалоге и никакого доминирования списков `- **Жирный тезис:** ...` над связной аналитической прозой.
- **Трассируемость**: каждая частота осложнения и каждый клинический нюанс выбора обязаны ссылаться на верифицированный `PMID / PMCID / NCT ID` в SQLite.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Отдельный проход API-поиска и таблица `extracted_complications` (`Clavien–Dindo`) | В общих поисковых запросах по нозологии работы по ятрогенным и редким/поздним хирургическим осложнениям теряются или смешиваются с первичными исходами | — Pending (v2.0) |
| Замена жесткой матрицы `1 стадия = 1 метод` на модель сквозных методик и перекрывающихся показаний (`clinical_decision_nuances`) | В реальной хирургии базовые операции (например, открытый и чрескожный/УЗ-релиз) перекрывают почти весь спектр стадий, конкурируя по нюансам оснащения, рубца и опыта хирурга | — Pending (v2.0) |
| Модернизация только движка и скиллов без пересборки прошлых отчетов | Экономит квоту API и сохраняет проверенные артефакты `v1.x`, закладывая стандарт `v2.0` для всех новых запусков | ✓ Confirmed |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions

---
*Last updated: 2026-11-13 — Milestone v2.0 initialized*
