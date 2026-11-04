# Phase 2: Роевая структурированная экстракция - Research

**Researched:** 2026-11-04
**Domain:** Параллельная структурированная экстракция биомедицинских и клинических данных из SQLite + полнотекстовых JATS XML (`Europe PMC`) по 4 кластерам контрактуры Дюпюитрена (2016–2026)
**Confidence:** HIGH

## Summary

В результате Фазы 1 сформирована база `data/dupuytren/literature.db`, содержащая `1 775` прошедших PRISMA-отбор статей (`Tier 1`: 181, `Tier 2`: 192, `Tier 3`: 942, `Tier 4`: 460), `233` полнотекстовых XML-файла в `data/dupuytren/raw/fulltext_xml/` и `80` клинических исследований из `ClinicalTrials.gov`.

Задача Фазы 2 — перевести этот корпус из уровня библиографических записей и XML в строго типизированные строки таблиц `extracted_mechanisms` и `extracted_clinical_evidence` (и 4 проверочных аналитических досье `data/dupuytren/extractions/cluster_1..4.md`), исключив потерю количественных метрик (`OR`, `HR`, `p-value`, размеры выборок `N`, углы коррекции МФС/ПМФС, частоты рецидивов на 1–3–5–10 годах и определение рецидива `≥20° Kan` vs `≥30°` vs `re-intervention`).

**Primary recommendation:** Реализовать 4 независимых кластерных пайплайна (`02-01` .. `02-04`), которые могут выполняться параллельно роем субагентов (`Wave 1`). Каждый кластерный модуль сочетает:
1. **Глубокий парсинг и экспертную курацию ядра (`Tier 1–2` + `233` JATS XML + целевые ниши `Tier 3–4`)** с извлечением точных цифр из разделов `Results`, `Tables` и структурированных абстрактов;
2. **Автоматизированную табличную индексацию остальных оригинальных серий `Tier 3`** (`D-01`) с отсевом нарративных обзоров (`D-06`);
3. **Запись в SQLite (`timeout=30.0`, `WAL`) + экспорт JSON-кэша и проверочного досье `data/dupuytren/extractions/cluster_N_*.md` (`D-04`)**.

---

## User Constraints (from `02-CONTEXT.md`)

