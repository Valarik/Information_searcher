---
phase: 01-harvesting-and-prisma-triage
plan: 01
subsystem: harvesting
tags: [pubmed, europepmc, openalex, clinicaltrials, sqlite, deduplication]
requires: []
provides:
  - src/harvester.py
  - data/dupuytren/literature.db
  - data/dupuytren/raw/
affects: [01-02, 02-01]
tech-stack:
  added: [pyyaml, polite-http, pip-system-certs, truststore, sqlite3]
  patterns: [idempotent-raw-json-cache, cascade-deduplication-pmid-doi-title]
key-files:
  created:
    - src/harvester.py
  modified:
    - configs/dupuytren.yaml
key-decisions:
  - "D-08: Keyless API execution using polite-http rate limiters across all 4 adapters."
  - "D-02: Journal version takes priority over bioRxiv/medRxiv preprint during title/DOI deduplication; surviving 2023-2026 preprints retain is_preprint=1 and [Preprint] tag."
  - "Injected truststore into SSL context to support Windows certificate store under standalone uv Python 3.12."
requirements-completed: [HARV-01, HARV-02]
duration: 12min
completed: 2026-11-04
---

# Phase 01 Plan 01: Multi-Source Harvesting & Cascade Deduplication Summary

Реализован универсальный конфигурационно-зависимый сборщик медицинской литературы (`src/harvester.py`), объединяющий выгрузку из PubMed, Europe PMC, OpenAlex и ClinicalTrials.gov с каскадной дедупликацией в SQLite (`data/dupuytren/literature.db`).

## Выполнение задач

| Task | Название | Статус | Ключевой результат |
|-----:|----------|--------|--------------------|
| 1 | Implement `src/harvester.py` | Выполнено | Адаптеры к 4 API (`pubmed_api.py`, `europepmc_api.py`, `openalex_cli.py`, `clinical_trials_api.py`), нормализация заголовков, слияние дублей по `PMID -> DOI -> norm_title` |
| 2 | Run Full 2016–2026 Dupuytren Harvest | Выполнено | Выгружено 3 363 сырых записи (PubMed: 1 132, Europe PMC: 537, OpenAlex: 1 694) и 80 РКИ/исследований из ClinicalTrials.gov; после дедупликации — **2 209 уникальных статей** |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Исправление проверки Windows SSL-сертификатов в изолированном окружении `uv`**
- **Found during:** Task 2
- **Issue:** Изолированный интерпретатор Python 3.12 (`uv`) падал с ошибкой `[SSL: CERTIFICATE_VERIFY_FAILED] self-signed certificate in certificate chain` при обращениях к внешним API на Windows.
- **Fix:** В зависимости скрипта добавлены `pip-system-certs` и `truststore` с вызовом `truststore.inject_into_ssl()`.
- **Files modified:** `src/harvester.py`

**2. [Rule 1 - Bug] Корректировка синтаксиса запросов OpenAlex и Europe PMC**
- **Found during:** Task 2
- **Issue:** OpenAlex API возвращал HTTP 400 при передаче виртуального поля `is_oa` в `select` (требуется `open_access`), а в Europe PMC строгий префикс `TITLE:` без фразового поиска упускал часть открытых статей.
- **Fix:** Обновлен список полей `--select` для OpenAlex и расширен запрос Europe PMC в `configs/dupuytren.yaml` (рост числа OA-записей Europe PMC с 211 до 537).
- **Files modified:** `src/harvester.py`, `configs/dupuytren.yaml`
