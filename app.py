# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "streamlit>=1.50.0",
#   "pandas>=2.2.0",
#   "plotly>=5.22.0",
#   "markdown>=3.6",
#   "pyyaml>=6.0.1",
#   "truststore>=0.10.0",
# ]
# ///
"""Universal Multi-Nosology Clinical Evidence & Synthesis Platform (`app.py`, v2.0: UI-01, UI-02, EXPORT-02).

Launch interactively:
    uv run streamlit run app.py

Run automated self-test (schema + SQLite + exports + headless Streamlit AppTest):
    uv run app.py --self-test
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.docx_exporter import (
    build_docx_bytes_from_markdown,
    build_executive_docx_bytes,
    build_full_dossier_docx_bytes,
)
from src.extractor_common import (
    VALID_CLAVIEN_DINDO,
    VALID_EVENT_CLASS,
    VALID_REVERSIBILITY,
    validate_nosology_id,
)
from src.harvester import build_complications_queries
from src.universal_schema import (
    dataframe_to_csv_bytes,
    discover_nosologies,
    get_active_project_root,
    load_nosology_bundle,
    query_articles_df,
    query_clinical_evidence_df,
    query_clinical_trials_df,
    query_complications_df,
    query_mechanisms_df,
    render_printable_html,
    save_new_nosology_config,
    split_markdown_sections,
    verify_universal_schema,
)

CLAVIEN_DINDO_ORDER: list[str] = list(VALID_CLAVIEN_DINDO)
CLAVIEN_DINDO_COLORS: dict[str, str] = {
    "I": "#10b981",
    "II": "#3b82f6",
    "IIIa": "#f59e0b",
    "IIIb": "#f97316",
    "IV": "#ef4444",
    "V": "#7f1d1d",
    "Не указан": "#94a3b8",
}
REVERSIBILITY_LABELS_RU: dict[str, str] = {
    "transient_self_limiting": "Транзиторное (самокупирующееся)",
    "requires_conservative_therapy": "Требует консервативной терапии",
    "requires_reoperation": "Требует повторной операции / ревизии",
    "permanent_deficit": "Стойкий дефицит",
}
REVERSIBILITY_COLORS: dict[str, str] = {
    "transient_self_limiting": "#10b981",
    "requires_conservative_therapy": "#3b82f6",
    "requires_reoperation": "#f97316",
    "permanent_deficit": "#b91c1c",
}
REVERSIBILITY_COLORS_RU: dict[str, str] = {
    **{REVERSIBILITY_LABELS_RU[k]: v for k, v in REVERSIBILITY_COLORS.items()},
    "—": "#94a3b8",
}
EVENT_CLASS_LABELS_RU: dict[str, str] = {
    "true_complication": "Истинное осложнение",
    "transient_postop_sequela": "Транзиторное послеоперационное явление",
}
_PMID_RE = re.compile(r"^[1-9]\d{0,8}$")

# CR-01: All nosology-scoped filter/selection widget keys cleared whenever active nosology changes
_NOSOLOGY_SCOPED_WIDGET_KEYS: tuple[str, ...] = (
    "tab1_search_query",
    "tab1_diss_sec",
    "tab1_kb_mod_select",
    "sub3_group_filter",
    "sub4_comparator_picks",
    "sub4_sql_grp",
    "t25_modalities",
    "t25_grades",
    "t25_reversibility",
    "t25_event_class",
    "t3_art_tiers",
    "t3_art_xml",
    "t3_art_kw",
    "t3_clin_grp",
    "t3_clin_kw",
    "t3_mech_cat",
    "t3_mech_kw",
    "t3_tr_status",
    "t3_tr_kw",
    "t3_comp_casuistry",
    "t3_comp_mod",
    "t3_comp_cd",
    "t3_comp_rev",
    "t3_comp_class",
    "t3_comp_kw",
)


def _dict_list(value: Any) -> list[dict[str, Any]]:
    """Return list of dict entries only when value is a list (guards against non-list truthy scalars, WR-01)."""
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def _clean_str(value: Any, fallback: str = "—") -> str:
    """Normalize scalar/null/NaN values cleanly without rendering literal 'None' or 'nan' (WR-01, WR-06)."""
    if value is None or isinstance(value, bool):
        return fallback
    if isinstance(value, float) and not math.isfinite(value):
        return fallback
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else fallback
    cleaned = str(value).strip()
    return cleaned if cleaned else fallback


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely coerce finite numeric value to int without crashing on NaN/inf/None/bool (WR-01)."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        fval = float(value)
        return int(fval) if math.isfinite(fval) else default
    try:
        fval = float(str(value).strip())
        return int(fval) if math.isfinite(fval) else default
    except (TypeError, ValueError):
        return default


def _format_pmid_links_md(pmids: Any) -> str:
    """Validate PMIDs strictly against ^[1-9]\\d{0,8}$ and return clickable Markdown PubMed links (T-19-02)."""
    if not isinstance(pmids, list):
        return "—"
    links: list[str] = []
    seen: set[str] = set()
    for raw in pmids:
        if raw is None or isinstance(raw, bool):
            continue
        pid = str(raw).strip()
        if pid and _PMID_RE.fullmatch(pid) and pid not in seen:
            seen.add(pid)
            links.append(f"[PMID {pid}](https://pubmed.ncbi.nlm.nih.gov/{pid}/)")
    return ", ".join(links) if links else "—"


@st.cache_data(show_spinner=False)
def cached_bundle(nosology_id: str, workspace_root: str = "") -> dict[str, Any]:
    _ = workspace_root
    return load_nosology_bundle(nosology_id)


@st.cache_data(show_spinner=False)
def cached_articles(db_path_str: str, included_only: bool = True) -> pd.DataFrame:
    return query_articles_df(Path(db_path_str), included_only=included_only)


@st.cache_data(show_spinner=False)
def cached_clinical_evidence(db_path_str: str) -> pd.DataFrame:
    return query_clinical_evidence_df(Path(db_path_str))


@st.cache_data(show_spinner=False)
def cached_mechanisms(db_path_str: str) -> pd.DataFrame:
    return query_mechanisms_df(Path(db_path_str))


@st.cache_data(show_spinner=False)
def cached_trials(db_path_str: str) -> pd.DataFrame:
    return query_clinical_trials_df(Path(db_path_str))


@st.cache_data(show_spinner=False)
def cached_complications(db_path_str: str, include_casuistry: bool = True) -> pd.DataFrame:
    return query_complications_df(Path(db_path_str), include_casuistry=include_casuistry)


def highlight_search_matches(md_text: str, query: str) -> tuple[str, int]:
    """Highlight case-insensitive search matches in Markdown text using <mark> tags."""
    q = query.strip()
    if not q or len(q) < 2:
        return md_text, 0
    pattern = re.compile(re.escape(q), re.IGNORECASE)
    matches = pattern.findall(md_text)
    if not matches:
        return md_text, 0
    highlighted = pattern.sub(lambda m: f"<mark style='background:#fef08a;padding:0 2px;'>{m.group(0)}</mark>", md_text)
    return highlighted, len(matches)


def render_sidebar(nosologies: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """Render nosology selector, ICD metadata, corpus KPIs, and quick report downloads."""
    with st.sidebar:
        st.markdown("## 🧬 Нозологический навигатор")
        options = {item["id"]: f"{item['name_ru']} ({item['icd10']})" for item in nosologies}
        if not options:
            options = {"prom": "Преждевременное излитие околоплодных вод (O42)"}

        selected_id = st.selectbox(
            "Выберите нозологию (`configs/*.yaml`):",
            options=list(options.keys()),
            format_func=lambda k: options[k],
            key="sidebar_nosology_select",
        )

        # CR-01: Clear nosology-scoped filter/selection widget keys whenever active nosology changes
        prev_nos_id = st.session_state.get("_active_nosology_id")
        if prev_nos_id is not None and prev_nos_id != selected_id:
            for wkey in _NOSOLOGY_SCOPED_WIDGET_KEYS:
                st.session_state.pop(wkey, None)
        st.session_state["_active_nosology_id"] = selected_id

        bundle = cached_bundle(selected_id, workspace_root=str(get_active_project_root()))
        kb = bundle["kb_index"]
        meta = kb.get("nosology_meta", {})
        stats = meta.get("corpus_stats", kb.get("corpus_stats", {}))

        st.caption(
            f"**МКБ-10:** `{meta.get('icd10', '—')}` | **МКБ-11:** `{meta.get('icd11', '—')}`\n\n"
            f"**Профиль:** {meta.get('specialty', '—')}\n\n"
            f"**Горизонт:** `{meta.get('time_horizon', '2016–2026')}`"
        )

        st.divider()
        st.markdown("### 📊 Объём доказательной базы")
        c1, c2 = st.columns(2)
        c1.metric("Уникальных статей", f"{stats.get('unique_articles', 0):,}".replace(",", " "))
        c2.metric("Включено (PRISMA)", f"{stats.get('included_articles', 0):,}".replace(",", " "))

        c3, c4 = st.columns(2)
        c3.metric("Клинических строк", f"{stats.get('extracted_clinical_rows', 0):,}".replace(",", " "))
        c4.metric("Механизмов (ряд.)", f"{stats.get('extracted_mechanisms_rows', 0):,}".replace(",", " "))

        c5, c6 = st.columns(2)
        c5.metric("Протоколов NCT", f"{stats.get('clinical_trials_nct', 0)}")
        c6.metric("Полнотекстов XML", f"{stats.get('fulltext_xml_count', 233)}")

        comp_rows = _safe_int(stats.get("extracted_complications_rows", 0), default=0)
        if comp_rows > 0 or str(kb.get("schema_version", "")) == "2.0":
            st.metric("Строк осложнений", f"{comp_rows:,}".replace(",", " "))

        st.divider()
        st.markdown("### 📥 Быстрый экспорт отчётов (Word .docx / MD / HTML)")
        DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if bundle["dissertation_md"]:
            st.download_button(
                "📘 Скачать Диссертацию (.docx)",
                data=build_docx_bytes_from_markdown(bundle["dissertation_md"]),
                file_name=f"{selected_id}_dissertation_report.docx",
                mime=DOCX_MIME,
                width="stretch",
                key="sb_dl_diss_docx",
            )
        if bundle["executive_summary_md"]:
            st.download_button(
                "⚡ Скачать Краткий отчёт (.docx)",
                data=build_executive_docx_bytes(bundle["executive_summary_md"], kb),
                file_name=f"{selected_id}_executive_summary.docx",
                mime=DOCX_MIME,
                width="stretch",
                key="sb_dl_exec_docx",
            )
        if bundle["dissertation_md"] and bundle["executive_summary_md"]:
            kb_module_texts = [
                m["content"] for m in bundle.get("kb_modules", []) if m.get("content")
            ]
            st.download_button(
                "📚 Скачать Полное досье (.docx)",
                data=build_full_dossier_docx_bytes(
                    bundle["executive_summary_md"],
                    bundle["dissertation_md"],
                    kb_module_texts,
                    kb,
                ),
                file_name=f"{selected_id}_full_clinical_dossier.docx",
                mime=DOCX_MIME,
                width="stretch",
                key="sb_dl_full_docx",
            )
        if bundle["dissertation_md"]:
            st.download_button(
                "📄 Скачать Диссертацию (.md)",
                data=bundle["dissertation_md"].encode("utf-8"),
                file_name=f"{selected_id}_dissertation_report.md",
                mime="text/markdown",
                width="stretch",
                key="sb_dl_diss_md",
            )
            diss_html = render_printable_html(
                f"{meta.get('title_ru', selected_id)} — Диссертационный отчёт",
                bundle["dissertation_md"],
                meta,
            )
            st.download_button(
                "🖨️ Скачать Диссертацию (HTML/PDF)",
                data=diss_html.encode("utf-8"),
                file_name=f"{selected_id}_dissertation_report.html",
                mime="text/html",
                width="stretch",
                key="sb_dl_diss_html",
            )

    return selected_id, bundle


def render_tab_reports(bundle: dict[str, Any]) -> None:
    """Tab 1: 3-Mode Report Reader with section navigation, keyword search, and MD/HTML export."""
    kb = bundle["kb_index"]
    meta = kb.get("nosology_meta", {})
    nos_id = bundle["nosology_id"]
    kb_mod_count = len(bundle.get("kb_modules", []))

    st.subheader("📑 Аналитические отчёты: 3 режима представления")
    col_mode, col_search = st.columns([2, 1])
    with col_mode:
        report_mode = st.radio(
            "Режим отчёта:",
            options=[
                "Режим А — Диссертационная монография (полный синтез)",
                "Режим Б — Краткий клинический отчёт (Executive Summary)",
                f"Режим В — Модульная база знаний ({kb_mod_count} тематических модулей)",
            ],
            horizontal=False,
            key="tab1_report_mode",
        )
    with col_search:
        search_query = st.text_input(
            "🔍 Поиск термина в тексте отчёта:",
            value="",
            placeholder="Введите клинический термин, биомаркер, препарат или PMID...",
            key="tab1_search_query",
        )

    if report_mode.startswith("Режим А"):
        md_text = bundle["dissertation_md"]
        if not md_text:
            st.warning("Файл `dissertation_report.md` ещё не сгенерирован для выбранной нозологии.")
            return
        sections = split_markdown_sections(md_text)
        sec_titles = ["Все главы целиком (полный текст)"] + [s["title"] for s in sections]
        chosen_sec = st.selectbox("Навигация по главам монографии:", sec_titles, key="tab1_diss_sec")

        active_md = (
            md_text
            if chosen_sec == sec_titles[0]
            else next((s["content"] for s in sections if s["title"] == chosen_sec), md_text)
        )
        DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        dl_col1, dl_col2, dl_col3 = st.columns(3)
        dl_col1.download_button(
            "📘 Скачать в формате Word (.docx)",
            data=build_docx_bytes_from_markdown(active_md),
            file_name=f"{nos_id}_dissertation.docx",
            mime=DOCX_MIME,
            key="t1_diss_docx_btn",
        )
        dl_col2.download_button(
            "⬇️ Скачать выбранный текст (.md)",
            data=active_md.encode("utf-8"),
            file_name=f"{nos_id}_dissertation.md",
            mime="text/markdown",
            key="t1_diss_md_btn",
        )
        dl_col3.download_button(
            "🖨️ Скачать версию для печати / PDF (.html)",
            data=render_printable_html(f"{meta.get('title_ru', nos_id)} — Монография", active_md, meta).encode("utf-8"),
            file_name=f"{nos_id}_dissertation.html",
            mime="text/html",
            key="t1_diss_html_btn",
        )
        rendered_md, match_cnt = highlight_search_matches(active_md, search_query)
        if search_query.strip():
            st.info(f"Найдено совпадений по запросу «{search_query}»: **{match_cnt}**")
        st.markdown(rendered_md, unsafe_allow_html=True)

    elif report_mode.startswith("Режим Б"):
        md_text = bundle["executive_summary_md"]
        if not md_text:
            st.warning("Файл `executive_summary.md` ещё не сгенерирован для выбранной нозологии.")
            return
        DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        dl_col1, dl_col2, dl_col3 = st.columns(3)
        dl_col1.download_button(
            "📘 Скачать Краткий отчёт в Word (.docx)",
            data=build_executive_docx_bytes(md_text, kb),
            file_name=f"{nos_id}_executive_summary.docx",
            mime=DOCX_MIME,
            key="t1_exec_docx_btn",
        )
        dl_col2.download_button(
            "⬇️ Скачать Краткий клинический отчёт (.md)",
            data=md_text.encode("utf-8"),
            file_name=f"{nos_id}_executive_summary.md",
            mime="text/markdown",
            key="t1_exec_md_btn",
        )
        dl_col3.download_button(
            "🖨️ Скачать версию для печати / PDF (.html)",
            data=render_printable_html(f"{meta.get('title_ru', nos_id)} — Краткий отчёт", md_text, meta).encode("utf-8"),
            file_name=f"{nos_id}_executive_summary.html",
            mime="text/html",
            key="t1_exec_html_btn",
        )
        rendered_md, match_cnt = highlight_search_matches(md_text, search_query)
        if search_query.strip():
            st.info(f"Найдено совпадений по запросу «{search_query}»: **{match_cnt}**")
        st.markdown(rendered_md, unsafe_allow_html=True)

    else:
        modules = bundle["kb_modules"]
        if not modules:
            st.warning("Модули базы знаний не найдены.")
            return
        mod_options = {m["id"]: m["title"] for m in modules}
        mod_options["__all__"] = f"📚 Показать все {len(modules)} модулей базы знаний подряд"
        selected_mod_id = st.selectbox(
            "Выберите тематический модуль базы знаний:",
            options=list(mod_options.keys()),
            format_func=lambda k: mod_options[k],
            key="tab1_kb_mod_select",
        )
        if selected_mod_id == "__all__":
            active_md = "\n\n---\n\n".join(m["content"] for m in modules if m["content"])
            fname = f"{nos_id}_knowledge_base_all"
        else:
            mod_obj = next((m for m in modules if m["id"] == selected_mod_id), modules[0])
            active_md = mod_obj["content"]
            fname = f"{nos_id}_{selected_mod_id}"

        DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        dl_col1, dl_col2, dl_col3 = st.columns(3)
        dl_col1.download_button(
            "📘 Скачать модуль в Word (.docx)",
            data=build_docx_bytes_from_markdown(active_md),
            file_name=f"{fname}.docx",
            mime=DOCX_MIME,
            key="t1_kb_docx_btn",
        )
        dl_col2.download_button(
            "⬇️ Скачать модуль базы знаний (.md)",
            data=active_md.encode("utf-8"),
            file_name=f"{fname}.md",
            mime="text/markdown",
            key="t1_kb_md_btn",
        )
        dl_col3.download_button(
            "🖨️ Скачать модуль для печати / PDF (.html)",
            data=render_printable_html(f"{meta.get('title_ru', nos_id)} — База знаний", active_md, meta).encode("utf-8"),
            file_name=f"{fname}.html",
            mime="text/html",
            key="t1_kb_html_btn",
        )
        rendered_md, match_cnt = highlight_search_matches(active_md, search_query)
        if search_query.strip():
            st.info(f"Найдено совпадений по запросу «{search_query}»: **{match_cnt}**")
        st.markdown(rendered_md, unsafe_allow_html=True)


def _render_red_flags_block(red_flags: list[dict[str, Any]]) -> None:
    """Render rare critical complications (<1%) as native Streamlit warning cards without raw HTML (D-02.4, T-19-02, WR-06)."""
    if not red_flags:
        return
    st.divider()
    st.markdown("#### 🚨 Красные флаги: редкие критические осложнения (<1%)")
    st.error(
        "Клиническое предупреждение: приведённые ниже осложнения встречаются редко (<1% наблюдений или единичные "
        "критические случаи), но ассоциированы с тяжестью Clavien–Dindo III–V, необходимостью экстренной ревизии "
        "или риском стойкого функционального дефицита."
    )
    for rf in red_flags:
        rev_raw = _clean_str(rf.get("reversibility"), fallback="")
        rev_ru = REVERSIBILITY_LABELS_RU.get(rev_raw, rev_raw or "—")
        pmid_md = _format_pmid_links_md(rf.get("evidence_pmids"))
        freq_disp = _clean_str(rf.get("frequency_pct"), fallback="<1%")
        comp_disp = _clean_str(rf.get("complication_name"))
        mod_disp = _clean_str(rf.get("modality"))
        cd_disp = _clean_str(rf.get("clavien_dindo_grade"), fallback="Не указан")
        anat_disp = _clean_str(rf.get("anatomical_substrate"))
        prev_disp = _clean_str(rf.get("prevention_and_management"))
        with st.container(border=True):
            st.markdown(
                f"**{comp_disp}** — _{mod_disp}_ "
                f"| **Clavien–Dindo:** `{cd_disp}` "
                f"| **Частота:** `{freq_disp}` "
                f"| **Обратимость:** {rev_ru}"
            )
            c_left, c_right = st.columns(2)
            c_left.markdown(f"**Анатомический субстрат:** {anat_disp}")
            c_right.markdown(f"**Профилактика и экстренная тактика:** {prev_disp}")
            st.caption(f"Доказательная база: {pmid_md}")


def _render_subtab_complications(kb: dict[str, Any], nos_id: str) -> None:
    """Subtab 2.5: Frequent complications profile (Clavien-Dindo), Plotly visuals, CSV & Red Flags (D-02, T-19-02, WR-01, WR-06)."""
    freq_list = _dict_list(kb.get("frequent_complications"))
    red_flags = _dict_list(kb.get("rare_critical_red_flags"))

    if not freq_list:
        st.info(
            "Данная нозология собрана по архивной схеме **v1.x** без отдельного структурированного профиля частых "
            "осложнений (`extracted_complications` / `Clavien–Dindo`). Ниже приведена сводная таблица текстовых "
            "профилей осложнений из раздела методик (режим только для чтения, данные `v1.x` не изменяются)."
        )
        modalities = _dict_list(kb.get("modalities"))
        if modalities:
            df_v1_comp = pd.DataFrame(
                [
                    {
                        "Класс": _clean_str(m.get("group")),
                        "Методика лечения": _clean_str(m.get("name")),
                        "Профиль осложнений (v1.x)": _clean_str(m.get("complications_profile")),
                        "Реабилитация": _clean_str(m.get("recovery_time")),
                    }
                    for m in modalities
                ]
            )
            if not df_v1_comp.empty:
                st.dataframe(df_v1_comp, width="stretch", hide_index=True)
        _render_red_flags_block(red_flags)
        return

    st.markdown("#### ⚠️ Профиль частых осложнений лечения (Clavien–Dindo, частота ≥ 1% в когортах)")
    df_fc = pd.DataFrame(freq_list)
    for col_name, default_val in (
        ("modality", "—"),
        ("complication_name", "—"),
        ("event_class", "—"),
        ("clavien_dindo_grade", "Не указан"),
        ("reversibility", "—"),
        ("frequency_pct", "—"),
        ("frequency_median_num", 0.0),
        ("sample_size_total", None),
        ("time_window", "—"),
        ("anatomical_substrate", "—"),
        ("prevention_and_management", "—"),
        ("evidence_pmids", None),
    ):
        if col_name not in df_fc.columns:
            df_fc[col_name] = default_val

    df_fc["modality"] = df_fc["modality"].apply(lambda v: _clean_str(v, "—"))
    df_fc["complication_name"] = df_fc["complication_name"].apply(lambda v: _clean_str(v, "—"))
    df_fc["event_class"] = df_fc["event_class"].apply(lambda v: _clean_str(v, "—"))
    df_fc["clavien_dindo_grade"] = df_fc["clavien_dindo_grade"].apply(
        lambda v: _clean_str(v, "Не указан")
    )
    df_fc["reversibility"] = df_fc["reversibility"].apply(lambda v: _clean_str(v, "—"))
    df_fc["frequency_pct"] = df_fc["frequency_pct"].apply(lambda v: _clean_str(v, "—"))
    df_fc["time_window"] = df_fc["time_window"].apply(lambda v: _clean_str(v, "—"))
    df_fc["anatomical_substrate"] = df_fc["anatomical_substrate"].apply(lambda v: _clean_str(v, "—"))
    df_fc["prevention_and_management"] = df_fc["prevention_and_management"].apply(
        lambda v: _clean_str(v, "—")
    )
    df_fc["sample_size_total"] = df_fc["sample_size_total"].apply(
        lambda v: _safe_int(v, default=-1)
    ).map(lambda n: str(n) if n >= 0 else "—")
    df_fc["reversibility_ru"] = df_fc["reversibility"].map(
        lambda v: REVERSIBILITY_LABELS_RU.get(v, v)
    )
    df_fc["event_class_ru"] = df_fc["event_class"].map(
        lambda v: EVENT_CLASS_LABELS_RU.get(v, v)
    )
    df_fc["evidence_pmids_str"] = df_fc["evidence_pmids"].apply(
        lambda ps: (
            ", ".join(
                dict.fromkeys(
                    str(p).strip()
                    for p in ps
                    if p is not None and not isinstance(p, bool) and _PMID_RE.fullmatch(str(p).strip())
                )
            )
            if isinstance(ps, list)
            else ""
        )
        or "—"
    )
    df_fc["frequency_median_num"] = (
        pd.to_numeric(df_fc["frequency_median_num"], errors="coerce")
        .replace([float("inf"), float("-inf")], float("nan"))
        .fillna(0.0)
    )

    mod_opts = list(dict.fromkeys(df_fc["modality"].tolist()))
    raw_grades = list(dict.fromkeys(df_fc["clavien_dindo_grade"].tolist()))
    grade_opts = [g for g in CLAVIEN_DINDO_ORDER if g in raw_grades] + [
        g for g in raw_grades if g not in CLAVIEN_DINDO_ORDER
    ]
    raw_revs = list(dict.fromkeys(df_fc["reversibility"].tolist()))
    rev_opts = [r for r in VALID_REVERSIBILITY if r in raw_revs] + [
        r for r in raw_revs if r not in VALID_REVERSIBILITY
    ]
    raw_classes = list(dict.fromkeys(df_fc["event_class"].tolist()))
    cls_opts = [c for c in VALID_EVENT_CLASS if c in raw_classes] + [
        c for c in raw_classes if c not in VALID_EVENT_CLASS
    ]

    f1, f2, f3, f4 = st.columns(4)
    sel_mods = f1.multiselect(
        "Методики лечения:",
        options=mod_opts,
        default=mod_opts,
        key="t25_modalities",
    )
    sel_grades = f2.multiselect(
        "Тяжесть (Clavien–Dindo):",
        options=grade_opts,
        default=grade_opts,
        key="t25_grades",
    )
    sel_revs = f3.multiselect(
        "Обратимость:",
        options=rev_opts,
        default=rev_opts,
        format_func=lambda v: REVERSIBILITY_LABELS_RU.get(v, v),
        key="t25_reversibility",
    )
    sel_classes = f4.multiselect(
        "Класс события:",
        options=cls_opts,
        default=cls_opts,
        format_func=lambda v: EVENT_CLASS_LABELS_RU.get(v, v),
        key="t25_event_class",
    )

    df_view = df_fc[
        df_fc["modality"].isin(sel_mods)
        & df_fc["clavien_dindo_grade"].isin(sel_grades)
        & df_fc["reversibility"].isin(sel_revs)
        & df_fc["event_class"].isin(sel_classes)
    ].copy()

    if df_view.empty:
        st.warning("Нет осложнений, соответствующих выбранным фильтрам.")
    else:
        color_mode = st.radio(
            "Цветовая кодировка диаграммы частот:",
            options=["Класс Clavien–Dindo", "Обратимость"],
            horizontal=True,
            key="t25_color_mode",
        )
        df_plot = df_view.sort_values(
            ["frequency_median_num", "complication_name"],
            ascending=[False, True],
        ).copy()
        df_plot["display_label"] = df_plot["complication_name"] + " — " + df_plot["modality"]

        if color_mode == "Обратимость":
            color_col = "reversibility_ru"
            color_map = REVERSIBILITY_COLORS_RU
            cat_orders = {
                "reversibility_ru": [REVERSIBILITY_LABELS_RU[k] for k in VALID_REVERSIBILITY]
            }
        else:
            color_col = "clavien_dindo_grade"
            color_map = CLAVIEN_DINDO_COLORS
            cat_orders = {"clavien_dindo_grade": CLAVIEN_DINDO_ORDER}

        fig_freq = px.bar(
            df_plot,
            x="frequency_median_num",
            y="display_label",
            color=color_col,
            orientation="h",
            text="frequency_pct",
            color_discrete_map=color_map,
            category_orders=cat_orders,
            hover_data={
                "frequency_median_num": ":.2f",
                "frequency_pct": True,
                "time_window": True,
                "sample_size_total": True,
                "evidence_pmids_str": True,
                "modality": True,
                "clavien_dindo_grade": True,
                "reversibility_ru": True,
                "event_class_ru": True,
                "display_label": False,
            },
            title="Медианная частота частых осложнений по методикам (%)",
            labels={
                "frequency_median_num": "Медианная частота (%)",
                "display_label": "Осложнение — методика",
                "clavien_dindo_grade": "Clavien–Dindo",
                "reversibility_ru": "Обратимость",
                "event_class_ru": "Класс события",
                "frequency_pct": "Частота (диапазон)",
                "time_window": "Окно разрешения",
                "sample_size_total": "Выборка N",
                "evidence_pmids_str": "PMID",
                "modality": "Методика",
            },
            height=max(360, 46 * len(df_plot) + 120),
        )
        fig_freq.update_layout(
            yaxis=dict(autorange="reversed"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_freq, width="stretch")

        df_stack = (
            df_view.groupby(["modality", "clavien_dindo_grade"], as_index=False)
            .size()
            .rename(columns={"size": "Количество событий"})
        )
        fig_stack = px.bar(
            df_stack,
            x="modality",
            y="Количество событий",
            color="clavien_dindo_grade",
            barmode="stack",
            color_discrete_map=CLAVIEN_DINDO_COLORS,
            category_orders={"clavien_dindo_grade": CLAVIEN_DINDO_ORDER},
            text_auto=True,
            title="Распределение частых осложнений по классам Clavien–Dindo (I–V) в разрезе методик",
            labels={
                "modality": "Методика лечения",
                "clavien_dindo_grade": "Clavien–Dindo",
            },
            height=380,
        )
        fig_stack.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_stack, width="stretch")

        disp_fc = df_plot[
            [
                "modality",
                "complication_name",
                "event_class_ru",
                "clavien_dindo_grade",
                "frequency_pct",
                "reversibility_ru",
                "time_window",
                "anatomical_substrate",
                "prevention_and_management",
                "sample_size_total",
                "evidence_pmids_str",
            ]
        ].rename(
            columns={
                "modality": "Методика",
                "complication_name": "Осложнение",
                "event_class_ru": "Класс события",
                "clavien_dindo_grade": "Clavien–Dindo",
                "frequency_pct": "Частота (%)",
                "reversibility_ru": "Обратимость",
                "time_window": "Окно разрешения",
                "anatomical_substrate": "Анатомический субстрат",
                "prevention_and_management": "Профилактика и лечение",
                "sample_size_total": "Выборка N",
                "evidence_pmids_str": "PMID",
            }
        )
        st.caption(f"Отображено частых осложнений: **{len(disp_fc)}** из **{len(df_fc)}**")
        st.dataframe(disp_fc, width="stretch", hide_index=True)
        st.download_button(
            "📥 Скачать профиль частых осложнений (.csv)",
            data=dataframe_to_csv_bytes(disp_fc),
            file_name=f"{nos_id}_frequent_complications.csv",
            mime="text/csv",
            key="dl_csv_freq_comp",
        )

    _render_red_flags_block(red_flags)


def _render_subtab_clinical_nuances(kb: dict[str, Any]) -> None:
    """Subtab 2.6: Clinical decision nuances — workhorses, gray zones & salvage niches (D-03, T-19-02, WR-01, WR-06)."""
    nuances = kb.get("clinical_decision_nuances")
    nuances_dict = nuances if isinstance(nuances, dict) else {}
    workhorses = _dict_list(nuances_dict.get("universal_workhorse_modalities"))
    overlaps = _dict_list(nuances_dict.get("overlapping_indications_and_gray_zones"))
    niches = _dict_list(nuances_dict.get("strict_niche_or_salvage_indications"))

    if not workhorses and not overlaps and not niches:
        st.info(
            "Данная нозология собрана по архивной схеме **v1.x** и не содержит структурированного раздела "
            "`clinical_decision_nuances` (сквозные методики, перекрывающиеся показания и «серые зоны»). "
            "Для сопоставления методик перейдите в подвкладку **«2.4. Бок-о-бок сравнение методик + Доказательства SQLite»**."
        )
        return

    if workhorses:
        st.markdown("#### 🛠️ Сквозные методики («рабочие лошадки»)")
        for wh in workhorses:
            with st.container(border=True):
                st.markdown(f"##### {_clean_str(wh.get('modality'))}")
                st.markdown(f"**Покрываемый спектр стадий:** {_clean_str(wh.get('applicable_spectrum'))}")
                col_l, col_r = st.columns(2)
                col_l.markdown(f"**Практические нюансы:**\n\n{_clean_str(wh.get('practical_nuances'))}")
                col_r.markdown(
                    f"**Факторы опыта хирурга и оснащения:**\n\n{_clean_str(wh.get('surgeon_and_equipment_factors'))}\n\n"
                    f"**Компромиссы для пациента:**\n\n{_clean_str(wh.get('patient_tradeoffs'))}"
                )
                st.caption(f"Доказательная база: {_format_pmid_links_md(wh.get('evidence_pmids'))}")

    if overlaps:
        if workhorses:
            st.divider()
        st.markdown("#### ⚖️ Перекрывающиеся показания и «серые зоны»")
        for ov in overlaps:
            comp_mods = ov.get("competing_modalities")
            if isinstance(comp_mods, list):
                comp_str = (
                    " vs ".join(
                        cleaned
                        for m in comp_mods
                        if (cleaned := _clean_str(m, fallback=""))
                    )
                    or "—"
                )
            else:
                comp_str = _clean_str(comp_mods)
            with st.container(border=True):
                st.markdown(f"##### {_clean_str(ov.get('clinical_scenario'))}")
                st.markdown(f"**Конкурирующие методики:** {comp_str}")
                st.warning(f"**Почему нет одного «победителя»:** {_clean_str(ov.get('why_no_single_winner'))}")
                st.markdown(f"**Решающие практические факторы:** {_clean_str(ov.get('decisive_practical_factors'))}")
                st.caption(f"Доказательная база: {_format_pmid_links_md(ov.get('evidence_pmids'))}")

    if niches:
        if workhorses or overlaps:
            st.divider()
        st.markdown("#### 🎯 Узконишевые показания и методики спасения")
        for ni in niches:
            with st.container(border=True):
                st.markdown(f"##### {_clean_str(ni.get('modality'))}")
                c_l, c_r = st.columns(2)
                c_l.markdown(
                    f"**Узкая ниша / роль спасения:**\n\n{_clean_str(ni.get('narrow_indication_or_salvage_role'))}"
                )
                c_r.markdown(
                    f"**Почему не первая линия для всех:**\n\n{_clean_str(ni.get('why_not_first_line_for_all'))}"
                )
                st.caption(f"Доказательная база: {_format_pmid_links_md(ni.get('evidence_pmids'))}")


def _format_text_or_list(value: Any) -> str:
    """Format scalar text or list of strings cleanly for tables and cards (v1.x trigger_finger compatibility, WR-06)."""
    if isinstance(value, list):
        return "; ".join(c for x in value if (c := _clean_str(x, fallback=""))) or "—"
    return _clean_str(value)


def render_tab_clinical_matrix(bundle: dict[str, Any]) -> None:
    """Tab 2: Universal Clinical Matrix (Stages, Etiology/Pathogenesis, Modalities, Comparator, Complications, Nuances)."""
    kb = bundle["kb_index"]
    nos_id = bundle["nosology_id"]
    db_path_str = str(bundle["db_path"])

    st.subheader("📊 Унифицированная клиническая аналитика нозологии")
    sub1, sub2, sub3, sub4, sub5, sub6 = st.tabs(
        [
            "📐 2.1. Стадии тяжести и Локализации/Подтипы",
            "🧬 2.2. Этиология, Факторы риска и Фазы патогенеза",
            "📈 2.3. Естественное течение vs Методики (Ремиссия / Рецидив / Процедив)",
            "⚖️ 2.4. Бок-о-бок сравнение методик + Доказательства SQLite",
            "⚠️ 2.5. Осложнения (Clavien–Dindo)",
            "🧭 2.6. Клинические компромиссы и серые зоны",
        ]
    )

    with sub1:
        staging = kb.get("staging_and_classification", {})
        st.markdown(
            f"#### {staging.get('classification_name') or staging.get('system_name') or 'Классификация стадий тяжести'}"
        )
        st.caption(
            f"**Шкала измерения:** {staging.get('metric_label') or staging.get('reference') or '—'}"
        )
        stages_list = staging.get("stages", [])
        if stages_list:
            df_stages = pd.DataFrame(stages_list)
            if {"stage_code", "population_share_num", "interventional_share_num"}.issubset(
                df_stages.columns
            ):
                fig_stg = go.Figure()
                fig_stg.add_trace(
                    go.Bar(
                        name="Доля в общей популяции (%)",
                        x=df_stages["stage_code"],
                        y=df_stages["population_share_num"],
                        text=df_stages.get("population_share"),
                        textposition="auto",
                        marker_color="#3b82f6",
                    )
                )
                fig_stg.add_trace(
                    go.Bar(
                        name="Доля среди направляемых на вмешательство (%)",
                        x=df_stages["stage_code"],
                        y=df_stages["interventional_share_num"],
                        text=df_stages.get("interventional_share"),
                        textposition="auto",
                        marker_color="#dc2626",
                    )
                )
                fig_stg.update_layout(
                    barmode="group",
                    title="Популяционная структура стадий против структуры хирургического/интервенционного потока",
                    yaxis_title="Доля пациентов (%)",
                    height=380,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_stg, width="stretch")

            canonical_stage_cols = [
                "stage_code",
                "threshold",
                "population_share",
                "interventional_share",
                "natural_progression",
                "clinical_description",
            ]
            if set(canonical_stage_cols).issubset(df_stages.columns):
                disp_stages = df_stages[canonical_stage_cols].rename(
                    columns={
                        "stage_code": "Стадия / степень",
                        "threshold": "Критерий / порог",
                        "population_share": "Доля в популяции",
                        "interventional_share": "Доля в хирургии/интервенциях",
                        "natural_progression": "Естественное прогрессирование без лечения",
                        "clinical_description": "Клинико-анатомическая характеристика",
                    }
                )
            else:
                disp_stages = df_stages.rename(
                    columns={
                        "stage": "Стадия / степень",
                        "criterion": "Критерий / порог",
                        "pathology_feature": "Патоморфологическая характеристика",
                        "indication_for_treatment": "Показания к лечению",
                        "recommended_first_line": "Рекомендуемая тактика первой линии",
                    }
                )
            st.dataframe(disp_stages, width="stretch", hide_index=True)

        st.divider()
        anat = kb.get("anatomical_or_subtype_distribution", {})
        st.markdown(f"#### {anat.get('dimension_name', 'Анатомические локализации и клинические подтипы')}")
        subtypes_list = anat.get("subtypes", [])
        if subtypes_list:
            df_sub = pd.DataFrame(subtypes_list)
            if "share_num" not in df_sub.columns and "frequency_num" in df_sub.columns:
                df_sub["share_num"] = df_sub["frequency_num"]
            if "share_pct" not in df_sub.columns and "frequency_pct" in df_sub.columns:
                df_sub["share_pct"] = df_sub["frequency_pct"]
            if "locus_or_subtype" not in df_sub.columns:
                if "code" in df_sub.columns:
                    df_sub["locus_or_subtype"] = df_sub["code"]
                elif "name" in df_sub.columns:
                    df_sub["locus_or_subtype"] = df_sub["name"]
            if "category" not in df_sub.columns:
                df_sub["category"] = "Локализация / подтип"
            if "rank" not in df_sub.columns:
                df_sub["rank"] = list(range(1, len(df_sub) + 1))
            if "prognostic_impact" not in df_sub.columns:
                df_sub["prognostic_impact"] = df_sub.get(
                    "clinical_note", df_sub.get("name", "—")
                )

            if {"share_num", "locus_or_subtype", "category"}.issubset(df_sub.columns):
                fig_sub = px.bar(
                    df_sub,
                    x="share_num",
                    y="locus_or_subtype",
                    color="category",
                    orientation="h",
                    text="share_pct" if "share_pct" in df_sub.columns else None,
                    title="Частота вовлечения анатомических локализаций и прогностических подтипов",
                    labels={
                        "share_num": "Средняя доля (%)",
                        "locus_or_subtype": "Локализация / подтип",
                        "category": "Категория",
                    },
                    height=380,
                )
                fig_sub.update_layout(yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_sub, width="stretch")

            sub_cols = [
                c
                for c in ["rank", "category", "locus_or_subtype", "share_pct", "prognostic_impact"]
                if c in df_sub.columns
            ]
            disp_sub = df_sub[sub_cols].rename(
                columns={
                    "rank": "Ранг",
                    "category": "Уровень",
                    "locus_or_subtype": "Локализация / клинический подтип",
                    "share_pct": "Частота поражения",
                    "prognostic_impact": "Прогностическое значение и влияние на выбор методики",
                }
            )
            st.dataframe(disp_sub, width="stretch", hide_index=True)

    with sub2:
        st.markdown("#### 🧬 Этиологические факторы риска и протективные модификаторы")
        factors = kb.get("etiology_and_risk_factors", [])
        if factors:
            df_fac = pd.DataFrame(factors)
            if "evidence_pmids" in df_fac.columns:
                df_fac["evidence_pmids"] = df_fac["evidence_pmids"].apply(_format_text_or_list)
            df_fac = df_fac.rename(
                columns={
                    "factor_name": "Фактор",
                    "factor": "Фактор",
                    "category": "Категория",
                    "direction": "Направленность",
                    "effect_size": "Сила эффекта (OR / HR / h²)",
                    "clinical_notes": "Клиническое значение",
                    "mechanism": "Патогенетический механизм",
                    "evidence_pmids": "PMID",
                }
            )
            st.dataframe(df_fac, width="stretch", hide_index=True)
            st.download_button(
                "📥 Скачать таблицу этиологических факторов (.csv)",
                data=dataframe_to_csv_bytes(df_fac),
                file_name=f"{nos_id}_etiology_risk_factors.csv",
                mime="text/csv",
                key="dl_csv_factors",
            )

        st.divider()
        st.markdown("#### 🔄 Фазы патогенеза и точки приложения терапии (терапевтические окна)")
        for ph in kb.get("pathogenesis_phases", []):
            ph_title = ph.get("phase_name") or ph.get("phase") or ph.get("name") or "Фаза патогенеза"
            ph_events = ph.get("cellular_and_tissue_events") or ph.get("histology") or "—"
            ph_corr = ph.get("clinical_correlate") or ph.get("clinical_manifestation") or "—"
            ph_window = ph.get("therapeutic_window") or ph.get("molecules_and_mediators") or "—"
            with st.expander(f"**{ph_title}**", expanded=True):
                c_a, c_b = st.columns(2)
                c_a.markdown(f"**Клеточные и матриксные процессы:**\n\n{ph_events}")
                c_b.markdown(
                    f"**Клинический коррелят:**\n\n{ph_corr}\n\n"
                    f"🎯 **Терапевтическое окно / медиаторы:** {ph_window}"
                )

    with sub3:
        nat = kb.get("natural_history_and_dynamics", {})
        defs = nat.get("definitions", {})
        st.markdown("#### 🧭 Стандартизованные определения исходов и динамики заболевания")
        untreated_txt = (
            nat.get("untreated_course_summary")
            or nat.get("progression_to_pip_contracture")
            or nat.get("spontaneous_resolution_adults")
            or "—"
        )
        st.info(f"**Естественное развитие без инвазивного лечения:** {untreated_txt}")

        if isinstance(defs, dict) and defs:
            d1, d2 = st.columns(2)
            d1.success(f"✅ **Первичная эффективность и ремиссия:**\n\n{defs.get('primary_remission', '—')}")
            d2.warning(f"🔁 **Истинный рецидив (Relapse):**\n\n{defs.get('true_recurrence', '—')}")
            d3, d4 = st.columns(2)
            d3.error(f"📈 **Процедив (Прогрессирование / Распространение):**\n\n{defs.get('procediv_progression', '—')}")
            d4.info(f"⏳ **Естественное течение (Natural History):**\n\n{defs.get('natural_history', '—')}")
        else:
            d1, d2 = st.columns(2)
            d1.success(
                f"✅ **Спонтанное разрешение:**\n\n{nat.get('spontaneous_resolution_adults', '—')}"
            )
            d2.warning(
                f"⏳ **Динамика послеоперационного периода:**\n\n{nat.get('postoperative_pip_6_month_phenomenon', '—')}"
            )
            if nat.get("untreated_complications"):
                st.error(f"📈 **Осложнения без лечения:**\n\n{nat.get('untreated_complications')}")

        modalities = kb.get("modalities", [])
        if modalities:
            df_mod = pd.DataFrame(modalities)
            all_groups = list(dict.fromkeys(df_mod["group"].tolist()))
            sel_groups = st.multiselect(
                "Фильтр по классам методик лечения:",
                options=all_groups,
                default=all_groups,
                key="sub3_group_filter",
            )
            df_filt = df_mod[df_mod["group"].isin(sel_groups)].copy() if sel_groups else df_mod.copy()

            fig_5y = go.Figure()
            fig_5y.add_trace(
                go.Bar(
                    name="Стойкая 5-летняя ремиссия (%)",
                    x=df_filt["name"],
                    y=df_filt["remission_5y_num"],
                    text=df_filt["remission_5y_pct"],
                    marker_color="#16a34a",
                )
            )
            fig_5y.add_trace(
                go.Bar(
                    name="Истинный рецидив к 5 годам (%)",
                    x=df_filt["name"],
                    y=df_filt["recurrence_5y_num"],
                    text=df_filt["recurrence_5y_overall"],
                    marker_color="#dc2626",
                )
            )
            fig_5y.add_trace(
                go.Bar(
                    name="Процедив / прогрессирование к 5 годам (%)",
                    x=df_filt["name"],
                    y=df_filt["procediv_5y_num"],
                    text=df_filt["procediv_5y"],
                    marker_color="#f59e0b",
                )
            )
            if "reintervention_5y_num" in df_filt.columns:
                fig_5y.add_trace(
                    go.Bar(
                        name="Повторные вмешательства к 5 годам (%)",
                        x=df_filt["name"],
                        y=df_filt["reintervention_5y_num"],
                        text=df_filt.get("reintervention_5y"),
                        marker_color="#6366f1",
                    )
                )
            fig_5y.update_layout(
                barmode="group",
                title="5-летние исходы по методикам: Стойкая ремиссия vs Истинный рецидив vs Процедив vs Повторные операции",
                yaxis_title="Доля пациентов (%, медиана диапазона)",
                xaxis_tickangle=-25,
                height=500,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_5y, width="stretch")

            traj_rows = []
            for _, r in df_filt.iterrows():
                for label, col_num in [
                    ("1–2 года", "recurrence_1_2y_num"),
                    ("3 года", "recurrence_3y_num"),
                    ("5 лет", "recurrence_5y_num"),
                    ("10 лет", "recurrence_10y_num"),
                ]:
                    val = r.get(col_num)
                    if pd.notna(val):
                        traj_rows.append({"Методика": r["name"], "Горизонт наблюдения": label, "Кумулятивный рецидив (%)": val})
            if traj_rows:
                df_traj = pd.DataFrame(traj_rows)
                fig_traj = px.line(
                    df_traj,
                    x="Горизонт наблюдения",
                    y="Кумулятивный рецидив (%)",
                    color="Методика",
                    markers=True,
                    title="Кривые накопления истинного рецидива / прогрессирования от 1–2 до 10 лет",
                    height=440,
                )
                st.plotly_chart(fig_traj, width="stretch")

            df_mod_disp = df_filt.copy()
            for list_col in ("pros", "cons"):
                if list_col in df_mod_disp.columns:
                    df_mod_disp[list_col] = df_mod_disp[list_col].apply(_format_text_or_list)
            disp_mod = df_mod_disp[
                [
                    "group",
                    "name",
                    "target_stage",
                    "primary_efficacy",
                    "remission_5y_pct",
                    "recurrence_1_2y",
                    "recurrence_3y",
                    "recurrence_5y_overall",
                    "recurrence_10y",
                    "procediv_5y",
                    "reintervention_5y",
                    "complications_profile",
                    "recovery_time",
                    "pros",
                    "cons",
                ]
            ].rename(
                columns={
                    "group": "Класс",
                    "name": "Методика лечения",
                    "target_stage": "Целевая стадия / показания",
                    "primary_efficacy": "Первичная эффективность",
                    "remission_5y_pct": "Ремиссия (5 лет)",
                    "recurrence_1_2y": "Рецидив (1–2 г.)",
                    "recurrence_3y": "Рецидив (3 г.)",
                    "recurrence_5y_overall": "Истинный рецидив (5 лет)",
                    "recurrence_10y": "Рецидив (10 лет)",
                    "procediv_5y": "Процедив / прогрессирование (5 лет)",
                    "reintervention_5y": "Повторные вмешательства (5 лет)",
                    "complications_profile": "Профиль осложнений",
                    "recovery_time": "Реабилитация",
                    "pros": "Плюсы (преимущества)",
                    "cons": "Минусы (ограничения и риски)",
                }
            )
            st.dataframe(disp_mod, width="stretch", hide_index=True)
            st.download_button(
                "📥 Скачать полную сравнительную матрицу методик (.csv)",
                data=dataframe_to_csv_bytes(disp_mod),
                file_name=f"{nos_id}_modalities_comparison_matrix.csv",
                mime="text/csv",
                key="dl_csv_modalities",
            )

    with sub4:
        modalities = kb.get("modalities", [])
        if modalities:
            mod_names = [m["name"] for m in modalities]
            default_picks = mod_names[:3]

            picked_names = st.multiselect(
                "Выберите от 2 до 4 методик для детального сравнения бок-о-бок:",
                options=mod_names,
                default=default_picks,
                max_selections=4,
                key="sub4_comparator_picks",
            )
            picked_mods = [m for m in modalities if m["name"] in picked_names]
            if picked_mods:
                cols = st.columns(len(picked_mods))
                for col, mod in zip(cols, picked_mods):
                    sub_dict = mod.get("recurrence_by_subtype", {})
                    sub_lines = " | ".join(
                        f"{k}: {v}" for k, v in sub_dict.items() if not k.endswith("_num")
                    )
                    with col:
                        st.markdown(f"##### {mod['name']}")
                        st.caption(f"**Класс:** {mod['group']} | **Показания:** {mod['target_stage']}")
                        st.markdown(
                            f"- **Первичная эффективность:** {mod['primary_efficacy']}\n"
                            f"- **Стойкая ремиссия (5 лет):** `{mod['remission_5y_pct']}`\n"
                            f"- **Истинный рецидив (1–2 / 3 / 5 / 10 лет):** `{mod['recurrence_1_2y']}` → `{mod['recurrence_3y']}` → **`{mod['recurrence_5y_overall']}`** → `{mod['recurrence_10y']}`\n"
                            f"- **Рецидив по подтипам:** {sub_lines}\n"
                            f"- **Процедив / распространение (5 лет):** `{mod['procediv_5y']}`\n"
                            f"- **Повторные операции (5 лет):** `{mod['reintervention_5y']}`\n"
                            f"- **Осложнения:** {mod['complications_profile']}\n"
                            f"- **Реабилитация:** `{mod['recovery_time']}`"
                        )
                        st.success(f"➕ **Плюсы:** {_format_text_or_list(mod.get('pros'))}")
                        st.error(f"➖ **Минусы:** {_format_text_or_list(mod.get('cons'))}")

        st.divider()
        st.markdown("#### 🔬 Первичные клинические доказательства из базы SQLite (`extracted_clinical_evidence`)")
        df_clin = cached_clinical_evidence(db_path_str)
        if not df_clin.empty:
            grp_opts = ["Все группы вмешательств"] + sorted(
                df_clin["intervention_group"].dropna().unique().tolist()
            )
            chosen_grp = st.selectbox("Фильтр по группе вмешательства в SQLite:", grp_opts, key="sub4_sql_grp")
            df_c_view = (
                df_clin
                if chosen_grp == grp_opts[0]
                else df_clin[df_clin["intervention_group"] == chosen_grp]
            )
            st.caption(f"Отображено клинических записей: **{len(df_c_view)}** из **{len(df_clin)}**")
            st.dataframe(
                df_c_view[
                    [
                        "pmid",
                        "first_author_year",
                        "evidence_tier",
                        "intervention_group",
                        "comparator_group",
                        "study_design",
                        "n_patients",
                        "followup_months",
                        "recurrence_rate_overall",
                        "complications_rate",
                        "key_conclusion",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

    with sub5:
        _render_subtab_complications(kb, nos_id)

    with sub6:
        _render_subtab_clinical_nuances(kb)


def render_tab_prisma_explorer(bundle: dict[str, Any]) -> None:
    """Tab 3: Literature & PRISMA SQLite Explorer across articles, clinical, mechanisms, trials, and complications."""
    nos_id = bundle["nosology_id"]
    db_path_str = str(bundle["db_path"])
    df_art = cached_articles(db_path_str, included_only=True)
    df_clin = cached_clinical_evidence(db_path_str)
    df_mech = cached_mechanisms(db_path_str)
    df_trials = cached_trials(db_path_str)
    df_comp_all = cached_complications(db_path_str, include_casuistry=True)

    st.subheader("📚 Доказательная база и PRISMA-навигатор (SQLite Explorer)")
    with st.expander("📋 Показать сводный отчёт PRISMA (`prisma_stats.md`)", expanded=False):
        if bundle["prisma_stats_md"]:
            st.markdown(bundle["prisma_stats_md"])
        else:
            st.info("Отчёт PRISMA ещё не сгенерирован.")

    if not df_art.empty:
        ch1, ch2 = st.columns(2)
        with ch1:
            yr_counts = (
                df_art.groupby("pub_year", dropna=True)
                .size()
                .reset_index(name="Количество статей")
                .sort_values("pub_year")
            )
            fig_yr = px.bar(
                yr_counts,
                x="pub_year",
                y="Количество статей",
                text="Количество статей",
                title="Динамика включённых публикаций по годам",
                labels={"pub_year": "Год публикации"},
                height=320,
            )
            st.plotly_chart(fig_yr, width="stretch")
        with ch2:
            tier_map = {
                1: "Tier 1 — Систематические обзоры и мета-анализы",
                2: "Tier 2 — РКИ и клинические исследования",
                3: "Tier 3 — Когортные и наблюдательные работы",
                4: "Tier 4 — Кейс-репорты, обзоры и письма",
            }
            t_counts = df_art["evidence_tier"].map(lambda x: tier_map.get(x, f"Tier {x}")).value_counts().reset_index()
            t_counts.columns = ["Уровень доказательности", "Количество"]
            fig_tr = px.pie(
                t_counts,
                names="Уровень доказательности",
                values="Количество",
                hole=0.42,
                title="Распределение статей по уровням доказательности (Tier 1–4)",
                height=320,
            )
            st.plotly_chart(fig_tr, width="stretch")

    table_choice = st.radio(
        "Выберите таблицу базы данных SQLite для интерактивного поиска и выгрузки:",
        options=[
            f"1. Включённые статьи PRISMA ({len(df_art)})",
            f"2. Извлечённые клинические доказательства ({len(df_clin)})",
            f"3. Извлечённые этиопатогенетические механизмы ({len(df_mech)})",
            f"4. Реестр клинических исследований ClinicalTrials.gov ({len(df_trials)})",
            f"5. Извлечённые осложнения лечения (extracted_complications) ({len(df_comp_all)})",
        ],
        horizontal=True,
        key="tab3_table_choice",
    )

    if table_choice.startswith("1."):
        if df_art.empty:
            st.info("В базе данных пока нет включённых статей PRISMA (`articles`: 0 записей).")
            return
        f1, f2, f3 = st.columns([1, 1, 2])
        with f1:
            tiers = sorted(df_art["evidence_tier"].dropna().unique().tolist())
            sel_tiers = st.multiselect("Уровень Tier:", options=tiers, default=tiers, key="t3_art_tiers")
        with f2:
            xml_only = st.checkbox("Только с полнотекстом PMC XML", value=False, key="t3_art_xml")
        with f3:
            kw = st.text_input("Поиск по заголовку, абстракту, авторам или PMID:", value="", key="t3_art_kw")

        view = df_art.copy()
        if sel_tiers:
            view = view[view["evidence_tier"].isin(sel_tiers)]
        if xml_only:
            view = view[view["has_fulltext_xml"] == 1]
        if kw.strip():
            q = kw.strip().lower()
            mask = (
                view["title"].fillna("").str.lower().str.contains(q, regex=False)
                | view["abstract"].fillna("").str.lower().str.contains(q, regex=False)
                | view["authors"].fillna("").str.lower().str.contains(q, regex=False)
                | view["pmid"].fillna("").astype(str).str.contains(q, regex=False)
            )
            view = view[mask]

        st.caption(f"Найдено статей: **{len(view)}** из **{len(df_art)}**")
        disp_cols = [
            "pmid",
            "pmcid",
            "pub_year",
            "evidence_tier",
            "title",
            "journal",
            "authors",
            "clusters",
            "has_fulltext_xml",
            "pubmed_url",
            "doi_url",
        ]
        st.dataframe(
            view[disp_cols],
            width="stretch",
            hide_index=True,
            column_config={
                "pubmed_url": st.column_config.LinkColumn("PubMed", display_text="Открыть PubMed"),
                "doi_url": st.column_config.LinkColumn("DOI", display_text="Открыть DOI"),
            },
        )
        st.download_button(
            "📥 Скачать отфильтрованный список статей (.csv)",
            data=dataframe_to_csv_bytes(view[disp_cols]),
            file_name=f"{nos_id}_articles_filtered.csv",
            mime="text/csv",
            key="dl_csv_articles",
        )

    elif table_choice.startswith("2."):
        if df_clin.empty:
            st.info("В базе данных пока нет извлечённых клинических доказательств (`extracted_clinical_evidence`: 0 записей).")
            return
        c1, c2 = st.columns(2)
        with c1:
            grps = ["Все"] + sorted(df_clin["intervention_group"].dropna().unique().tolist())
            g_pick = st.selectbox("Группа вмешательства:", grps, key="t3_clin_grp")
        with c2:
            kw_c = st.text_input("Поиск по исходам, осложнениям, выводу или PMID:", value="", key="t3_clin_kw")

        view = df_clin.copy()
        if g_pick != "Все":
            view = view[view["intervention_group"] == g_pick]
        if kw_c.strip():
            q = kw_c.strip().lower()
            view = view[
                view["key_conclusion"].fillna("").str.lower().str.contains(q, regex=False)
                | view["complications_summary"].fillna("").str.lower().str.contains(q, regex=False)
                | view["pmid"].fillna("").astype(str).str.contains(q, regex=False)
            ]
        st.caption(f"Найдено клинических записей: **{len(view)}** из **{len(df_clin)}**")
        st.dataframe(view, width="stretch", hide_index=True)
        st.download_button(
            "📥 Скачать клинические доказательства (.csv)",
            data=dataframe_to_csv_bytes(view),
            file_name=f"{nos_id}_clinical_evidence.csv",
            mime="text/csv",
            key="dl_csv_clin",
        )

    elif table_choice.startswith("3."):
        if df_mech.empty:
            st.info("В базе данных пока нет извлечённых патогенетических механизмов (`extracted_mechanisms`: 0 записей).")
            return
        c1, c2 = st.columns(2)
        with c1:
            cats = ["Все"] + sorted(df_mech["category"].dropna().unique().tolist())
            c_pick = st.selectbox("Категория механизма:", cats, key="t3_mech_cat")
        with c2:
            kw_m = st.text_input("Поиск по генам, цитокинам, рецепторам или сигнальным путям:", value="", key="t3_mech_kw")

        view = df_mech.copy()
        if c_pick != "Все":
            view = view[view["category"] == c_pick]
        if kw_m.strip():
            q = kw_m.strip().lower()
            view = view[
                view["targets_genes_pathways"].fillna("").str.lower().str.contains(q, regex=False)
                | view["mechanism_summary"].fillna("").str.lower().str.contains(q, regex=False)
                | view["pmid"].fillna("").astype(str).str.contains(q, regex=False)
            ]
        st.caption(f"Найдено патогенетических записей: **{len(view)}** из **{len(df_mech)}**")
        st.dataframe(view, width="stretch", hide_index=True)
        st.download_button(
            "📥 Скачать патогенетические механизмы (.csv)",
            data=dataframe_to_csv_bytes(view),
            file_name=f"{nos_id}_mechanisms.csv",
            mime="text/csv",
            key="dl_csv_mech",
        )

    elif table_choice.startswith("4."):
        if df_trials.empty:
            st.info("В базе данных пока нет протоколов ClinicalTrials.gov (`clinical_trials`: 0 записей).")
            return
        c1, c2 = st.columns(2)
        with c1:
            statuses = ["Все"] + sorted(df_trials["overall_status"].dropna().unique().tolist())
            s_pick = st.selectbox("Статус исследования:", statuses, key="t3_tr_status")
        with c2:
            kw_t = st.text_input("Поиск по NCT ID, вмешательству или названию:", value="", key="t3_tr_kw")

        view = df_trials.copy()
        if s_pick != "Все":
            view = view[view["overall_status"] == s_pick]
        if kw_t.strip():
            q = kw_t.strip().lower()
            view = view[
                view["nct_id"].fillna("").str.lower().str.contains(q, regex=False)
                | view["brief_title"].fillna("").str.lower().str.contains(q, regex=False)
                | view["interventions"].fillna("").str.lower().str.contains(q, regex=False)
            ]
        st.caption(f"Найдено протоколов ClinicalTrials.gov: **{len(view)}** из **{len(df_trials)}**")
        st.dataframe(
            view,
            width="stretch",
            hide_index=True,
            column_config={
                "ctgov_url": st.column_config.LinkColumn("ClinicalTrials.gov", display_text="Открыть NCT"),
            },
        )
        st.download_button(
            "📥 Скачать протоколы ClinicalTrials.gov (.csv)",
            data=dataframe_to_csv_bytes(view),
            file_name=f"{nos_id}_clinical_trials.csv",
            mime="text/csv",
            key="dl_csv_trials",
        )

    else:
        if df_comp_all.empty:
            st.info(
                "В базе данных этой нозологии нет записей в таблице `extracted_complications` "
                "(0 записей, режим строго read-only; характерно для архивных нозологий `v1.x`)."
            )
            return

        show_casuistry = st.checkbox(
            "Показать редкую казуистику (Tier 4 / N<20)",
            value=False,
            key="t3_comp_casuistry",
        )
        df_comp = cached_complications(db_path_str, include_casuistry=show_casuistry)

        # Derive multiselect options/defaults strictly from full df_comp_all so toggling casuistry
        # never hides casuistry-only modalities/grades due to stale session_state defaults.
        mod_opts = list(dict.fromkeys(df_comp_all["modality"].dropna().astype(str).tolist()))
        raw_cds = list(dict.fromkeys(df_comp_all["clavien_dindo_grade"].dropna().astype(str).tolist()))
        cd_opts = [g for g in CLAVIEN_DINDO_ORDER if g in raw_cds] + [
            g for g in raw_cds if g not in CLAVIEN_DINDO_ORDER
        ]
        raw_revs = list(dict.fromkeys(df_comp_all["reversibility"].dropna().astype(str).tolist()))
        rev_opts = [r for r in VALID_REVERSIBILITY if r in raw_revs] + [
            r for r in raw_revs if r not in VALID_REVERSIBILITY
        ]
        raw_classes = list(dict.fromkeys(df_comp_all["event_class"].dropna().astype(str).tolist()))
        class_opts = [c for c in VALID_EVENT_CLASS if c in raw_classes] + [
            c for c in raw_classes if c not in VALID_EVENT_CLASS
        ]

        cf1, cf2, cf3, cf4 = st.columns(4)
        sel_mods = cf1.multiselect(
            "Методика:",
            options=mod_opts,
            default=mod_opts,
            key="t3_comp_mod",
        )
        sel_cds = cf2.multiselect(
            "Clavien–Dindo:",
            options=cd_opts,
            default=cd_opts,
            key="t3_comp_cd",
        )
        sel_revs = cf3.multiselect(
            "Обратимость:",
            options=rev_opts,
            default=rev_opts,
            format_func=lambda v: REVERSIBILITY_LABELS_RU.get(v, v),
            key="t3_comp_rev",
        )
        sel_classes = cf4.multiselect(
            "Класс события:",
            options=class_opts,
            default=class_opts,
            format_func=lambda v: EVENT_CLASS_LABELS_RU.get(v, v),
            key="t3_comp_class",
        )
        kw_comp = st.text_input(
            "Поиск по осложнению, анатомическому субстрату, профилактике/лечению или PMID:",
            value="",
            key="t3_comp_kw",
        )

        if df_comp.empty:
            st.info(
                "Все записи таблицы `extracted_complications` в этой базе относятся к редкой казуистике "
                "(`Tier 4 / N<20`). Включите флажок «Показать редкую казуистику (Tier 4 / N<20)», чтобы отобразить их."
            )
            return

        view = df_comp.copy()
        if sel_mods:
            view = view[view["modality"].astype(str).isin(sel_mods)]
        if sel_cds:
            view = view[view["clavien_dindo_grade"].astype(str).isin(sel_cds)]
        if sel_revs:
            view = view[view["reversibility"].astype(str).isin(sel_revs)]
        if sel_classes:
            view = view[view["event_class"].astype(str).isin(sel_classes)]
        if kw_comp.strip():
            q = kw_comp.strip().lower()
            mask = (
                view["complication_name"].fillna("").astype(str).str.lower().str.contains(q, regex=False)
                | view["anatomical_substrate"].fillna("").astype(str).str.lower().str.contains(q, regex=False)
                | view["prevention_and_management"].fillna("").astype(str).str.lower().str.contains(q, regex=False)
                | view["modality"].fillna("").astype(str).str.lower().str.contains(q, regex=False)
                | view["pmid"].fillna("").astype(str).str.contains(q, regex=False)
            )
            view = view[mask]

        view["event_class_ru"] = view["event_class"].map(
            lambda v: EVENT_CLASS_LABELS_RU.get(_clean_str(v, ""), _clean_str(v, "—"))
        )
        view["reversibility_ru"] = view["reversibility"].map(
            lambda v: REVERSIBILITY_LABELS_RU.get(_clean_str(v, ""), _clean_str(v, "—"))
        )

        comp_cols = [
            "pmid",
            "first_author_year",
            "evidence_tier",
            "modality",
            "complication_name",
            "event_class_ru",
            "clavien_dindo_grade",
            "frequency_pct",
            "reversibility_ru",
            "time_window",
            "anatomical_substrate",
            "prevention_and_management",
            "sample_size",
            "is_rare_casuistry",
            "pubmed_url",
            "doi_url",
        ]
        disp_comp = view[comp_cols].copy()

        st.caption(
            f"Найдено записей осложнений: **{len(disp_comp)}** из **{len(df_comp)}** "
            f"(всего в БД с казуистикой: **{len(df_comp_all)}**)"
        )
        st.dataframe(
            disp_comp,
            width="stretch",
            hide_index=True,
            column_config={
                "pmid": st.column_config.Column("PMID"),
                "first_author_year": st.column_config.Column("Автор и год"),
                "evidence_tier": st.column_config.Column("Tier"),
                "modality": st.column_config.Column("Методика"),
                "complication_name": st.column_config.Column("Осложнение"),
                "event_class_ru": st.column_config.Column("Класс события"),
                "clavien_dindo_grade": st.column_config.Column("Clavien–Dindo"),
                "frequency_pct": st.column_config.Column("Частота (%)"),
                "reversibility_ru": st.column_config.Column("Обратимость"),
                "time_window": st.column_config.Column("Окно разрешения"),
                "anatomical_substrate": st.column_config.Column("Анатомический субстрат"),
                "prevention_and_management": st.column_config.Column("Профилактика и лечение"),
                "sample_size": st.column_config.Column("Выборка N"),
                "is_rare_casuistry": st.column_config.Column("Казуистика"),
                "pubmed_url": st.column_config.LinkColumn("PubMed", display_text="Открыть PubMed"),
                "doi_url": st.column_config.LinkColumn("DOI", display_text="Открыть DOI"),
            },
        )
        csv_view = disp_comp.rename(
            columns={
                "pmid": "PMID",
                "first_author_year": "Автор и год",
                "evidence_tier": "Tier",
                "modality": "Методика",
                "complication_name": "Осложнение",
                "event_class_ru": "Класс события",
                "clavien_dindo_grade": "Clavien–Dindo",
                "frequency_pct": "Частота (%)",
                "reversibility_ru": "Обратимость",
                "time_window": "Окно разрешения",
                "anatomical_substrate": "Анатомический субстрат",
                "prevention_and_management": "Профилактика и лечение",
                "sample_size": "Выборка N",
                "is_rare_casuistry": "Казуистика (Tier 4 / N<20)",
                "pubmed_url": "PubMed URL",
                "doi_url": "DOI URL",
            }
        )
        st.download_button(
            "📥 Скачать извлечённые осложнения (.csv)",
            data=dataframe_to_csv_bytes(csv_view),
            file_name=f"{nos_id}_extracted_complications.csv",
            mime="text/csv",
            key="dl_csv_comp",
        )


def render_tab_configurator_and_audit(bundle: dict[str, Any]) -> None:
    """Tab 4: Read-Only Verification Audit Certificate & v2.0 New Nosology YAML Configurator (D-05, T-19-01, T-19-03)."""
    st.subheader("🛡️ Аудит верификации ссылок и Конфигуратор новых нозологий")
    col_audit, col_cfg = st.columns([1, 1])

    with col_audit:
        st.markdown("#### ✅ Сертификат верификации (`Zero-Tolerance Gate`)")
        if st.button(
            "🔄 Запустить повторный аудит verify_reports.py --verify --read-only",
            key="btn_run_verify",
        ):
            try:
                safe_nos_id = validate_nosology_id(bundle["nosology_id"])
                res = subprocess.run(
                    [
                        sys.executable,
                        str(PROJECT_ROOT / "src" / "verify_reports.py"),
                        "--nosology",
                        safe_nos_id,
                        "--verify",
                        "--read-only",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    shell=False,
                    timeout=60,
                )
                if res.returncode == 0:
                    st.success("Аудит успешно пройден (read-only): 0 галлюцинаций и 0 запрещённых ИИ-штампов.")
                else:
                    st.error("Обнаружены замечания при проверке.")
                st.code(res.stdout + ("\n" + res.stderr if res.stderr else ""))
            except subprocess.TimeoutExpired:
                st.error("Превышено время ожидания аудита verify_reports.py (60 с).")
            except (ValueError, OSError, UnicodeError) as exc:
                st.error(f"Не удалось выполнить аудит verify_reports.py: {exc}")

        if bundle["verification_audit_md"]:
            st.markdown(bundle["verification_audit_md"])
        else:
            st.info("Файл `verification_audit.md` отсутствует.")

    with col_cfg:
        st.markdown("#### ⚙️ Добавить новую нозологию (`configs/<id>.yaml`)")
        st.caption(
            "Платформа полностью универсальна: настройте клинический профиль сбора осложнений (`v2.0`) и "
            "создайте YAML-профиль любой нозологии для запуска 4-фазного пайплайна сбора и синтеза."
        )

        # Reactive complications profile & query terms ABOVE st.form so preview updates immediately (D-05.1, D-05.2, Pitfall 3)
        profile_choice = st.radio(
            "Клинический профиль нозологии (сбор осложнений):",
            options=[
                "Хирургическая / смешанная (surgical_focus: true)",
                "Чисто консервативная (surgical_focus: false, treatment_profile: conservative)",
            ],
            horizontal=False,
            key="t4_profile_radio",
        )
        is_surgical = "surgical_focus: true" in profile_choice
        treatment_profile = "surgical" if is_surgical else "conservative"

        mesh_val = st.text_input(
            "Термины MeSH (через запятую):",
            value="Carpal Tunnel Syndrome, Median Neuropathy",
            key="t4_mesh_terms",
        )
        core_terms_val = st.text_input(
            "Ключевые термины нозологии (triage_rules.core_terms, через запятую):",
            value="carpal tunnel syndrome, carpal tunnel release, median nerve decompression",
            key="t4_core_terms",
        )

        mesh_terms_list = [m.strip() for m in mesh_val.split(",") if m.strip()]
        core_terms_list = [t.strip() for t in core_terms_val.split(",") if t.strip()]
        preview_cfg = {
            "nosology": {
                "mesh_terms": mesh_terms_list,
                "surgical_focus": is_surgical,
                "treatment_profile": treatment_profile,
            },
            "triage_rules": {"core_terms": core_terms_list},
            "date_range": {"start_year": 2016, "end_year": 2026},
        }
        preview_queries = build_complications_queries(preview_cfg)

        with st.container(border=True):
            st.markdown(
                f"**Живой предпросмотр автогенерируемых запросов осложнений** "
                f"(профиль: `{preview_queries['profile']}`, `surgical_focus={preview_queries['surgical_focus']}`)"
            )
            st.caption("PubMed (`complications_queries.pubmed`):")
            st.code(preview_queries["pubmed"], language="text")
            st.caption("Europe PMC (`complications_queries.europepmc`):")
            st.code(preview_queries["europepmc"], language="text")

        with st.form("new_nosology_form"):
            new_id = st.text_input(
                "ID нозологии (латиницей):",
                value="carpal_tunnel_syndrome",
                key="t4_new_id",
            )
            new_ru = st.text_input(
                "Название (RU):",
                value="Синдром запястного канала",
                key="t4_new_ru",
            )
            new_en = st.text_input(
                "Название (EN):",
                value="Carpal Tunnel Syndrome",
                key="t4_new_en",
            )
            c_icd10, c_icd11 = st.columns(2)
            icd10_val = c_icd10.text_input("Код МКБ-10:", value="G56.0", key="t4_icd10")
            icd11_val = c_icd11.text_input("Код МКБ-11:", value="8C10.0", key="t4_icd11")
            pubmed_q = st.text_area(
                "Поисковый запрос PubMed / Europe PMC:",
                value='("Carpal Tunnel Syndrome"[MeSH] OR "carpal tunnel syndrome"[tiab] OR "carpal tunnel release"[tiab])',
                key="t4_pubmed_q",
            )
            ct_cond = st.text_input(
                "Условие для ClinicalTrials.gov:",
                value="Carpal Tunnel Syndrome",
                key="t4_ct_cond",
            )
            comp_override_pm = st.text_area(
                "Ручное переопределение complications_queries.pubmed (опционально):",
                value="",
                placeholder="Оставьте пустым для автогенерации по профилю выше",
                key="t4_comp_override_pm",
            )
            comp_override_epmc = st.text_area(
                "Ручное переопределение complications_queries.europepmc (опционально):",
                value="",
                placeholder="Оставьте пустым для автогенерации по профилю выше",
                key="t4_comp_override_epmc",
            )
            submitted = st.form_submit_button("💾 Сохранить конфигурацию в `configs/`")

        if submitted:
            payload: dict[str, Any] = {
                "nosology": {
                    "id": new_id.strip().lower(),
                    "name_ru": new_ru.strip(),
                    "name_en": new_en.strip(),
                    "icd10": icd10_val.strip(),
                    "icd11": icd11_val.strip(),
                    "mesh_terms": mesh_terms_list,
                    "surgical_focus": is_surgical,
                    "treatment_profile": treatment_profile,
                },
                "date_range": {"start_year": 2016, "end_year": 2026},
                "queries": {
                    "pubmed": pubmed_q.strip(),
                    "europepmc": pubmed_q.strip(),
                    "openalex_search": new_en.strip(),
                    "clinical_trials_condition": ct_cond.strip(),
                },
                "triage_rules": {
                    "core_terms": core_terms_list,
                },
            }
            comp_overrides: dict[str, str] = {}
            if comp_override_pm.strip():
                comp_overrides["pubmed"] = comp_override_pm.strip()
            if comp_override_epmc.strip():
                comp_overrides["europepmc"] = comp_override_epmc.strip()
            if comp_overrides:
                payload["complications_queries"] = comp_overrides

            try:
                saved_path = save_new_nosology_config(payload)
                st.success(f"Конфигурация сохранена: `{saved_path}`")
                st.code(saved_path.read_text(encoding="utf-8"), language="yaml")
            except PermissionError as exc:
                st.error(f"Защита замороженной нозологии v1.x: {exc}")
            except ValueError as exc:
                st.error(f"Ошибка валидации параметров нозологии: {exc}")
            except OSError as exc:
                st.error(f"Ошибка записи файла конфигурации: {exc}")

        st.markdown("##### 🚀 Команды запуска пайплайна для новой нозологии")
        st.code(
            "# Фаза 1: Сбор PubMed / Europe PMC / OpenAlex / ClinicalTrials и PRISMA-триаж\n"
            "uv run src/harvester.py --config configs/<id>.yaml\n"
            "uv run src/triage.py --config configs/<id>.yaml\n\n"
            "# Фаза 3–4: Компиляция библиографии, аудит и запуск веб-интерфейса\n"
            "uv run src/verify_reports.py --nosology <id> --verify --read-only\n"
            "uv run streamlit run app.py",
            language="bash",
        )


def render_streamlit_app() -> None:
    """Main Streamlit UI entry point."""
    st.set_page_config(
        page_title="Универсальная платформа клинического синтеза (2016–2026)",
        page_icon="🧬",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    nosologies = discover_nosologies()
    _, bundle = render_sidebar(nosologies)
    meta = bundle["kb_index"].get("nosology_meta", {})

    st.title(f"🧬 {meta.get('title_ru', bundle['nosology_id'])} ({meta.get('icd10', '—')})")
    st.caption(
        f"**Англоязычный эквивалент:** {meta.get('title_en', '—')} | "
        f"**Горизонт доказательной базы:** {meta.get('time_horizon', '2016–2026')} | "
        f"**Архитектура:** универсальная нозологически-независимая схема (`D-01`–`D-03`)"
    )

    t1, t2, t3, t4 = st.tabs(
        [
            "📑 1. Аналитические отчёты (3 режима)",
            "📊 2. Унифицированная клиническая аналитика (Стадии / Ремиссия / Рецидив / Процедив)",
            "📚 3. База литературы и PRISMA-навигатор (SQLite)",
            "🛡️ 4. Аудит верификации и Конфигуратор нозологий",
        ]
    )
    with t1:
        render_tab_reports(bundle)
    with t2:
        render_tab_clinical_matrix(bundle)
    with t3:
        render_tab_prisma_explorer(bundle)
    with t4:
        render_tab_configurator_and_audit(bundle)


def run_self_test() -> int:
    """Automated headless verification of schema, SQLite queries, exports, and Streamlit AppTest (`UI-01`, `UI-02`, `D-08.3`)."""
    import os

    os.environ["INFO_SEARCHER_APPTEST_ACTIVE"] = "1"
    sys.argv = [arg for arg in sys.argv if arg != "--self-test"]

    print("[1/3] Running universal schema & export verification across all discovered nosologies...")
    discovered = discover_nosologies()
    target_nosologies = discovered if discovered else [{"id": "prom"}]
    for item in target_nosologies:
        rc = verify_universal_schema(item["id"])
        if rc != 0:
            return rc

    print("[2/3] Running headless Streamlit AppTest on `app.py` for all discovered nosologies...")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(Path(__file__).resolve()), default_timeout=60)
    at.run(timeout=60)
    if len(at.exception) > 0:
        print(f"[FAIL] Streamlit AppTest initial run raised {len(at.exception)} exception(s):")
        for exc in at.exception:
            print(exc)
        return 1

    for item in target_nosologies:
        nos_id = item["id"]
        at.selectbox(key="sidebar_nosology_select").set_value(nos_id).run(timeout=60)
        if len(at.exception) > 0:
            print(f"[FAIL] Selecting nosology '{nos_id}' raised exception: {at.exception[0]}")
            return 1

        tab_labels = [t.label for t in at.tabs]
        if not any("2.5" in lbl for lbl in tab_labels) or not any("2.6" in lbl for lbl in tab_labels):
            print(f"[FAIL] Subtabs 2.5/2.6 missing for '{nos_id}': {tab_labels}")
            return 1

        mode_opts = list(at.radio(key="tab1_report_mode").options)
        mode_a = next((o for o in mode_opts if o.startswith("Режим А")), None)
        mode_b = next((o for o in mode_opts if o.startswith("Режим Б")), None)
        mode_c = next((o for o in mode_opts if o.startswith("Режим В")), None)
        if not mode_b or not mode_c:
            print(f"[FAIL] Missing Mode B/C options for '{nos_id}': {mode_opts}")
            return 1

        at.radio(key="tab1_report_mode").set_value(mode_b).run(timeout=60)
        if len(at.exception) > 0:
            print(f"[FAIL] Mode B raised exception for '{nos_id}': {at.exception[0]}")
            return 1

        at.radio(key="tab1_report_mode").set_value(mode_c).run(timeout=60)
        if len(at.exception) > 0:
            print(f"[FAIL] Mode C raised exception for '{nos_id}': {at.exception[0]}")
            return 1

        if mode_a:
            at.radio(key="tab1_report_mode").set_value(mode_a).run(timeout=60)
            if len(at.exception) > 0:
                print(f"[FAIL] Mode A reset raised exception for '{nos_id}': {at.exception[0]}")
                return 1

        t3_opts = list(at.radio(key="tab3_table_choice").options)
        opt1 = next((o for o in t3_opts if o.startswith("1.")), None)
        opt5 = next((o for o in t3_opts if o.startswith("5.")), None)
        if not opt5:
            print(f"[FAIL] Missing Tab 3 option 5 (extracted_complications) for '{nos_id}': {t3_opts}")
            return 1

        at.radio(key="tab3_table_choice").set_value(opt5).run(timeout=60)
        if len(at.exception) > 0:
            print(f"[FAIL] Tab 3 option 5 raised exception for '{nos_id}': {at.exception[0]}")
            return 1

        if opt1:
            at.radio(key="tab3_table_choice").set_value(opt1).run(timeout=60)
            if len(at.exception) > 0:
                print(f"[FAIL] Tab 3 option 1 reset raised exception for '{nos_id}': {at.exception[0]}")
                return 1

    print(
        f"[3/3] [PASS] Streamlit AppTest verified {len(target_nosologies)} nosology(ies), "
        f"all 4 tabs + subtabs 2.5/2.6, dynamic Mode C, and Tab 3 option 5 with 0 exceptions "
        f"(metrics={len(at.metric)}, dataframes={len(at.dataframe)}, tabs={len(at.tabs)})."
    )
    return 0


if __name__ == "__main__":
    import os

    if "--self-test" in sys.argv and os.environ.get("INFO_SEARCHER_APPTEST_ACTIVE") != "1":
        sys.exit(run_self_test())
    else:
        render_streamlit_app()
