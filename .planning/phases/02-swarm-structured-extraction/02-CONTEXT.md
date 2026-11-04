# Phase 2: Роевая структурированная экстракция - Context

**Gathered:** 2026-11-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Параллельная структурированная экстракция данных из ранжированного корпуса контрактуры Дюпюитрена (`1 775` статей и `80` протоколов `ClinicalTrials.gov` в `data/dupuytren/literature.db`) по 4 тематическим кластерам с заполнением таблиц `extracted_mechanisms` и `extracted_clinical_evidence` и формированием проверочных аналитических досье `data/dupuytren/extractions/cluster_1..4.md`.

Написание чистовых текстов трех вариантов отчета относится к Фазе 3, разработка веб-интерфейса Streamlit — к Фазе 4.
</domain>

<decisions>
## Implementation Decisions

### Глубина охвата корпуса (`Tier 1–4`) при экстракции
- **D-01 (Гибридный глубокий охват корпуса):**
  - **Ядро глубокого разбора (100%):** Все статьи уровней `Tier 1` (`181` шт.) и `Tier 2` (`192` шт.) — суммарно `373` работы, а также все `233` статьи `Tier 1–3`, для которых скачаны полнотекстовые XML из Europe PMC (`data/dupuytren/raw/fulltext_xml/`).
  - **Целевой добор из `Tier 3` и `Tier 4`:** Оригинальные работы `Tier 3` по специализированным хирургическим и экспериментальным нишам (техника WALANT, липофилинг / инъекции стромально-васкулярной фракции, дистракционные внешние фиксаторы ПМФС `Digit Widget`, новые молекулярные мишени *in vitro* / *ex vivo*) и `23` размеченных клинических случая редких/тяжелых осложнений из `Tier 4` (`Rare Complication Case [D-05]`).
  - **Сплошная индексация остальных серий `Tier 3`:** Для остальных оригинальных серий `Tier 3` выполняется автоматизированное табличное извлечение базовых параметров (автор/год, дизайн, размер выборки `N`, вмешательство, ключевой исход) в БД, при этом нарративные обзоры (`133` статьи с меткой `Narrative Review [D-06]`) используются только для перекрестной проверки полноты библиографии и не смешиваются с первичными данными.

### Стандартизация критериев рецидива и углов контрактуры (ПФС vs ПМФС)
- **D-02 (Раздельная стратификация по критерию рецидива, суставу и сроку наблюдения):**
  - В поле `recurrence_definition` таблицы `extracted_clinical_evidence` обязательно фиксируется определение рецидива, использованное авторами: консенсусное определение Kan et al. (`≥20°` нарастания контрактуры в пролеченном суставе с пальпируемым тяжем), порог `≥30°`, необходимость повторного вмешательства (`re-intervention`) или авторское определение.
  - Исходы и частоты рецидивов извлекаются и хранятся **раздельно** для пястно-фалангового сустава (`mcp_outcome`, `recurrence_rate_mcp`) и проксимального межфалангового сустава (`pip_outcome`, `recurrence_rate_pip`).
  - Сроки наблюдения (`followup_months`) при сведении группируются по трем клиническим горизонтам: краткосрочный (`≤12 мес.`), среднесрочный (`24–36 мес.`) и отдаленный (`≥60 мес. / 5–10 лет`).

### Коллагеназа (CCH), таргетная терапия и интеграция с ClinicalTrials.gov
- **D-03 (Полный разбор CCH и сшивка `NCT ID <-> PMID`):**
  - Коллагеназа *Clostridium histolyticum* (CCH / Xiapex / Xiaflex) разбирается в полном объеме за весь период 2016–2026 гг. наравне с игольной апоневротомией (PNF) и ограниченной фасциэктомией (LF) — включая прямые сравнительные РКИ, 5-летние результаты, фармакоэкономику и контекст коммерческого отзыва с рынков ЕС и Великобритании в 2020 г.
  - Все `80` протоколов из таблицы `clinical_trials` (`ClinicalTrials.gov`) перекрестно связываются с опубликованными статьями в `articles` по `NCT ID` / заголовкам / авторам; неопубликованные, активные и завершенные испытания новых модальностей (анти-TNF адалимумаб / RIDD trial, пирфенидон, вертепорфин, коллагеназа нового поколения, УВТ) выносятся в отдельную сводную таблицу клинического пайплайна.