### Locked Decisions
- **D-01 (Гибридный глубокий охват корпуса):**
  - 100% разбор всех статей `Tier 1–2` (`373` шт.) и всех `233` полнотекстовых XML (`Tier 1–3`).
  - Целевой добор оригинальных работ `Tier 3` по нишевым темам (`WALANT`, липографтинг/SVF, дистракционные аппараты `Digit Widget`, новые молекулярные мишени *in vitro*/*ex vivo*) и `23` клинических случаев редких/тяжелых осложнений из `Tier 4` (`Rare Complication Case [D-05]`).
  - Автоматизированная сводная индексация остальных оригинальных серий `Tier 3` без смешивания с нарративными обзорами (`133` статьи `Narrative Review [D-06]`).
- **D-02 (Стандартизация критериев рецидива и суставов ПФС/ПМФС):**
  - Обязательная фиксация порога рецидива в `recurrence_definition` (`≥20° Kan consensus`, `≥30°`, `re-intervention`, `not specified`).
  - Раздельная запись исходов и рецидивов по ПФС (`mcp_outcome`, `recurrence_rate_mcp`) и ПМФС (`pip_outcome`, `recurrence_rate_pip`) с группировкой по горизонтам `≤12 мес.`, `24–36 мес.`, `≥60 мес.`.
- **D-03 (Полный разбор CCH и сшивка с `ClinicalTrials.gov`):**
  - Полный разбор коллагеназы *C. histolyticum* (`CCH` / `Xiapex` / `Xiaflex`) наравне с `PNF` и фасциэктомией (включая отзыв с рынка ЕС/Великобритании в 2020 г. и фармакоэкономику).
  - Перекрестная сшивка всех `80` протоколов `ClinicalTrials.gov` (`NCT ID`) с опубликованными `PMID` и таблица новых таргетных испытаний (адалимумаб / `RIDD`, пирфенидон, вертепорфин, УВТ).
- **D-04 (Двойной выход роевой экстракции):**
  - Заполнение таблиц `extracted_mechanisms` и `extracted_clinical_evidence` в `data/dupuytren/literature.db` + генерация 4 проверочных аналитических досье:
    - `data/dupuytren/extractions/cluster_1_etiology_genetics.md`
    - `data/dupuytren/extractions/cluster_2_pathogenesis.md`
    - `data/dupuytren/extractions/cluster_3_conservative_minimally_invasive.md`
    - `data/dupuytren/extractions/cluster_4_surgical_and_outcomes.md`

---

## Corpus Breakdown & Architecture Patterns

### Распределение статей по кластерам в `data/dupuytren/literature.db`

| План | Кластер | Целевая таблица SQLite | Всего статей | Ядро `Tier 1–2` | Полных XML (`Tier 1–3`) | Выходное досье |
|------|---------|------------------------|-------------:|----------------:|------------------------:|----------------|
| `02-01` | Кластер 1: Этиология, эпидемиология и генетика (`etiology`) | `extracted_mechanisms` | 433 | 124 | 80 | `cluster_1_etiology_genetics.md` |
| `02-02` | Кластер 2: Молекулярный и клеточный патогенез (`pathogenesis`) | `extracted_mechanisms` | 649 | 199 | 124 | `cluster_2_pathogenesis.md` |
| `02-03` | Кластер 3: Консервативные и малоинвазивные методы (`conservative` + `80` РКИ) | `extracted_clinical_evidence` | 683 | 198 | 106 | `cluster_3_conservative_minimally_invasive.md` |
| `02-04` | Кластер 4: Хирургическое лечение, осложнения и отдаленные результаты (`surgical` + `outcomes` + `23` редких осложнений `Tier 4`) | `extracted_clinical_evidence` | 915 (уник.) | 328 (уник.) | 158 (уник.) | `cluster_4_surgical_and_outcomes.md` |

### Безопасная параллельная запись в SQLite (`WAL` + `timeout=30.0` + идемпотентные срезы)
Чтобы 4 субагента в `Wave 1` могли параллельно писать в `data/dupuytren/literature.db` без блокировок `database is locked` и дублирования строк:
1. Каждый кластерный скрипт открывает соединение через `sqlite3.connect(db_path, timeout=30.0)` с `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=30000;`.
2. У каждого кластера свой непересекающийся префикс/множество категорий:
   - `02-01` (`extracted_mechanisms`): категории `Epidemiology & Prevalence`, `Genetics & GWAS`, `Wnt Signaling Genetics`, `Metabolic & Lifestyle Risk Factors`, `Occupational & Vibration Exposure`, `Dupuytren Diathesis & Associated Fibromatoses`, `Epigenetics & Non-coding RNA`.
   - `02-02` (`extracted_mechanisms`): категории `Myofibroblast Biology & Cellular Origin`, `TGF-beta / Smad Canonical & Non-canonical Signaling`, `Mechanotransduction & YAP/TAZ`, `Immune Microenvironment, Macrophages & TNF`, `Extracellular Matrix, Collagen III/I & MMPs/TIMPs`, `Single-Cell & Spatial Multi-Omics`.
   - `02-03` (`extracted_clinical_evidence`): интервенции консервативного/малоинвазивного профиля (`Collagenase Clostridium histolyticum (CCH)`, `Percutaneous Needle Fasciotomy (PNF)`, `Adalimumab / Anti-TNF & Targeted Injections`, `Radiotherapy`, `Corticosteroid Injection`, `ESWT / Physical Therapy / Night Splinting`).
   - `02-04` (`extracted_clinical_evidence`): хирургические интервенции, сравнительные РКИ/метаанализы хирургии vs малоинвазивных методов и редкие осложнения (`Limited / Selective Fasciectomy (LF)`, `Dermofasciectomy (DF) & Skin Grafting`, `Open Palm (McCash) & Z-Plasty/Brunner`, `WALANT Hand Surgery`, `Percutaneous Aponeurotomy + Lipofilling (PALF/SVF)`, `Skeletal Traction / Digit Widget & Salvage`, `Comparative Surgery vs PNF/CCH Long-Term`, `Rare Severe Complication [D-05]`).
3. Каждый скрипт также сохраняет полный дамп извлеченных записей в `data/dupuytren/extractions/cluster_<N>_rows.json`.

### Парсинг полнотекстовых JATS XML (`data/dupuytren/raw/fulltext_xml/PMC*.xml`)
- Стандартная библиотека `xml.etree.ElementTree` безопасна и не требует внешних бинарных зависимостей.
- Из каждого XML извлекаются:
  - Заголовки и текст разделов `<sec>` с фильтрацией по `Results`, `Patients and Methods`, `Statistical Analysis`, `Complications`, `Recurrence`;
  - Таблицы `<table-wrap>` (`<caption/>` + строки `<tr><td>`), где содержатся точные углы МФС/ПМФС, частоты рецидивов, `OR`/`HR` и `p-value`.

---

## Validation Architecture

### Automated Verification Commands
- **Проверка `02-01` (Кластер 1 — Этиология и генетика):**
  `uv run src/extract_cluster_1.py --verify` — проверяет наличие записей в `extracted_mechanisms` по всем 7 этиологическим/генетическим рубрикам, валидность ссылок `article_id`/`pmid` и полноту файла `data/dupuytren/extractions/cluster_1_etiology_genetics.md`.
- **Проверка `02-02` (Кластер 2 — Молекулярный и клеточный патогенез):**
  `uv run src/extract_cluster_2.py --verify` — проверяет заполнение `extracted_mechanisms` по всем 6 патогенетическим рубрикам, наличие данных из XML/scRNA-seq и наличие `data/dupuytren/extractions/cluster_2_pathogenesis.md`.
- **Проверка `02-03` (Кластер 3 — Консервативные и малоинвазивные методы):**
  `uv run src/extract_cluster_3.py --verify` — проверяет заполнение `extracted_clinical_evidence` по CCH, PNF, адалимумабу, лучевой терапии, стероидам, УВТ и ортезированию, сшивку 80 протоколов `ClinicalTrials.gov` и файл `data/dupuytren/extractions/cluster_3_conservative_minimally_invasive.md`.
- **Проверка `02-04` (Кластер 4 — Хирургия, осложнения и отдаленные результаты):**
  `uv run src/extract_cluster_4.py --verify` — проверяет заполнение `extracted_clinical_evidence` по всем хирургическим техникам, раздельным показателям МФС/ПМФС (`mcp_outcome`, `pip_outcome`, `recurrence_rate_mcp`, `recurrence_rate_pip`, `recurrence_definition`), 23 редким осложнениям `Tier 4` и файл `data/dupuytren/extractions/cluster_4_surgical_and_outcomes.md`.
