---
name: nosology-research-pipeline
description: >-
  Универсальный многофазный пайплайн сбора, PRISMA-скрининга, структурированной
  экстракции и аналитического синтеза медицинской литературы по любой нозологии
  с использованием API PubMed, Europe PMC, OpenAlex и ClinicalTrials.gov.
---

# Пайплайн глубокого исследования нозологии (Nosology Research Pipeline)

Стандарт работы агентов при создании систематических аналитических отчетов по медицинским нозологиям за заданный горизонт лет.

## Архитектура пайплайна (5 фаз)

### Фаза 0: Конфигурация нозологии (`configs/<nosology>.yaml`)
Перед запуском поиска формируется конфигурационный файл нозологии:
- `nosology_id`, название (RU / EN), коды МКБ-10 / МКБ-11, MeSH-дескрипторы.
- Временной диапазон (например, `2016-01-01` — `2026-12-31`).
- Поисковые запросы для каждой базы:
  - **PubMed:** MeSH + Title/Abstract синонимы.
  - **Europe PMC:** запрос для выгрузки метаданных и открытых полных текстов (`HAS_FT:y` / `OPEN_ACCESS:y`).
  - **OpenAlex:** разрешение концепта/топика через ID и фильтрация по цитируемости и годам.
  - **ClinicalTrials.gov:** поиск клинических исследований по условию (`condition`).
- Тематические кластеры и схема полей для экстракции.

### Фаза 1: Сбор и PRISMA-картирование (`src/harvester.py`)
1. Выгрузка всех найденных публикаций из 4 источников через штатные API-обертки.
2. Загрузка в единую базу `data/<nosology>/literature.db` (SQLite):
   - Дедупликация по нормализованному `DOI`, `PMID`, `PMCID` и совпадению нормализованного заголовка + года.
   - Автоматическая классификация по уровню доказательности и типу работы:
     - `Tier 1`: Систематические обзоры, метаанализы, рандомизированные контролируемые исследования (РКИ / RCT), клинические рекомендации.
     - `Tier 2`: Проспективные когортные исследования, сравнительные исследования, GWAS / scRNA-seq / мультиомиксные фундаментальные работы.
     - `Tier 3`: Ретроспективные серии, исследования случай-контроль, экспериментальные работы *in vitro* / *ex vivo*, нарративные обзоры.
     - `Tier 4`: Одиночные клинические случаи (case reports), письма, комментарии, статьи без абстракта.
   - Автоматическая тематическая разметка (множественные теги: `etiology_genetics`, `pathogenesis_molecular`, `treatment_conservative`, `treatment_surgical`, `outcomes_recurrence`, `rehabilitation_complications`).
   - Докачка полнотекстовых XML из Europe PMC для работ `Tier 1` и `Tier 2`, имеющих открытый `PMCID`.

### Фаза 2: Роевая структурированная экстракция (`Extractor Swarm`)
Вместо неструктурированного RAG-поиска корпус делится на тематические домены. На каждый домен запускается специализированный субагент-экстрактор, который читает полнотекстовые XML и абстракты работ `Tier 1–2` (и релевантных `Tier 3`) и записывает структурированные карточки в таблицы базы данных:
- **`extracted_clinical_studies`**: `pmid`, `doi`, `year`, `first_author`, `study_design`, `evidence_tier`, `sample_size_patients`, `sample_size_rays_or_joints`, `stage_classification`, `interventions_compared`, `followup_months`, `recurrence_definition`, `mcp_outcome`, `pip_outcome`, `recurrence_rate`, `complications`, `key_statistical_findings`.
- **`extracted_basic_science`**: `pmid`, `doi`, `year`, `first_author`, `domain` (`genetics`, `epigenetics`, `cell_biology`, `signaling`, `biomechanics`, `immunology`), `genes_or_proteins`, `pathway`, `model_system` (`patient_tissue`, `primary_fibroblasts`, `gwas_cohort`, `scrna_seq`, `animal_model`), `sample_size`, `main_mechanism_finding`, `therapeutic_implication`.
- **`extracted_epidemiology_risk`**: `pmid`, `doi`, `year`, `population_country`, `sample_size`, `prevalence_or_incidence`, `risk_factor`, `effect_size_or_hr` (с 95% ДИ), `notes`.

### Фаза 3: Многорежимный синтез отчета (`Synthesizer`)
На основе таблиц из Фазы 2 генерируются тексты в трех режимах (строго по правилам скилла `ru-medical-humanizer`):
1. `reports/<nosology>/dissertation_report.md` — полный текст диссертационного / монографического уровня.
2. `reports/<nosology>/executive_summary.md` — концентрированное аналитическое резюме.
3. `reports/<nosology>/knowledge_base/` — модульная база знаний (карточки генов, методов лечения, матрица РКИ, клинические алгоритмы).

Каждый численный тезис в отчете обязан иметь ссылку вида `[Автор, Год; PMID: XXXXXXXX]` или `[NCTXXXXXXXX]`, проверяемую по локальной БД.

### Фаза 4: Интерактивный навигатор (`app.py`)
Веб-интерфейс (Streamlit), подключающийся к `data/<nosology>/literature.db` и папке `reports/<nosology>/`:
- Переключатель нозологий и трех режимов чтения отчета.
- PRISMA-статистика и библиометрические графики по годам и типам исследований.
- Интерактивный фильтр по всем статьям корпуса и извлеченным клиническим/молекулярным таблицам.
- Сравнительный калькулятор исходов и рецидивов по методам лечения.
