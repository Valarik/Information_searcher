# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "streamlit>=1.38.0",
#   "pandas>=2.2.0",
#   "plotly>=5.22.0",
#   "markdown>=3.6",
#   "pyyaml>=6.0.1",
# ]
# ///
"""Universal Multi-Nosology Clinical Evidence & Synthesis Platform (`app.py`, Phase 4: UI-01, D-01..D-03).

Launch interactively:
    uv run streamlit run app.py

Run automated self-test (schema + SQLite + exports + headless Streamlit AppTest):
    uv run app.py --self-test
"""

from __future__ import annotations

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
import yaml

from src.docx_exporter import (
    build_docx_bytes_from_markdown,
    build_docx_bytes_from_markdown_sections,
)
from src.universal_schema import (
    dataframe_to_csv_bytes,
    discover_nosologies,
    load_nosology_bundle,
    query_articles_df,
    query_clinical_evidence_df,
    query_clinical_trials_df,
    query_mechanisms_df,
    render_printable_html,
    save_new_nosology_config,
    split_markdown_sections,
    verify_universal_schema,
)


@st.cache_data(show_spinner=False)
def cached_bundle(nosology_id: str) -> dict[str, Any]:
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

        bundle = cached_bundle(selected_id)
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

        st.divider()
        st.markdown("### 📥 Быстрый экспорт отчётов (Word .docx / MD / HTML)")
        DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if bundle["dissertation_md"]:
            st.download_button(
                "📘 Скачать Диссертацию (.docx)",
                data=build_docx_bytes_from_markdown(bundle["dissertation_md"]),
                file_name=f"{selected_id}_dissertation_report.docx",
                mime=DOCX_MIME,
                use_container_width=True,
                key="sb_dl_diss_docx",
            )
        if bundle["executive_summary_md"]:
            st.download_button(
                "⚡ Скачать Краткий отчёт (.docx)",
                data=build_docx_bytes_from_markdown(bundle["executive_summary_md"]),
                file_name=f"{selected_id}_executive_summary.docx",
                mime=DOCX_MIME,
                use_container_width=True,
                key="sb_dl_exec_docx",
            )
        if bundle["dissertation_md"] and bundle["executive_summary_md"]:
            full_sections = [bundle["executive_summary_md"], bundle["dissertation_md"]] + [
                m["content"] for m in bundle.get("kb_modules", []) if m.get("content")
            ]
            st.download_button(
                "📚 Скачать Полное досье (.docx)",
                data=build_docx_bytes_from_markdown_sections(full_sections),
                file_name=f"{selected_id}_full_clinical_dossier.docx",
                mime=DOCX_MIME,
                use_container_width=True,
                key="sb_dl_full_docx",
            )
        if bundle["dissertation_md"]:
            st.download_button(
                "📄 Скачать Диссертацию (.md)",
                data=bundle["dissertation_md"].encode("utf-8"),
                file_name=f"{selected_id}_dissertation_report.md",
                mime="text/markdown",
                use_container_width=True,
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
                use_container_width=True,
                key="sb_dl_diss_html",
            )

    return selected_id, bundle


