# Сертификат автоматической верификации отчётов (`src/verify_reports.py` — `trigger_finger`)

- **Статус проверки:** `PASSED (Zero-Tolerance Gate)`
- **Нозология:** Болезнь Нотта (стенозирующий лигаментит / щелкающий палец и контрактура ПМФС) (`M65.3`)
- **База данных верификации:** `data/trigger_finger/literature.db` (`1024` включённых статей, `99` протоколов `ClinicalTrials.gov`)
- **Число библиографических источников `[1]..[98]` в диссертационном отчёте:** `98` (`100%` подтверждены в SQLite)
- **Нарушений словаря `ru-medical-humanizer`:** `0`
- **Несуществующих / галлюцинированных `PMID / PMCID / DOI / NCT ID`:** `0`
- **Сформированные файлы MS Word (`.docx`):** `dissertation_report.docx` (29.0 КБ), `executive_summary.docx` (10.4 КБ), `full_clinical_dossier.docx` (68.3 КБ)

## Сводная таблица проверенных файлов отчёта (3 режима)

| Файл отчёта | Объём (КБ) | Верифицировано уникальных `PMID` | Верифицировано `PMCID` | Верифицировано `NCT ID` | Штампы ИИ (`ru-medical-humanizer`) | Статус |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `reports/trigger_finger/dissertation_report.md` | 74.2 | 98 | 31 | 11 | 0 | `OK` |
| `reports/trigger_finger/executive_summary.md` | 17.9 | 39 | 0 | 4 | 0 | `OK` |
| `reports/trigger_finger/knowledge_base/01_disease_overview_and_pathogenesis.md` | 16.7 | 21 | 0 | 1 | 0 | `OK` |
| `reports/trigger_finger/knowledge_base/02_pip_joint_pain_and_contracture_6m_phenomenon.md` | 26.2 | 27 | 0 | 2 | 0 | `OK` |
| `reports/trigger_finger/knowledge_base/03_conservative_and_injection_modalities.md` | 10.6 | 19 | 0 | 5 | 0 | `OK` |
| `reports/trigger_finger/knowledge_base/04_surgical_release_and_fds_resection.md` | 10.7 | 23 | 0 | 2 | 0 | `OK` |
| `reports/trigger_finger/knowledge_base/05_clinical_trials_and_rct_registry.md` | 14.1 | 23 | 0 | 14 | 0 | `OK` |
