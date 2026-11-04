---
phase: 02-swarm-structured-extraction
plan: 03
subsystem: extraction
tags: [cluster3, collagenase, cch, pnf, adalimumab, radiotherapy, eswt, splinting, clinicaltrials]
requires: [01-01, 01-02, 02-01]
provides:
  - src/extract_cluster_3.py
  - data/dupuytren/extractions/cluster_3_rows.json
  - data/dupuytren/extractions/cluster_3_conservative_minimally_invasive.md
affects: [03-01, 03-02, 03-03]
tech-stack:
  added: []
  patterns: [joint-stratified-outcomes-mcp-pip, clinicaltrials-pmid-crosslinking]
key-files:
  created:
    - src/extract_cluster_3.py
    - data/dupuytren/extractions/cluster_3_rows.json
    - data/dupuytren/extractions/cluster_3_conservative_minimally_invasive.md
  modified: []
key-decisions:
  - "D-02: Separate extraction of MCP (ПФС) and PIP (ПМФС) outcomes and explicit recurrence_definition thresholds across all 481 Cluster 3 rows."
  - "D-03: Full evaluation of Collagenase C. histolyticum (CCH) including DISC/DETECT trials and post-2020 EU withdrawal alongside cross-linking of all 80 ClinicalTrials.gov records."
requirements-completed: [EXTR-03]
duration: 15min
completed: 2026-11-04
---

# Phase 02 Plan 03: Cluster 3 Structured Extraction (Conservative & Minimally Invasive Treatments + ClinicalTrials.gov) Summary

Реализован скрипт клинической экстракции Кластера 3 (`src/extract_cluster_3.py`), добавивший **481 запись** (`[Cluster3]*`) в таблицу `extracted_clinical_evidence` по 6 группам консервативных, инъекционных и миниинвазивных вмешательств, и сформировано аналитическое досье `data/dupuytren/extractions/cluster_3_conservative_minimally_invasive.md` с кросс-линковкой всех 80 протоколов `ClinicalTrials.gov`.

## Выполнение задач

| Task | Название | Статус | Ключевой результат |
|-----:|----------|--------|--------------------|
| 1 | Create and Run `src/extract_cluster_3.py` | Выполнено | В `extracted_clinical_evidence` записана 481 строка (`CCH`: 206, `PNF`: 150, `ESWT / Physical Therapy / Night Splinting`: 72, `Radiotherapy`: 26, `Corticosteroid Injection`: 14, `Adalimumab / Anti-TNF & Targeted Injections`: 13) |
| 2 | Synthesize `cluster_3_conservative_minimally_invasive.md` | Выполнено | Сформировано досье объёмом 28,7 КБ с разбором РКИ `DISC`, `DETECT`, `RIDD` (адалимумаб), `DEPART` (лучевая терапия), РКИ ночного шинирования и полным реестром 80 протоколов `ClinicalTrials.gov` (`NCT ID <-> PMID`) |

## Deviations from Plan

Отклонений от плана не потребовалось — все 6 групп вмешательств и матрица `ClinicalTrials.gov` прошли верификацию (`--verify`).
