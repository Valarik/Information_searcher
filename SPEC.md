# Архитектурная спецификация проекта `Information_searcher`

Универсальный исследовательский движок для сбора, PRISMA-фильтрации, структурированной агентской экстракции и генерации аналитических медицинских обзоров по нозологиям в трех форматах.

## 1. Структура проекта

```text
Information_searcher/
├── .agent/
│   └── skills/
│       ├── ru-medical-humanizer/         # Правила де-ИИзации русского медицинского текста
│       └── nosology-research-pipeline/   # Протокол фаз сбора, экстракции и синтеза
├── configs/
│   └── dupuytren.yaml                    # Конфигурация поиска и кластеров по контрактуре Дюпюитрена
├── src/
│   ├── schema.py                         # Инициализация SQLite БД и таблиц экстракции
│   ├── harvester.py                      # Сборщик (PubMed, Europe PMC, OpenAlex, ClinicalTrials)
│   ├── triage.py                         # Дедупликация, ранжирование (Tier 1-4), тегирование кластеров
│   └── exporter.py                       # Сборка отчетов в 3 режимах и экспорт таблиц
├── data/
│   └── dupuytren/
│       ├── raw/                          # Сырые JSON-ответы API и полнотекстовые XML из Europe PMC
│       └── literature.db                 # Единая SQLite база корпуса и таблиц экстракции
├── reports/
│   └── dupuytren/
│       ├── dissertation_report.md        # Вариант 1: Научная работа диссертационного уровня
│       ├── executive_summary.md          # Вариант 2: Краткое аналитическое содержание
│       └── knowledge_base/               # Вариант 3: Структурированная внутренняя база знаний
└── app.py                                # Веб-интерфейс (переключатель режимов, фильтры БД, таблицы)
```

## 2. Схема базы данных (`literature.db`)

1. **`articles`** — основной реестр публикаций после дедупликации:
   - `id` (PK), `pmid`, `pmcid`, `doi`, `openalex_id`
   - `title`, `abstract`, `journal`, `pub_year`, `pub_date`, `authors`
   - `pub_types` (JSON: RCT, Meta-Analysis, Review, Journal Article и др.)
   - `evidence_tier` (`1` — высший: метаанализы/РКИ; `2` — когорты/GWAS/scRNA-seq; `3` — ретроспективные серии/in vitro/обзоры; `4` — кейс-репорты/письма)
   - `clusters` (JSON: `etiology`, `pathogenesis`, `conservative`, `surgical`, `outcomes`)
   - `cited_by_count`, `is_open_access`, `has_fulltext_xml`, `fulltext_path`
   - `source_flags` (в каких базах найдена: PubMed, EuropePMC, OpenAlex)

2. **`clinical_trials`** — реестр клинических исследований из ClinicalTrials.gov:
   - `nct_id` (PK), `brief_title`, `official_title`, `overall_status`, `phase`, `study_type`
   - `interventions`, `enrollment`, `start_date`, `completion_date`, `has_results`, `summary`

3. **`extracted_clinical_evidence`** — таблица структурированной экстракции клинических работ (заполняется субагентами во 2-й фазе):
   - `article_id`, `pmid`, `first_author_year`, `study_design`, `evidence_tier`
   - `n_patients`, `n_hands_or_rays`, `tubiana_stage_or_baseline`
   - `intervention_group`, `comparator_group`, `followup_months`
   - `mcp_correction`, `pip_correction`
   - `recurrence_definition`, `recurrence_rate_overall`, `recurrence_rate_mcp`, `recurrence_rate_pip`
   - `complications_summary`, `complications_rate`, `patient_reported_outcomes` (DASH, QuickDASH, URAM, SHS)
   - `key_conclusion`

4. **`extracted_mechanisms`** — таблица экстракции по этиологии, генетике и молекулярному патогенезу:
   - `article_id`, `pmid`, `first_author_year`, `category` (`genetics_gwas`, `epigenetics`, `myofibroblast_signaling`, `ecm_biomechanics`, `immunology`, `epidemiology_risk`)
   - `targets_genes_pathways` (например: `WNT7B`, `SFRP4`, `TGF-b1`, `TNF`, `YAP/TAZ`, `MMP14`, `COL1A1/COL3A1`)
   - `study_model` (GWAS, scRNA-seq, биоптаты узелков/тяжей пациентов, культура фибробластов, популяционная когорта)
   - `sample_size`, `quantitative_findings` (OR, p-value, кратность изменения экспрессии), `mechanism_summary`

## 3. Три режима генерации отчета

Пользователь может переключаться между тремя представлениями в интерфейсе `app.py` или читать их как отдельные файлы:
1. **Диссертационный режим (`dissertation_report.md`)** — развернутый критический обзор литературы с полным методологическим разбором выборок, биологических механизмов, сравнением хирургических и малоинвазивных методик и строгим списком литературы.
2. **Краткое содержание (`executive_summary.md`)** — плотная аналитическая сводка с ключевыми цифрами, главными сдвигами в подходах за 2016–2026 гг. и итоговыми сравнительными таблицами.
3. **Внутренняя база знаний (`knowledge_base/`)** — гранулярный справочник по молекулярным мишеням, факторам риска, каждому методу лечения и ключевым РКИ.
