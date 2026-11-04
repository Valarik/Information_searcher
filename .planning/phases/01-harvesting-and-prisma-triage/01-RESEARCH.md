# Phase 1: Сбор корпуса и PRISMA-триаж — Technical Research

**Phase:** 01-harvesting-and-prisma-triage
**Date:** 2026-11-04
**Requirements covered:** HARV-01, HARV-02, HARV-03, HARV-04
**Decisions integrated:** D-01, D-02, D-03, D-04, D-05, D-06, D-07, D-08

---

## 1. Интеграция с официальными API-скриптами плагина Science

В системе уже установлены и проверены 4 официальных CLI-инструмента (запускаются через `uv run`):

1. **PubMed (`C:/Users/user/.gemini/config/plugins/science/skills/pubmed_database/scripts/pubmed_api.py`)**:
   - Использует библиотеку `polite-http` с автоматическим rate-limiting: `3 req/s` без ключа (`10 req/s` с `NCBI_API_KEY`).
   - Вызов поиска: `uv run <path>/pubmed_api.py <out.json> search_pubmed "<query>" --max_results 5000 --sort_by pub_date`.
   - Вызов пакетного получения метаданных и абстрактов: поскольку `fetch_article_abstracts` выполняет `GET` к `efetch.fcgi`, оптимальный размер батча без переполнения длины URL — **150–200 PMID за вызов** (`uv run <path>/pubmed_api.py <batch.json> fetch_article_abstracts "PMID1,PMID2,..."`). Для 2500 статей это ~13–17 запросов (~5–6 секунд в безключевом режиме `D-08`).

2. **Europe PMC (`C:/Users/user/.gemini/config/plugins/science/skills/literature_search_europepmc/scripts/europepmc_api.py`)**:
   - Встроенный лимит `1 req/s` через `polite-http`.
   - Поиск автоматически добавляет `OPEN_ACCESS:y` и возвращает `resultType=core` (включая `pmid`, `pmcid`, `doi`, `pubTypeList`, `citedByCount`, `abstractText`, `language`, `inEPMC`).
   - Поддерживает курсорную пагинацию `--max_results 1000 --cursor "<nextCursorMark>"`.
   - Выгрузка полнотекстового XML (`D-07`): `uv run <path>/europepmc_api.py get_fulltext <PMCID> --format xml --output <path.xml>` (или `--format text` для очищенного структурированного текста).

3. **OpenAlex (`C:/Users/user/.gemini/config/plugins/science/skills/literature_search_openalex/scripts/openalex_cli.py`)**:
   - В безключевом режиме (`D-08`) дневной бюджет составляет `$0.10/day` на IP, при этом операция `filter` стоит `$0.0001` (в 10 раз дешевле `--search`).
   - Оптимальная стратегия: сначала выполнить один вызов `resolve topics "Dupuytren"` / фильтр по `title_and_abstract.search:Dupuytren,publication_year:2016-2026` с `--per-page 100` и `--select id,doi,ids,display_name,publication_year,publication_date,type,cited_by_count,is_oa,primary_location,authorships,abstract_inverted_index`.
   - Позволяет захватить препринты (`type == "preprint"` в bioRxiv / medRxiv / ResearchSquare) согласно `D-02` и обогатить статьи метрикой `cited_by_count`.

4. **ClinicalTrials.gov (`C:/Users/user/.gemini/config/plugins/science/skills/clinical_trials_database/scripts/clinical_trials_api.py`)**:
   - Вызов: `uv run <path>/clinical_trials_api.py search --condition "Dupuytren Contracture" --limit 1000 --count-total --fields "NCTId,BriefTitle,OfficialTitle,OverallStatus,Phase,StudyType,StartDate,CompletionDate,EnrollmentCount,BriefSummary,ConditionsModule,ArmsInterventionsModule,HasResults" --output <trials.json>`.

---

## 2. Алгоритм дедупликации и PRISMA-триажа (`src/triage.py`)

