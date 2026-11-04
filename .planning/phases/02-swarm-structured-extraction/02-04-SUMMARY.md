---
phase: 02-swarm-structured-extraction
plan: 04
subsystem: extraction
tags: [cluster4, surgery, fasciectomy, dermofasciectomy, walant, palf, recurrence, proms, complications]
requires: [01-01, 01-02, 02-01]
provides:
  - src/extract_cluster_4.py
  - data/dupuytren/extractions/cluster_4_rows.json
  - data/dupuytren/extractions/cluster_4_surgical_and_outcomes.md
affects: [03-01, 03-02, 03-03]
tech-stack:
  added: []
  patterns: [mcp-vs-pip-recurrence-matrix, isolated-tier4-rare-complication-registry-d05]
key-files:
  created:
    - src/extract_cluster_4.py
    - data/dupuytren/extractions/cluster_4_rows.json
    - data/dupuytren/extractions/cluster_4_surgical_and_outcomes.md
  modified: []
key-decisions:
  - "D-02: Built a 1-3-5-10 year recurrence matrix stratified by joint (MCP vs PIP) and recurrence definition (Kan >=20 deg vs >=30 deg vs re-intervention)."
  - "D-05: Isolated all 23 Tier 4 rare severe complication case reports under '[Cluster4] Rare Severe Complication [D-05]' so population complication rates in RCTs/cohorts remain unskewed."
requirements-completed: [EXTR-04]
duration: 15min
completed: 2026-11-04
---

# Phase 02 Plan 04: Cluster 4 Structured Extraction (Surgical Treatments, Complications & Long-Term Outcomes) Summary

Реализован скрипт структурированной экстракции хирургических вмешательств, осложнений и отдалённых результатов (`src/extract_cluster_4.py`), записавший **732 строки** (`[Cluster4]*`) в таблицу `extracted_clinical_evidence` (доведя её общий объём до **1 213 строк**), и подготовлено аналитическое досье `data/dupuytren/extractions/cluster_4_surgical_and_outcomes.md`.

## Выполнение задач

| Task | Название | Статус | Ключевой результат |
|-----:|----------|--------|--------------------|
| 1 | Create and Run `src/extract_cluster_4.py` | Выполнено | В `extracted_clinical_evidence` внесено 732 строки по 8 группам (`Comparative Surgery vs PNF/CCH Long-Term`: 414, `Limited / Selective Fasciectomy (LF)`: 181, `Skeletal Traction / Digit Widget & Salvage`: 35, `Dermofasciectomy (DF) & Skin Grafting`: 29, `Rare Severe Complication [D-05]`: 23, `Open Palm (McCash) & Z-Plasty/Brunner`: 21, `PALF/SVF`: 20, `WALANT Hand Surgery`: 9) |
| 2 | Synthesize `cluster_4_surgical_and_outcomes.md` | Выполнено | Сформировано досье объёмом 30,9 КБ с анализом `LF`, `DF + FTSG`, `McCash`, `WALANT`, `PALF`, дистракции `Digit Widget`, матрицей рецидивов `ПФС vs ПМФС` на 1–10 лет, шкалами `URAM/DASH/PEM` и изолированным реестром 23 редких катастрофических осложнений (`D-05`) |

## Deviations from Plan

Отклонений от плана не потребовалось — все 8 хирургических и прогностических групп, включая изолированный реестр 23 редких осложнений (`D-05`), прошли автоматическую верификацию (`--verify`).
