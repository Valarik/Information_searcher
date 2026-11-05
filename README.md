# Information_searcher — Универсальная платформа доказательного медицинского синтеза (2016–2026)

Автономная многофазная исследовательская система для программного сбора литературы из мировых биомедицинских баз (`PubMed`, `Europe PMC`, `OpenAlex`, `ClinicalTrials.gov`), автоматизированного PRISMA-триажа, кластерной экстракции в реляционную базу данных `SQLite` и генерации строго верифицированных клинических отчётов в 3 режимах с универсальным интерактивным веб-интерфейсом на `Streamlit`.

Активная нозология в рабочей конфигурации (`configs/prom.yaml`, `data/prom/`, `reports/prom/`):
- **Преждевременное излитие околоплодных вод (`ПИОВ / ПРПО — Premature Rupture of Membranes [PROM / PPROM]`, МКБ-10: `O42` / МКБ-11: `JA89`)** — **4 474** уникальные статьи (включено после PRISMA-триажа **2 643** исследования: `Tier 1` — 440, `Tier 2` — 638, `Tier 3` — 1 374, `Tier 4` — 191), **210** клинических протоколов `ClinicalTrials.gov`, **950** патогенетических записей и **1 150** записей клинической эффективности.

*(Предыдущая наработка по контрактуре Дюпюитрена перенесена в отдельную изолированную папку `archive/dupuytren/` и исключена из активного интерфейса).*

---

## 1. Запуск универсального веб-приложения (`app.py`)

```powershell
$env:PATH = "$HOME\.local\bin;" + $env:PATH
uv run streamlit run app.py
```

Для безголового автоматического самотестирования всех 4 вкладок, универсальной схемы и экспортов `.html` / `.csv`:

```powershell
$env:PATH = "$HOME\.local\bin;" + $env:PATH
uv run app.py --self-test
```

---

## 2. Изолированная структура папок для каждой нозологии

Каждая нозология хранится в собственных директориях `configs/<id>.yaml`, `data/<id>/` и `reports/<id>/`, не смешиваясь с другими заболеваниями:

```text
├── app.py                          # Универсальное веб-приложение Streamlit (4 вкладки)
├── configs/
│   └── prom.yaml                   # Конфигурация нозологии «Преждевременное излитие околоплодных вод» (O42)
├── src/
│   ├── schema.py                   # Универсальная схема таблиц SQLite
│   ├── harvester.py                # Фаза 1: Сбор PubMed, Europe PMC, OpenAlex, ClinicalTrials.gov
│   ├── triage.py                   # Фаза 1: Конфигурационно-зависимый PRISMA-триаж и загрузка XML
│   ├── extractor_common.py         # Фаза 2: Ядро кластерной экстракции
│   ├── extract_prom.py             # Фаза 2: Кластерная экстракция в data/prom/literature.db
│   ├── verify_reports.py           # Фаза 3: Компиляция библиографии и Zero-Tolerance аудит (--nosology <id>)
│   └── universal_schema.py         # Фаза 4: Универсальный адаптер нозологий и HTML/CSV экспорт
├── data/prom/
│   ├── literature.db               # База SQLite по ПИОВ/ПРПО (2643 статьи, 1150 клин., 950 мех., 210 РКИ)
│   └── extractions/                # 4 кластерных аналитических досье
├── reports/prom/
│   ├── dissertation_report.md      # Режим А: Диссертационная монография (4 главы + 97 источников [1]..[97])
│   ├── executive_summary.md        # Режим Б: Краткий клинический отчёт
│   ├── prisma_stats.md             # Сводка отбора PRISMA
│   ├── verification_audit.md       # Сертификат верификации ссылок и стиля
│   └── knowledge_base/             # Режим В: 5 модулей базы знаний + kb_index.json
└── archive/dupuytren/              # Изолированный архив предыдущей нозологии
```

---

## 3. Команды полного цикла для любой нозологии

```powershell
$env:PATH = "$HOME\.local\bin;" + $env:PATH

# 1. Сбор литературы и PRISMA-триаж
uv run src/harvester.py --config configs/prom.yaml
uv run src/triage.py --config configs/prom.yaml

# 2. Кластерная экстракция
uv run src/extract_prom.py

# 3. Компиляция библиографии, аудит ссылок и проверка универсальной схемы
uv run src/verify_reports.py --nosology prom --compile-bibliography --verify
uv run src/universal_schema.py --verify --nosology prom

# 4. Самотестирование и запуск веб-приложения
uv run app.py --self-test
uv run streamlit run app.py
```
