# Сертификат автоматической верификации отчётов Фазы 3 (`src/verify_reports.py`)

- **Статус проверки:** `PASSED (Zero-Tolerance Gate)`
- **База данных верификации:** `data/dupuytren/literature.db` (`1 775` включённых статей, `80` протоколов `ClinicalTrials.gov`)
- **Число библиографических источников `[1]..[87]` в диссертационном отчёте:** `87` (`100%` подтверждены в SQLite)
- **Нарушений словаря `ru-medical-humanizer`:** `0`
- **Несуществующих / галлюцинированных `PMID / PMCID / DOI / NCT ID`:** `0`

## Сводная таблица проверенных файлов отчёта (3 режима)

| Файл отчёта | Объём (КБ) | Верифицировано уникальных `PMID` | Верифицировано `PMCID` | Верифицировано `NCT ID` | Штампы ИИ (`ru-medical-humanizer`) | Статус |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `reports/dupuytren/dissertation_report.md` | 127.9 | 87 | 55 | 0 | 0 | `OK` |
| `reports/dupuytren/executive_summary.md` | 29.4 | 54 | 1 | 0 | 0 | `OK` |
| `reports/dupuytren/knowledge_base/01_etiology_epidemiology_and_patient_profile.md` | 9.4 | 25 | 1 | 0 | 0 | `OK` |
| `reports/dupuytren/knowledge_base/02_pathogenesis_and_staging_classification.md` | 10.4 | 23 | 0 | 0 | 0 | `OK` |
| `reports/dupuytren/knowledge_base/03_treatment_modalities_pros_and_cons.md` | 20.6 | 38 | 0 | 0 | 0 | `OK` |
| `reports/dupuytren/knowledge_base/04_recurrence_and_complications_statistics.md` | 9.6 | 30 | 0 | 0 | 0 | `OK` |
| `reports/dupuytren/knowledge_base/05_clinical_trials_and_rct_registry.md` | 7.7 | 17 | 0 | 7 | 0 | `OK` |
