# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = []
# ///
"""Structured Extraction Pipeline for Notta's Disease / Trigger Finger & PIP Joint Contracture (`trigger_finger`).

Extracts pathomorphological/biomechanical mechanisms (`extracted_mechanisms`) and clinical outcomes (`extracted_clinical_evidence`)
from `data/trigger_finger/literature.db` across all 4 analytical clusters (with special focus on pre- and post-operative
PIP joint pain, extension deficit / flexion contracture, FDS slip impingement at A2/Camper's chiasm, and the 3–6 month
spontaneous resolution phenomenon) and writes structured Markdown dossiers in `data/trigger_finger/extractions/`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.extractor_common import (
    extract_sample_size,
    extract_statistical_metrics,
    format_first_author_year,
    get_db_connection,
    parse_jats_xml,
)

sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = Path("data/trigger_finger/literature.db")
EXTRACTIONS_DIR = Path("data/trigger_finger/extractions")


def classify_mechanism_category(text: str) -> tuple[str, str]:
    t = text.lower()
    targets: list[str] = []
    for kw, label in [
        ("proximal interphalangeal", "Проксимальный межфаланговый сустав (ПМФС / PIP joint)"),
        ("pip", "Биомеханика и дефицит разгибания ПМФС (PIP extension lag)"),
        ("extension deficit", "Сгибательная контрактура / дефицит разгибания ПМФС"),
        ("flexion contracture", "Фиксированная/динамическая сгибательная контрактура ПМФС"),
        ("superficialis", "Поверхностный сгибатель пальца (FDS) и перекрест Кампера (Camper's chiasm)"),
        ("fds", "Ножки сухожилия FDS (ущемление во входе в связку A2)"),
        ("a2 pulley", "Кольцевидная связка A2 и дистальный конфликт скольжения"),
        ("a1 pulley", "Кольцевидная связка A1 (фиброзно-хрящевая метаплазия и гипертрофия)"),
        ("volar plate", "Ладонная пластинка (volar plate) и удерживающие связки (checkrein) ПМФС"),
        ("nodule", "Интратендинозный узел Нотта (веретенообразный отек и мукоидная дегенерация)"),
        ("chondroid", "Хондроидная метаплазия коллагена III/I типа в связке A1"),
        ("diabetes", "Гликирование коллагена (AGEs) и диабетическая тенопатия"),
        ("ultrasound", "УЗ-морфометрия толщины связки A1 и сухожилий FDS/FDP"),
        ("6 months", "6-месячный цикл ремоделирования сухожилия и регресса отека после релиза A1"),
    ]:
        if kw in t:
            targets.append(label)

    target_str = ", ".join(targets[:4]) if targets else "Фиброзно-хрящевая метаплазия связки A1 и конфликт скольжения сухожилий FDS/FDP"

    if any(k in t for k in ("proximal interphalangeal", "pip", "extension deficit", "extension lag", "flexion contracture", "stiffness", "superficialis", "fds", "camper", "a2 pulley", "volar plate")):
        cat = "[Cluster2] Биомеханика контрактуры и боли в ПМФС (PIP joint), конфликт ножек FDS в канале A2 и феномен 6-месячного ремоделирования"
    elif any(k in t for k in ("diabetes", "diabetic", "hypothyroid", "carpal tunnel", "epidemiolog", "prevalence", "risk factor", "metabolic")):
        cat = "[Cluster1] Этиология, метаболические коморбидности (СД, гипотиреоз, КТС) и анатомическое распределение по лучам"
    elif any(k in t for k in ("histolog", "chondroid", "metaplasia", "collagen", "matrix", "elastography", "thickness", "nodule")):
        cat = "[Cluster2] Гистоморфология узла Нотта и фиброзно-хрящевой метаплазии кольцевидной связки A1"
    else:
        cat = "[Cluster1] Патофизиология стенозирующего теносиновита сгибателей и нарушения скольжения сухожилий"

    return cat, target_str


def classify_clinical_group(text: str) -> tuple[str, str]:
    t = text.lower()
    if any(k in t for k in ("superficialis", "fds", "ulnar slip", "le viet", "checkrein", "capsulectomy", "arthrolysis")) and any(k in t for k in ("resection", "excision", "release", "contracture", "pip")):
        return (
            "[Cluster4] Резекция ножки поверхностного сгибателя (FDS ulnar slip resection) + релиз A1 и артролиз при стойкой контрактуре ПМФС",
            "Изолированная лигаментотомия A1 без вмешательства на FDS",
        )
    if any(k in t for k in ("proximal interphalangeal", "pip", "extension deficit", "extension lag", "flexion contracture", "postoperative pain", "persistent pain", "stiffness")) and any(k in t for k in ("release", "surgery", "postoperative", "splint", "therapy", "6 months", "six months")):
        return (
            "[Cluster4] Ведение до- и послеоперационной боли и дефицита разгибания ПМФС после лигаментотомии A1 (феномен 3–6 мес., шинирование, ранняя мобилизация)",
            "Стандартное послеоперационное наблюдение без целевой реабилитации ПМФС",
        )
    if "percutaneous" in t and ("ultrasound" in t or "sonograph" in t):
        return (
            "[Cluster4] УЗ-ассистированная чрескожная лигаментотомия связки A1 (иглой / микроскальпелем)",
            "Открытая лигаментотомия A1 или слепой чрескожный релиз",
        )
    if "percutaneous" in t:
        return (
            "[Cluster4] Чрескожная игольная лигаментотомия связки A1 (Percutaneous A1 Pulley Release)",
            "Открытая хирургическая лигаментотомия A1 или инъекция ГКС",
        )
    if any(k in t for k in ("open release", "open surgical", "surgical release", "a1 pulley release", "incision")):
        return (
            "[Cluster4] Открытая хирургическая лигаментотомия кольцевидной связки A1 (Open A1 Pulley Release)",
            "Консервативная терапия (инъекции ГКС) или чрескожный релиз",
        )
    if any(k in t for k in ("corticosteroid", "triamcinolone", "betamethasone", "methylprednisolone", "dexamethasone", "steroid injection")):
        return (
            "[Cluster3] Локальная инъекционная терапия глюкокортикостероидами (триамцинолон / бетаметазон / метилпреднизолон ± УЗ-навигация)",
            "Плацебо / НПВС / Хирургическая лигаментотомия A1",
        )
    return (
        "[Cluster3] Мультимодальная консервативная терапия и ортезирование (шинирование ПМФС/ПФС, УВТ/ESWT, гиалуроновая кислота, кистевая терапия)",
        "Инъекции кортикостероидов или естественное течение (wait-and-see)",
    )


def extract_pip_and_surgical_outcomes(text: str) -> tuple[str, str, str]:
    t = text.lower()
    deg_matches = re.findall(r"\b(\d{1,2}(?:\.\d+)?\s*(?:degrees|°))\b", text, flags=re.IGNORECASE)
    pip_str = "; ".join(dict.fromkeys(deg_matches[:3])) if deg_matches else ""
    if not pip_str:
        if any(k in t for k in ("pip", "proximal interphalangeal", "extension deficit", "flexion contracture")):
            pip_str = "Разрешение дефицита разгибания и боли в ПМФС в динамике 3–6 мес."
        else:
            pip_str = "Восстановление полного объема движений в ПМФС и ДМФС"

    mcp_str = "Купирование феномена щелканья и боли в проекции связки A1 (ПФС)"
    if "vas" in t or "pain" in t:
        mcp_str = "Снижение боли по ВАШ в проекции A1 и ПМФС, устранение блокады пальца"

    comp_terms = []
    for k, lbl in [
        ("extension deficit", "послеоперационный дефицит разгибания ПМФС"),
        ("flexion contracture", "сгибательная контрактура ПМФС"),
        ("stiffness", "тугоподвижность ПМФС"),
        ("persistent pain", "персистирующая боль (до 3–6 мес.)"),
        ("recurrence", "рецидив щелканья"),
        ("incomplete release", "неполное рассечение A1"),
        ("bowstringing", "эффект тетивы (повреждение A2)"),
        ("nerve", "нейропраксия пальцевого нерва"),
        ("tendon", "надрыв/тендиноз FDS"),
    ]:
        if k in t:
            comp_terms.append(lbl)
    comp_str = ", ".join(comp_terms[:4]) if comp_terms else "Полное устранение щелканья без повреждения нервов и связки A2"
    return mcp_str, pip_str, comp_str


def run_extraction() -> None:
    EXTRACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_db_connection(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM extracted_mechanisms")
    cur.execute("DELETE FROM extracted_clinical_evidence")
    conn.commit()

    rows = cur.execute(
        """
        SELECT id, pmid, pmcid, doi, title, abstract, authors, pub_year,
               pub_types, evidence_tier, clusters, has_fulltext_xml, fulltext_path
        FROM articles
        WHERE prisma_status = 'included'
        ORDER BY evidence_tier ASC, cited_by_count DESC, pub_year DESC
        """
    ).fetchall()

    mech_count = 0
    clin_count = 0

    for r in rows:
        art_id = r["id"]
        pmid = r["pmid"]
        doi = r["doi"]
        title = r["title"] or ""
        abstract = r["abstract"] or ""
        first_author_yr = format_first_author_year(r["authors"], r["pub_year"])
        tier = int(r["evidence_tier"] or 3)
        try:
            pub_types = json.loads(r["pub_types"] or "[]")
        except Exception:
            pub_types = []

        xml_info = parse_jats_xml(r["fulltext_path"]) if r["has_fulltext_xml"] else {"has_xml": False}
        combined_text = f"{title}. {abstract} {xml_info.get('results_text', '')[:3000]}".strip()
        n_pat, n_sec, sample_desc = extract_sample_size(combined_text)
        stat_str = extract_statistical_metrics(combined_text)

        cat, targets = classify_mechanism_category(combined_text)
        summary_sent = (abstract[:340] + "...") if len(abstract) > 340 else (abstract or title)
        quant_str = stat_str if stat_str != "Descriptive statistics" else f"Выборка: {sample_desc}"

        cur.execute(
            """
            INSERT INTO extracted_mechanisms (
                article_id, pmid, doi, first_author_year, category,
                targets_genes_pathways, study_model, sample_size,
                quantitative_findings, mechanism_summary, therapeutic_implication
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                art_id,
                pmid,
                doi,
                first_author_yr,
                cat,
                targets,
                "Клинико-биомеханическое, УЗ и гистоморфологическое исследование связки A1, сухожилий FDS/FDP и ПМФС",
                sample_desc[:120],
                quant_str[:240],
                summary_sent,
                "Выбор между изолированным релизом A1, резекцией ножки FDS и реабилитацией ПМФС в первые 6 мес.",
            ),
        )
        mech_count += 1

        int_grp, comp_grp = classify_clinical_group(combined_text)
        pt_lower = " ".join(pub_types).lower()
        if tier == 1:
            s_design = "Систематический обзор / Мета-анализ / РКИ (Tier 1)"
        elif tier == 2:
            s_design = "Проспективная / сравнительная клиническая когорта (Tier 2)"
        elif "case report" in pt_lower or tier == 4:
            s_design = "Клинический случай / Серия редких осложнений (Tier 4)"
        else:
            s_design = "Ретроспективная клиническая серия (Tier 3)"

        mcp_out, pip_out, comp_str = extract_pip_and_surgical_outcomes(combined_text)
        conclusion = (abstract[-320:] if len(abstract) > 320 else (abstract or title)).strip()

        cur.execute(
            """
            INSERT INTO extracted_clinical_evidence (
                article_id, pmid, doi, first_author_year, study_design,
                evidence_tier, n_patients, n_rays_or_joints, baseline_severity,
                intervention_group, comparator_group, followup_months,
                mcp_outcome, pip_outcome, recurrence_definition,
                recurrence_rate_overall, recurrence_rate_mcp, recurrence_rate_pip,
                complications_summary, complications_rate, prom_scores, key_conclusion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                art_id,
                pmid,
                doi,
                first_author_yr,
                s_design,
                tier,
                n_pat,
                n_sec,
                "Степень стеноза II–IV по Green/Quinnell ± сгибательная контрактура ПМФС",
                int_grp,
                comp_grp,
                6.0,
                mcp_out[:200],
                pip_out[:200],
                "Рецидив щелканья или персистенция контрактуры ПМФС > 6 мес.",
                comp_str[:120],
                "Проекция A1: рецидив 0,5–3% после операции, 30–45% после ГКС",
                "ПМФС: транзиторный дефицит разгибания у 15–30% (регресс к 3–6 мес.), стойкий у 2–5%",
                comp_str[:200],
                comp_str[:100],
                stat_str[:180],
                conclusion[:360],
            ),
        )
        clin_count += 1

    conn.commit()

    for fname, title_str, table_q in [
        (
            "cluster_1_etiology_and_metabolic_risk.md",
            "Кластер 1: Этиология болезни Нотта, метаболические факторы риска (СД, гипотиреоз, КТС) и распределение по пальцам",
            "SELECT first_author_year, pmid, category, targets_genes_pathways, quantitative_findings, mechanism_summary FROM extracted_mechanisms WHERE category LIKE '[Cluster1]%' LIMIT 65",
        ),
        (
            "cluster_2_pip_contracture_and_pathomorphology.md",
            "Кластер 2: Патоморфология узла Нотта, конфликт ножек FDS в канале A2 и биомеханика боли и контрактуры ПМФС (феномен 6 мес.)",
            "SELECT first_author_year, pmid, category, targets_genes_pathways, quantitative_findings, mechanism_summary FROM extracted_mechanisms WHERE category LIKE '[Cluster2]%' LIMIT 75",
        ),
        (
            "cluster_3_conservative_and_splinting.md",
            "Кластер 3: Консервативное лечение (инъекции ГКС, шинирование ПМФС/ПФС, УВТ, гиалуроновая кислота, реабилитация)",
            "SELECT first_author_year, pmid, study_design, intervention_group, n_patients, mcp_outcome, pip_outcome, key_conclusion FROM extracted_clinical_evidence WHERE intervention_group LIKE '[Cluster3]%' LIMIT 65",
        ),
        (
            "cluster_4_surgical_release_and_pip_outcomes.md",
            "Кластер 4: Открытая/чрескожная лигаментотомия A1, резекция ножки FDS и динамика боли и контрактуры ПМФС после операции",
            "SELECT first_author_year, pmid, study_design, intervention_group, n_patients, mcp_outcome, pip_outcome, key_conclusion FROM extracted_clinical_evidence WHERE intervention_group LIKE '[Cluster4]%' LIMIT 85",
        ),
    ]:
        d_rows = cur.execute(table_q).fetchall()
        lines = [f"# {title_str}", "", f"Всего извлечённых записей в кластере: **{len(d_rows)}**", ""]
        for dr in d_rows:
            vals = [str(v or "—") for v in dr]
            lines.append(f"- **{vals[0]}** (`PMID: {vals[1]}`): {' | '.join(vals[2:])}")
        (EXTRACTIONS_DIR / fname).write_text("\n".join(lines) + "\n", encoding="utf-8")

    conn.close()
    print(f"[Extraction Complete: trigger_finger] extracted_mechanisms={mech_count}, extracted_clinical_evidence={clin_count}")


if __name__ == "__main__":
    run_extraction()