### 2.1. Склейка дублей и препринтов (`D-02`)
- Первичный ключ склейки: `PMID` → нормализованный `DOI` (в нижнем регистре без префикса `https://doi.org/`) → нормализованный заголовок (`re.sub(r'[^a-z0-9]', '', title.lower())`).
- Если запись из OpenAlex или Europe PMC имеет тип `preprint` (`PPR` / `type: preprint`), к заголовку/типу добавляется метка `[Preprint]`. Если в базе уже есть журнальная статья с тем же нормализованным заголовком и первым автором, препринт склеивается с журнальной версией.

### 2.2. Жесткий фильтр исключения (`D-01`, `D-03`, `D-04`)
В таблицу `articles` добавляется поле `prisma_status` (`included`, `excluded_ fracture_or_offtopic`, `excluded_isolated_peyronie_ledderhose`, `excluded_no_abstract_foreign`):
- **Отсев перелома Дюпюитрена (`D-04`):** если в заголовке/абстракте встречаются маркеры перелома лодыжки (`ankle`, `malleol`, `fibula`, `tibiofibular`, `bimalleolar`, `pott's fracture`, `lower leg`) и нет упоминания ладонного апоневроза (`palmar`, `hand`, `finger`, `aponeurosis`, `fascia`).
- **Отсев нецелевых общих статей (`D-04`):** если ни в заголовке, ни в абстракте, ни в MeSH нет корней `dupuytren`, `palmar fibromatosis`, `vikings disease`, `morbus dupuytren`.
- **Отсев изолированных смежных фиброматозов (`D-03`):** если статья посвящена исключительно болезни Пейрони (`peyronie`, `penile`, `tunica albuginea`) или болезни Леддерхозе (`ledderhose`, `plantar fibromatosis`) без изучения самой контрактуры Дюпюитрена или общих генетических/молекулярных механизмов.
- **Языковой фильтр (`D-01`):** если у статьи отсутствует абстракт на английском/русском языке и нет полнотекстового XML в открытом доступе, она помечается как `excluded_no_abstract` (либо `Tier 4` для писем/комментариев).

### 2.3. Правила стратификации `Tier 1–4` (`D-05`, `D-06`)
- **`Tier 1` (Высший уровень доказательности):**
  - Метаанализы (`Meta-Analysis`), систематические обзоры (`Systematic Review`, `PRISMA` в заголовке/абстракте), рандомизированные контролируемые исследования (`Randomized Controlled Trial`, `RCT`, прямое рандомизированное сравнение LF / PNF / CCH / Radiotherapy / Adalimumab), клинические рекомендации профильных обществ.
- **`Tier 2` (Сильный клинический и фундаментальный уровень):**
  - Проспективные когортные и сравнительные исследования (`Comparative Study`, `Prospective`, `Cohort`, `Registry` с $N \ge 50$), крупные популяционные исследования, полногеномные исследования ассоциаций (`GWAS`, `Mendelian randomization`, `UK Biobank`, `FinnGen`), работы с секвенированием единичных клеток (`scRNA-seq`, `single-cell`, `spatial transcriptomics`), многолетние исследования исходов ($\ge 3$ лет наблюдения).
- **`Tier 3` (Базовый клинический, экспериментальный и обзорный уровень):**
  - Ретроспективные клинические серии, исследования случай-контроль, экспериментальные лабораторные работы *in vitro* / *ex vivo* на тканях пациентов, а также обычные нарративные обзоры (`Narrative Review` по `D-06` — получают специальный подтип `narrative_review`, чтобы во 2-й фазе использоваться только для проверки полноты ссылок, а не для первичной агрегации частот рецидивов).
- **`Tier 4` (Низкий уровень — только PRISMA и редкие осложнения по `D-05`):**
  - Одиночные клинические случаи (`Case Reports`, `case report`), письма в редакцию (`Letter`, `Comment`, `Editorial`, `Erratum`), статьи без абстракта.

---

## Validation Architecture

- **Framework:** Python `unittest` / `pytest` через `uv run python -m unittest`
- **Quick check command:** `uv run python -c "import src.schema, src.harvester, src.triage; print('OK')"`
- **Database & PRISMA verification command:** `uv run python src/verify_phase1.py` (проверяет целостность таблиц `articles` и `clinical_trials`, отсутствие дублей PMID/DOI, работу фильтров `D-01..D-08` и наличие `reports/dupuytren/prisma_stats.md`).
