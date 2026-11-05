# Сертификат автоматической верификации отчётов (`src/verify_reports.py` — `metroplasty_pregnancy`)

- **Статус проверки:** `PASSED (Zero-Tolerance Gate)`
- **Нозология:** Клинические случаи метропластики и реконструкции матки во время беременности (`O34.2 / O71.0 / O71.1 / Q51.1–Q51.4`)
- **База данных верификации:** `data/metroplasty_pregnancy/literature.db` (`506` включённых статей, `8` протоколов `ClinicalTrials.gov`)
- **Число библиографических источников `[1]..[78]` в диссертационном отчёте:** `78` (`100%` подтверждены в SQLite)
- **Нарушений словаря `ru-medical-humanizer`:** `0`
- **Несуществующих / галлюцинированных `PMID / PMCID / DOI / NCT ID`:** `0`

## Сводная таблица проверенных файлов отчёта (3 режима)

| Файл отчёта | Объём (КБ) | Верифицировано уникальных `PMID` | Верифицировано `PMCID` | Верифицировано `NCT ID` | Штампы ИИ (`ru-medical-humanizer`) | Статус |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `reports/metroplasty_pregnancy/dissertation_report.md` | 62.9 | 78 | 49 | 10 | 0 | `OK` |
| `reports/metroplasty_pregnancy/executive_summary.md` | 15.7 | 33 | 0 | 2 | 0 | `OK` |
| `reports/metroplasty_pregnancy/knowledge_base/01_etiology_epidemiology_and_patient_profile.md` | 11.6 | 33 | 0 | 2 | 0 | `OK` |
| `reports/metroplasty_pregnancy/knowledge_base/02_pathogenesis_and_staging_classification.md` | 10.8 | 26 | 0 | 1 | 0 | `OK` |
| `reports/metroplasty_pregnancy/knowledge_base/03_treatment_modalities_pros_and_cons.md` | 14.3 | 39 | 0 | 3 | 0 | `OK` |
| `reports/metroplasty_pregnancy/knowledge_base/04_recurrence_and_complications_statistics.md` | 12.8 | 8 | 0 | 0 | 0 | `OK` |
| `reports/metroplasty_pregnancy/knowledge_base/05_clinical_trials_and_rct_registry.md` | 13.3 | 26 | 0 | 13 | 0 | `OK` |
