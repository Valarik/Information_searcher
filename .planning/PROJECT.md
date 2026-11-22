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
- ✓ **COMP-01..04**: Гибридный API-сбор по осложнениям лечения (`src/harvester.py`), двухконтурный PRISMA-триаж `complications_safety` и приоритет Full-Text XML (`src/triage.py`), реляционная таблица `extracted_complications` с двойной осью `Clavien–Dindo`/`CTCAE` + `reversibility` (`src/schema.py`, `src/extractor_common.py`) и агрегатор/валидатор `frequent_complications` + `rare_critical_red_flags` (`src/universal_schema.py`) с read-only защитой баз `v1.x` — Validated in Phase 17 (`17-VERIFICATION.md`, `11/11 pytest`)
- ✓ **HUM2-01..03**: Скиллы `ru-medical-humanizer v2.0` и `nosology-research-pipeline v2.0` (запрет «коробочных» выводов, модель сквозных конкурирующих методик и баланс прозы `bold_lead_bullet_ratio <= 0.35`), контракт `clinical_decision_nuances` + `validate_kb_v2()` в `src/universal_schema.py`, структурный анти-ИИ линтер `check_humanizer_v2_structure()` и Zero-Tolerance кросс-проверка `kb_index.json` `evidence_pmids` в `src/verify_reports.py` — Validated in Phase 18 (`18-VERIFICATION.md`, `17/17 pytest`)
- ✓ **UI-02, EXPORT-02**: Подвкладки `2.5` (`Clavien–Dindo`, 2 Plotly-графика, фильтры, Red Flags, `v1.x` fallback) и `2.6` (`clinical_decision_nuances`), таблица `extracted_complications` во вкладке 3, конфигуратор `surgical_focus` с живым предпросмотром `build_complications_queries()` и `--read-only` аудитом во вкладке 4 (`app.py`), структурированные приложения `v2.0` + строгая ECMA-376 вёрстка таблиц + защита `FROZEN_V1_NOSOLOGIES` (`src/docx_exporter.py`), и сквозной комплект автотестов `tests/test_v2_engine.py` + `app.py --self-test` с проверкой нулевых мутаций 3 замороженных нозологий `v1.x` — Validated in Phase 19 (`19-VERIFICATION.md`, `14/14 must-haves`, `25/25 pytest`)

### Active (Milestone v2.0)

Все требования Milestone `v2.0` (`9/9`: `COMP-01..04`, `HUM2-01..03`, `UI-02`, `EXPORT-02`) выполнены и верифицированы. Готово к архивации майлстоуна или запуску новых нозологий по стандарту `v2.0`.

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
| Отдельный проход API-поиска и таблица `extracted_complications` (`Clavien–Dindo`) | В общих поисковых запросах по нозологии работы по ятрогенным и редким/поздним хирургическим осложнениям теряются или смешиваются с первичными исходами | ✓ Validated in Phase 17 |
| Замена жесткой матрицы `1 стадия = 1 метод` на модель сквозных методик и перекрывающихся показаний (`clinical_decision_nuances`) | В реальной хирургии базовые операции (например, открытый и чрескожный/УЗ-релиз) перекрывают почти весь спектр стадий, конкурируя по нюансам оснащения, рубца и опыта хирурга | ✓ Validated in Phase 18 |
| Модернизация только движка и скиллов без пересборки прошлых отчетов | Экономит квоту API и сохраняет проверенные артефакты `v1.x`, закладывая стандарт `v2.0` для всех новых запусков | ✓ Validated in Phases 17–19 (0 mutations across `prom`, `metroplasty_pregnancy`, `trigger_finger`) |
| Единые приложения `v2.0` в `executive_summary.docx` и `full_clinical_dossier.docx` + строгая ECMA-376 вёрстка таблиц | Гарантирует идентичность сводок осложнений (`Clavien–Dindo`) и клинических компромиссов между CLI и UI без дублирования текста диссертации и с читаемым переносом многостраничных таблиц | ✓ Validated in Phase 19 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions

---
*Last updated: 2026-11-22 — Phase 19 complete and verified (UI-02, EXPORT-02 validated; Milestone v2.0 9/9 complete)*
