# Сертификат автоматической верификации отчётов (`src/verify_reports.py` — `prom`)

- **Статус проверки:** `PASSED (Zero-Tolerance Gate)`
- **Нозология:** Преждевременное излитие околоплодных вод (ПИОВ / ПРПО) (`O42 (O42.0–O42.9)`)
- **База данных верификации:** `data/prom/literature.db` (`2643` включённых статей, `210` протоколов `ClinicalTrials.gov`)
- **Число библиографических источников `[1]..[97]` в диссертационном отчёте:** `97` (`100%` подтверждены в SQLite)
- **Нарушений словаря `ru-medical-humanizer`:** `0`
- **Несуществующих / галлюцинированных `PMID / PMCID / DOI / NCT ID`:** `0`
- **Сформированные файлы MS Word (`.docx`):** `dissertation_report.docx` (30.9 КБ), `executive_summary.docx` (8.6 КБ), `full_clinical_dossier.docx` (54.5 КБ)

## Сводная таблица проверенных файлов отчёта (3 режима)

| Файл отчёта | Объём (КБ) | Верифицировано уникальных `PMID` | Верифицировано `PMCID` | Верифицировано `NCT ID` | Штампы ИИ (`ru-medical-humanizer`) | Статус |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `reports/prom/dissertation_report.md` | 72.9 | 97 | 74 | 14 | 0 | `OK` |
| `reports/prom/executive_summary.md` | 12.5 | 27 | 0 | 1 | 0 | `OK` |
| `reports/prom/knowledge_base/01_etiology_epidemiology_and_patient_profile.md` | 8.4 | 21 | 0 | 0 | 0 | `OK` |
| `reports/prom/knowledge_base/02_pathogenesis_and_staging_classification.md` | 7.6 | 17 | 0 | 2 | 0 | `OK` |
| `reports/prom/knowledge_base/03_treatment_modalities_pros_and_cons.md` | 9.3 | 23 | 0 | 1 | 0 | `OK` |
| `reports/prom/knowledge_base/04_recurrence_and_complications_statistics.md` | 8.1 | 21 | 0 | 0 | 0 | `OK` |
| `reports/prom/knowledge_base/05_clinical_trials_and_rct_registry.md` | 8.0 | 14 | 0 | 13 | 0 | `OK` |
