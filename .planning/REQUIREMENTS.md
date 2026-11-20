# Requirements: Information Searcher — Milestone v2.0 (Engine & Skills Upgrade)

**Defined:** 2026-11-13
**Core Value:** Доказательный, верифицируемый по `PMID / DOI / NCT ID` синтез клинической и фундаментальной литературы без галлюцинаций, канцелярита и шаблонных «коробочных» ИИ-выводов, с полным учетом профиля хирургических осложнений и реальных клинических компромиссов.

---

## Validated Baseline (Milestones 1–4 / v1.x)

- [x] **HARV-01..04**: Универсальный сборщик `src/harvester.py`, дедупликация в SQLite, PRISMA-триаж `src/triage.py` и загрузка полнотекстовых XML Europe PMC.
- [x] **EXTR-01..04**: Кластерная табличная экстракция патогенеза (`extracted_mechanisms`) и клинической эффективности (`extracted_clinical_evidence`).
- [x] **SYNT-01..03**: Синтез отчетов в 3 режимах (`dissertation`, `executive_summary`, `knowledge_base`) с анти-галлюцинаторным контролем `src/verify_reports.py`.
- [x] **UI-01**: Мульти-нозологическое веб-приложение `app.py` (4 вкладки, автотест `--self-test`).
- [x] **EXPORT-01**: Академическая компиляция отчетов и сводного клинического досье в формат MS Word (`.docx`) через `src/docx_exporter.py`.

---

## Milestone v2.0 Requirements

### 1. Сбор и структурированная экстракция частых осложнений лечения (`COMP`)

- [x] **COMP-01**: Конфигурация `configs/<id>.yaml` и форма создания нозологии в `app.py` поддерживают флаг `surgical_focus: true/false` и блок целевых запросов `complications_queries` (`pubmed`, `europepmc`), а `src/harvester.py` выполняет отдельный проход выгрузки публикаций по интра- и послеоперационным осложнениям (либо автоматически генерирует подзапрос `Postoperative Complications / Intraoperative Complications / adverse effects` для хирургических нозологий).
- [x] **COMP-02**: Скрипт `src/triage.py` размечает публикации по безопасности и осложнениям тегом `complications_safety`, учитывает их в `prisma_stats.md` и включает релевантные работы по хирургическим осложнениям в очередь выгрузки полнотекстовых XML Europe PMC.
- [x] **COMP-03**: Схема `src/schema.py` и ядро `src/extractor_common.py` содержат таблицу `extracted_complications` (поля: `article_id`, `modality`, `complication_name`, `timing_category`, `clavien_dindo_grade`, `frequency_pct`, `frequency_num`, `reversibility`, `time_window`, `anatomical_substrate`, `prevention_and_management`, `sample_size`, `pmid`) и функции записи/чтения с безопасной миграцией (`CREATE TABLE IF NOT EXISTS`) для обратной совместимости с базами `v1.x`.
- [x] **COMP-04**: Универсальный адаптер `src/universal_schema.py` поддерживает в `kb_index.json` структурированный массив `frequent_complications` (с проверкой обязательных полей в режиме `v2.0` и мягким fallback-режимом для ранее собранных нозологий `v1.x`).

### 2. Глубокая структурная и клиническая хуманизация (`HUM2`)

- [x] **HUM2-01**: Скилл `.agent/skills/ru-medical-humanizer/SKILL.md` обновлен до `v2.0`: зафиксирован запрет на искусственную линейную маршрутизацию в выводах (*«это лечение для 1, это для 2, это для 3»*), описан стандарт подачи **сквозных конкурирующих методик** (подходящих почти ко всему спектру стадий, но различающихся практическими нюансами, рисками и требованиями к оснащению/опыту) и введены жесткие правила баланса связной прозы против маркированных списков.
- [x] **HUM2-02**: Скилл `.agent/skills/nosology-research-pipeline/SKILL.md` и контракт `kb_index.json` (`v2.0`) включают блок `clinical_decision_nuances` (`universal_workhorse_modalities`, `overlapping_indications_and_gray_zones`, `strict_niche_or_salvage_indications`) и обязательный раздел разбора частых осложнений для всех будущих нозологий.
- [x] **HUM2-03**: Верификатор `src/verify_reports.py` оснащен структурным анти-ИИ линтером `v2.0`: расширенный словарь речевых и логических штампов ИИ, автоматический подсчет доли буллитов с жирным зачином (`bold-lead bullet ratio`) в диссертационном отчете, блокировка механических «коробочных» выводов в финальной главе и проверка наличия анализа осложнений и перекрывающихся показаний для отчетов `v2.0`.

### 3. Визуализация в `app.py`, экспорт `.docx` и автотестирование движка (`UI / EXPORT`)

- [ ] **UI-02**: Веб-интерфейс `app.py` отображает интерактивный профиль частых осложнений (`Clavien–Dindo`, частота по методикам, обратимость vs стойкий дефицит, тактика коррекции), таблицу `extracted_complications` в PRISMA-навигаторе с выгрузкой в `.csv` и блок клинических нюансов/перекрывающихся показаний (`clinical_decision_nuances`), не ломая рендеринг готовых нозологий `v1.x`.
- [ ] **EXPORT-02**: Экспортер `src/docx_exporter.py` и набор автотестов (`tests/test_v2_engine.py` + `uv run app.py --self-test`) проверяют полный цикл работы движка `v2.0` (таблица осложнений, линтер де-ИИзации выводов, генерация `.docx` и обратная совместимость с существующими папками `prom`, `metroplasty_pregnancy`, `trigger_finger`).

---

## Future / Deferred Requirements

- **AUTO-01**: Периодический мониторинг новых публикаций по расписанию (`Living Systematic Review`).
- **RETRO-01**: Опциональная пересборка архивных/ранее созданных нозологий `v1.x` по стандарту `v2.0` (выполняется только по отдельному запросу пользователя).

## Out of Scope

| Feature | Reason |
|---------|--------|
| Автоматическая перезапись готовых отчетов `prom`, `metroplasty_pregnancy`, `trigger_finger` в рамках Milestone v2.0 | По решению пользователя обновляется только движок и скиллы для будущих нозологий |
| Обход закрытых пейволлов | Используются исключительно официальные API (`PubMed`, `Europe PMC`, `OpenAlex`, `ClinicalTrials.gov`) |

---

## Traceability (Milestone v2.0)

| Requirement | Phase | Status |
|-------------|-------|--------|
| COMP-01 | Phase 17 | Complete |
| COMP-02 | Phase 17 | Complete |
| COMP-03 | Phase 17 | Complete |
| COMP-04 | Phase 17 | Complete |
| HUM2-01 | Phase 18 | Complete |
| HUM2-02 | Phase 18 | Complete |
| HUM2-03 | Phase 18 | Complete |
| UI-02 | Phase 19 | Pending |
| EXPORT-02 | Phase 19 | Pending |

**Coverage:**

- Milestone v2.0 requirements: `9` total
- Mapped to phases: `9` (`100%`)
- Unmapped: `0`

---
*Last updated: 2026-11-13 — Milestone v2.0 requirements defined*