def render_tab_reports(bundle: dict[str, Any]) -> None:
    """Tab 1: 3-Mode Report Reader with section navigation, keyword search, and MD/HTML export."""
    kb = bundle["kb_index"]
    meta = kb.get("nosology_meta", {})
    nos_id = bundle["nosology_id"]

    st.subheader("📑 Аналитические отчёты: 3 режима представления")
    col_mode, col_search = st.columns([2, 1])
    with col_mode:
        report_mode = st.radio(
            "Режим отчёта:",
            options=[
                "Режим А — Диссертационная монография (полный синтез)",
                "Режим Б — Краткий клинический отчёт (Executive Summary)",
                "Режим В — Модульная база знаний (5 тематических модулей)",
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
            data=build_docx_bytes_from_markdown(md_text),
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
        mod_options["__all__"] = "📚 Показать все 5 модулей базы знаний подряд"
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


def render_tab_clinical_matrix(bundle: dict[str, Any]) -> None:
    """Tab 2: Universal Clinical Matrix (Stages, Etiology/Pathogenesis, Natural History vs Modalities, Comparator)."""
    kb = bundle["kb_index"]
    nos_id = bundle["nosology_id"]
    db_path_str = str(bundle["db_path"])

    st.subheader("📊 Унифицированная клиническая аналитика нозологии")
    sub1, sub2, sub3, sub4 = st.tabs(
        [
            "📐 2.1. Стадии тяжести и Локализации/Подтипы",
            "🧬 2.2. Этиология, Факторы риска и Фазы патогенеза",
            "📈 2.3. Естественное течение vs Методики (Ремиссия / Рецидив / Процедив)",
            "⚖️ 2.4. Бок-о-бок сравнение методик + Доказательства SQLite",
        ]
    )

    with sub1:
        staging = kb.get("staging_and_classification", {})
        st.markdown(f"#### {staging.get('classification_name', 'Классификация стадий тяжести')}")
        st.caption(f"**Шкала измерения:** {staging.get('metric_label', '—')}")
        stages_list = staging.get("stages", [])
        if stages_list:
            df_stages = pd.DataFrame(stages_list)
            fig_stg = go.Figure()
            fig_stg.add_trace(
                go.Bar(
                    name="Доля в общей популяции (%)",
                    x=df_stages["stage_code"],
                    y=df_stages["population_share_num"],
                    text=df_stages["population_share"],
                    textposition="auto",
                    marker_color="#3b82f6",
                )
            )
            fig_stg.add_trace(
                go.Bar(
                    name="Доля среди направляемых на вмешательство (%)",
                    x=df_stages["stage_code"],
                    y=df_stages["interventional_share_num"],
                    text=df_stages["interventional_share"],
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
            st.plotly_chart(fig_stg, use_container_width=True)

            disp_stages = df_stages[
                [
                    "stage_code",
                    "threshold",
                    "population_share",
                    "interventional_share",
                    "natural_progression",
                    "clinical_description",
                ]
            ].rename(
                columns={
                    "stage_code": "Стадия / степень",
                    "threshold": "Критерий / порог",
                    "population_share": "Доля в популяции",
                    "interventional_share": "Доля в хирургии/интервенциях",
                    "natural_progression": "Естественное прогрессирование без лечения",
                    "clinical_description": "Клинико-анатомическая характеристика",
                }
            )
            st.dataframe(disp_stages, use_container_width=True, hide_index=True)

        st.divider()
        anat = kb.get("anatomical_or_subtype_distribution", {})
        st.markdown(f"#### {anat.get('dimension_name', 'Анатомические локализации и клинические подтипы')}")
        subtypes_list = anat.get("subtypes", [])
        if subtypes_list:
            df_sub = pd.DataFrame(subtypes_list)
            fig_sub = px.bar(
                df_sub,
                x="share_num",
                y="locus_or_subtype",
                color="category",
                orientation="h",
                text="share_pct",
                title="Частота вовлечения анатомических локализаций и прогностических подтипов",
                labels={
                    "share_num": "Средняя доля (%)",
                    "locus_or_subtype": "Локализация / подтип",
                    "category": "Категория",
                },
                height=380,
            )
            fig_sub.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_sub, use_container_width=True)

            disp_sub = df_sub[
                ["rank", "category", "locus_or_subtype", "share_pct", "prognostic_impact"]
            ].rename(
                columns={
                    "rank": "Ранг",
                    "category": "Уровень",
                    "locus_or_subtype": "Локализация / клинический подтип",
                    "share_pct": "Частота поражения",
                    "prognostic_impact": "Прогностическое значение и влияние на выбор методики",
                }
            )
            st.dataframe(disp_sub, use_container_width=True, hide_index=True)

    with sub2:
        st.markdown("#### 🧬 Этиологические факторы риска и протективные модификаторы")
        factors = kb.get("etiology_and_risk_factors", [])
        if factors:
            df_fac = pd.DataFrame(factors).rename(
                columns={
                    "factor_name": "Фактор",
                    "category": "Категория",
                    "direction": "Направленность",
                    "effect_size": "Сила эффекта (OR / HR / h²)",
                    "clinical_notes": "Клиническое значение",
                    "mechanism": "Патогенетический механизм",
                }
            )
            st.dataframe(df_fac, use_container_width=True, hide_index=True)
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
            with st.expander(f"**{ph.get('phase_name')}**", expanded=True):
                c_a, c_b = st.columns(2)
                c_a.markdown(f"**Клеточные и матриксные процессы:**\n\n{ph.get('cellular_and_tissue_events')}")
                c_b.markdown(
                    f"**Клинический коррелят:**\n\n{ph.get('clinical_correlate')}\n\n"
                    f"🎯 **Терапевтическое окно:** {ph.get('therapeutic_window')}"
                )

    with sub3:
        nat = kb.get("natural_history_and_dynamics", {})
        defs = nat.get("definitions", {})
        st.markdown("#### 🧭 Стандартизованные определения исходов и динамики заболевания")
        st.info(f"**Естественное развитие без инвазивного лечения:** {nat.get('untreated_course_summary', '—')}")

        d1, d2 = st.columns(2)
        d1.success(f"✅ **Первичная эффективность и ремиссия:**\n\n{defs.get('primary_remission', '—')}")
        d2.warning(f"🔁 **Истинный рецидив (Relapse):**\n\n{defs.get('true_recurrence', '—')}")
        d3, d4 = st.columns(2)
        d3.error(f"📈 **Процедив (Прогрессирование / Распространение):**\n\n{defs.get('procediv_progression', '—')}")
        d4.info(f"⏳ **Естественное течение (Natural History):**\n\n{defs.get('natural_history', '—')}")

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
            fig_5y.add_trace(
                go.Bar(
                    name="Повторные вмешательства к 5 годам (%)",
                    x=df_filt["name"],
                    y=df_filt["reintervention_5y_num"],
                    text=df_filt["reintervention_5y"],
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
            st.plotly_chart(fig_5y, use_container_width=True)

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
                st.plotly_chart(fig_traj, use_container_width=True)

            disp_mod = df_filt[
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
            st.dataframe(disp_mod, use_container_width=True, hide_index=True)
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
                        st.success(f"➕ **Плюсы:** {mod['pros']}")
                        st.error(f"➖ **Минусы:** {mod['cons']}")

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
                use_container_width=True,
                hide_index=True,
            )


def render_tab_prisma_explorer(bundle: dict[str, Any]) -> None:
    """Tab 3: Literature & PRISMA SQLite Explorer across articles, clinical, mechanisms, and trials."""
    nos_id = bundle["nosology_id"]
    db_path_str = str(bundle["db_path"])
    df_art = cached_articles(db_path_str, included_only=True)
    df_clin = cached_clinical_evidence(db_path_str)
    df_mech = cached_mechanisms(db_path_str)
    df_trials = cached_trials(db_path_str)

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
            st.plotly_chart(fig_yr, use_container_width=True)
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
            st.plotly_chart(fig_tr, use_container_width=True)

    table_choice = st.radio(
        "Выберите таблицу базы данных SQLite для интерактивного поиска и выгрузки:",
        options=[
            f"1. Включённые статьи PRISMA ({len(df_art)})",
            f"2. Извлечённые клинические доказательства ({len(df_clin)})",
            f"3. Извлечённые этиопатогенетические механизмы ({len(df_mech)})",
            f"4. Реестр клинических исследований ClinicalTrials.gov ({len(df_trials)})",
        ],
        horizontal=True,
        key="tab3_table_choice",
    )

    if table_choice.startswith("1."):
        f1, f2, f3 = st.columns([1, 1, 2])
        with f1:
            tiers = sorted(df_art["evidence_tier"].dropna().unique().tolist()) if not df_art.empty else []
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
            use_container_width=True,
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
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.download_button(
            "📥 Скачать клинические доказательства (.csv)",
            data=dataframe_to_csv_bytes(view),
            file_name=f"{nos_id}_clinical_evidence.csv",
            mime="text/csv",
            key="dl_csv_clin",
        )

    elif table_choice.startswith("3."):
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
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.download_button(
            "📥 Скачать патогенетические механизмы (.csv)",
            data=dataframe_to_csv_bytes(view),
            file_name=f"{nos_id}_mechanisms.csv",
            mime="text/csv",
            key="dl_csv_mech",
        )

    else:
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
            use_container_width=True,
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


def render_tab_configurator_and_audit(bundle: dict[str, Any]) -> None:
    """Tab 4: Verification Audit Certificate & New Nosology YAML Configurator."""
    st.subheader("🛡️ Аудит верификации ссылок и Конфигуратор новых нозологий")
    col_audit, col_cfg = st.columns([1, 1])

    with col_audit:
        st.markdown("#### ✅ Сертификат верификации (`Zero-Tolerance Gate`)")
        if st.button("🔄 Запустить повторный аудит `verify_reports.py --verify`", key="btn_run_verify"):
            res = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "src" / "verify_reports.py"),
                    "--nosology",
                    bundle["nosology_id"],
                    "--verify",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if res.returncode == 0:
                st.success("Аудит успешно пройден: 0 галлюцинаций и 0 запрещённых ИИ-штампов.")
            else:
                st.error("Обнаружены замечания при проверке.")
            st.code(res.stdout + ("\n" + res.stderr if res.stderr else ""))

        if bundle["verification_audit_md"]:
            st.markdown(bundle["verification_audit_md"])
        else:
            st.info("Файл `verification_audit.md` отсутствует.")

    with col_cfg:
        st.markdown("#### ⚙️ Добавить новую нозологию (`configs/<id>.yaml`)")
        st.caption(
            "Платформа полностью универсальна: создайте YAML-профиль любой нозологии, чтобы запустить 4-фазный пайплайн сбора и синтеза."
        )
        with st.form("new_nosology_form"):
            new_id = st.text_input("ID нозологии (латиницей):", value="trigger_finger")
            new_ru = st.text_input("Название (RU):", value="Стенозирующий лигаментит (болезнь Нотта / щёлкающий палец)")
            new_en = st.text_input("Название (EN):", value="Trigger Finger (Stenosing Tenosynovitis)")
            c_icd10, c_icd11 = st.columns(2)
            icd10_val = c_icd10.text_input("Код МКБ-10:", value="M65.3")
            icd11_val = c_icd11.text_input("Код МКБ-11:", value="FB40.2")
            mesh_val = st.text_input("Термины MeSH (через запятую):", value="Trigger Finger Disorder, Tenosynovitis")
            pubmed_q = st.text_area(
                "Поисковый запрос PubMed / Europe PMC:",
                value='("Trigger Finger Disorder"[MeSH] OR "trigger finger"[tiab] OR "stenosing tenosynovitis"[tiab])',
            )
            ct_cond = st.text_input("Условие для ClinicalTrials.gov:", value="Trigger Finger")
            submitted = st.form_submit_button("💾 Сохранить конфигурацию в `configs/`")

        if submitted:
            payload = {
                "nosology": {
                    "id": new_id.strip().lower(),
                    "name_ru": new_ru.strip(),
                    "name_en": new_en.strip(),
                    "icd10": icd10_val.strip(),
                    "icd11": icd11_val.strip(),
                    "mesh_terms": [m.strip() for m in mesh_val.split(",") if m.strip()],
                },
                "date_range": {"start_year": 2016, "end_year": 2026},
                "queries": {
                    "pubmed": pubmed_q.strip(),
                    "europepmc": pubmed_q.strip(),
                    "openalex": new_en.strip(),
                    "clinicaltrials": ct_cond.strip(),
                },
            }
            try:
                saved_path = save_new_nosology_config(payload)
                st.success(f"Конфигурация сохранена: `{saved_path}`")
                st.code(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), language="yaml")
            except Exception as exc:
                st.error(f"Ошибка сохранения: {exc}")

        st.markdown("##### 🚀 Команды запуска пайплайна для новой нозологии")
        st.code(
            "# Фаза 1: Сбор PubMed / Europe PMC / OpenAlex / ClinicalTrials и PRISMA-триаж\n"
            "uv run src/harvester.py --config configs/<id>.yaml\n"
            "uv run src/triage.py --config configs/<id>.yaml\n\n"
            "# Фаза 3–4: Компиляция библиографии, аудит и запуск веб-интерфейса\n"
            "uv run src/verify_reports.py --compile-bibliography --verify\n"
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
    """Automated headless verification of schema, SQLite queries, exports, and Streamlit AppTest (`UI-01`)."""
    import os

    os.environ["INFO_SEARCHER_APPTEST_ACTIVE"] = "1"
    sys.argv = [arg for arg in sys.argv if arg != "--self-test"]

    print("[1/3] Running universal schema & export verification...")
    discovered = discover_nosologies()
    active_nos = discovered[0]["id"] if discovered else "prom"
    rc = verify_universal_schema(active_nos)
    if rc != 0:
        return rc

    print("[2/3] Running headless Streamlit AppTest on `app.py`...")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(Path(__file__).resolve()), default_timeout=60)
    at.run(timeout=60)
    if len(at.exception) > 0:
        print(f"[FAIL] Streamlit AppTest raised {len(at.exception)} exception(s):")
        for exc in at.exception:
            print(exc)
        return 1

    # Switch report modes in Tab 1 to ensure Mode B and Mode C also render cleanly
    at.radio(key="tab1_report_mode").set_value("Режим Б — Краткий клинический отчёт (Executive Summary)").run(timeout=60)
    if len(at.exception) > 0:
        print(f"[FAIL] Mode B raised exception: {at.exception[0]}")
        return 1

    at.radio(key="tab1_report_mode").set_value("Режим В — Модульная база знаний (5 тематических модулей)").run(timeout=60)
    if len(at.exception) > 0:
        print(f"[FAIL] Mode C raised exception: {at.exception[0]}")
        return 1

    print(
        f"[3/3] [PASS] Streamlit AppTest rendered all 4 tabs and all 3 report modes with 0 exceptions "
        f"(metrics={len(at.metric)}, dataframes={len(at.dataframe)}, tabs={len(at.tabs)})."
    )
    return 0


if __name__ == "__main__":
    import os

    if "--self-test" in sys.argv and os.environ.get("INFO_SEARCHER_APPTEST_ACTIVE") != "1":
        sys.exit(run_self_test())
    else:
        render_streamlit_app()