### Формат промежуточных артефактов роевой экстракции
- **D-04 (Двойной выход: таблицы SQLite + 4 проверочных Markdown-досье):**
  - Каждый из 4 кластерных потоков экстракции записывает структурированные строки в `data/dupuytren/literature.db` (`extracted_mechanisms` и `extracted_clinical_evidence`) И одновременно генерирует детальное проверочное аналитическое досье в `data/dupuytren/extractions/`:
    1. `data/dupuytren/extractions/cluster_1_etiology_genetics.md` (эпидемиология, факторы риска, локусы GWAS, Wnt-сигналинг, эпигенетика, диатез Дюпюитрена).
    2. `data/dupuytren/extractions/cluster_2_pathogenesis.md` (миофибробласты, TGF-β1/Smad, механотрансдукция YAP/TAZ, иммунное микроокружение/TNF, матрикс, scRNA-seq/мультиомика).
    3. `data/dupuytren/extractions/cluster_3_conservative_minimally_invasive.md` (игольная апоневротомия PNF, коллагеназа CCH, лучевая терапия, адалимумаб, инъекции стероидов, УВТ, ортезирование и реабилитация, матрица `ClinicalTrials.gov`).
    4. `data/dupuytren/extractions/cluster_4_surgical_and_outcomes.md` (ограниченная/селективная фасциэктомия, дермофасциэктомия, открытая ладонь McCash, кожная пластика, WALANT, липографтинг, внешние фиксаторы, сравнительная матрица рецидивов 1–10 лет по ПФС/ПМФС, профиль осложнений и PROMs: DASH/QuickDASH/URAM/SHQ).

### Claude's Discretion
- Техническая реализация скриптов автоматизированного парсинга XML/абстрактов (`src/extractor.py`) в сочетании с глубоким агентским разбором топ-работ `Tier 1–2` и полных XML.
- Идемпотентная очистка/обновление таблиц `extracted_mechanisms` и `extracted_clinical_evidence` при повторном прогоне.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `SPEC.md` — Архитектура проекта, 4 тематических кластера и структура таблиц экстракции.
- `configs/dupuytren.yaml` — Конфигурация нозологии и ключевые слова 5 кластеров.
- `src/schema.py` — Схема SQLite (`articles`, `clinical_trials`, `extracted_clinical_evidence`, `extracted_mechanisms`).
- `.planning/phases/01-harvesting-and-prisma-triage/01-CONTEXT.md` — Решения `D-01..D-08` Фазы 1 (правила `Tier 4`, нарративных обзоров и препринтов).
- `reports/dupuytren/prisma_stats.md` — Точная статистика собранного корпуса (`1 775` статей, `233` полнотекстовых XML, `80` РКИ).
- `.agent/skills/nosology-research-pipeline/SKILL.md` — Методология роевой экстракции и верификации PMID.
- `.agent/skills/ru-medical-humanizer/SKILL.md` — Требования к научному стилю при написании аналитических досье.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/schema.py`: Функция `init_db()` уже создает целевые таблицы `extracted_clinical_evidence` (23 колонки, включая `mcp_outcome`, `pip_outcome`, `recurrence_definition`, `recurrence_rate_mcp`, `recurrence_rate_pip`, `complications_summary`, `prom_scores`) и `extracted_mechanisms` (12 колонок, включая `category`, `targets_genes_pathways`, `study_model`, `sample_size`, `quantitative_findings`, `therapeutic_implication`).
- `data/dupuytren/literature.db`: Содержит `1 775` включенных статей (`Tier 1`: 181, `Tier 2`: 192, `Tier 3`: 942, `Tier 4`: 460) и `80` записей `clinical_trials`.
- `data/dupuytren/raw/fulltext_xml/`: Содержит `233` полнотекстовых JATS XML файла (`PMC*.xml`), готовых для парсинга секций `Methods`, `Results` и табличных данных (`<table>`).

### Integration Points
- Скрипт `src/extractor.py` (и/или кластерные модули экстракции) должен читать записи из `data/dupuytren/literature.db` и XML из `data/dupuytren/raw/fulltext_xml/`, заполнять `extracted_mechanisms` и `extracted_clinical_evidence`, и сохранять проверочные досье `data/dupuytren/extractions/cluster_1..4.md`.
</code_context>

<specifics>
## Specific Ideas

- В каждом из 4 аналитических досье (`cluster_1..4.md`) обязательно выделить раздел **«Противоречия и дискуссионные зоны 2016–2026»** (например: спор о роли травмы/вибрации, противоречивые данные по эффективности ночного шинирования, расхождения в 5-летних рецидивах между CCH, PNF и фасциэктомией в зависимости от порога `≥20°` vs повторной операции).
</specifics>

<deferred>
## Deferred Ideas

None — все обсужденные вопросы входят в границы Фазы 2.
</deferred>

---
*Phase: 02-swarm-structured-extraction*
*Context gathered: 2026-11-04*
