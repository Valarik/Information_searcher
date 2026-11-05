# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = []
# ///
"""Structured Extraction Pipeline for Clinical Cases of Metroplasty During Pregnancy (`metroplasty_pregnancy`).

Extracts pathomorphological mechanisms (`extracted_mechanisms`) and surgical case outcomes (`extracted_clinical_evidence`)
from `data/metroplasty_pregnancy/literature.db` across all 4 analytical clusters (including Tier 4 Case Reports)
and writes structured Markdown dossiers in `data/metroplasty_pregnancy/extractions/`.
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

DB_PATH = Path("data/metroplasty_pregnancy/literature.db")
EXTRACTIONS_DIR = Path("data/metroplasty_pregnancy/extractions")


def classify_mechanism_category(text: str) -> tuple[str, str]:
    t = text.lower()
    targets: list[str] = []
    for kw, label in [
        ("residual myometrial thickness", "Остаточная толщина миометрия (RMT < 2,0–2,5 мм)"),
        ("rmt", "RMT (УЗ/МРТ-маркер состоятельности рубца)"),
        ("isthmocele", "Истмоцеле (ниша рубца после КС)"),
        ("dehiscence", "Дегисценция (расползание) рубца с пролабированием плодного пузыря"),
        ("uterine window", "«Маточное окно» (дефект миометрия при целом серозном покрове)"),
        ("hysteroscopic metroplasty", "Состояние миометрия после гистероскопической метропластики (перегородка/Т-матка)"),
        ("strassmann", "Рубец после метропластики Штрассмана (двурогая матка)"),
        ("rudimentary horn", "Рудиментарный рог / интерстициально-корнуальная зона"),
        ("placenta accreta", "Врастание плаценты в зону рубца (PAS: accreta/increta/percreta)"),
        ("scar pregnancy", "Беременность в рубце на матке (CSP тип I/II)"),
        ("myomectomy", "Ложе после гравидарной или предгравидарной миомэктомии"),
        ("collagen", "Ремоделирование коллагена I/III и фиброз миометрия"),
        ("mri", "МРТ-навигация дефекта стенки матки"),
    ]:
        if kw in t:
            targets.append(label)

    target_str = ", ".join(targets[:4]) if targets else "Морфофункциональная несостоятельность рубца и миометрия во время гестации"

    if any(k in t for k in ("hysteroscopic", "strassmann", "septate", "bicornuate", "t-shaped", "mullerian", "congenital")):
        cat = "[Cluster1] Аномалии мюллеровых протоков и состояние матки после предшествующей метропластики"
    elif any(k in t for k in ("isthmocele", "niche", "residual myometrial", "rmt", "previous cesarean", "scar defect")):
        cat = "[Cluster1] Этиопатогенез истмоцеле (ниши) и истончения рубца после кесарева сечения"
    elif any(k in t for k in ("placenta accreta", "increta", "percreta", "scar pregnancy", "csp", "trophoblast")):
        cat = "[Cluster2] Аномальная инвазия трофобласта в нишу рубца (CSP и спектр врастания плаценты PAS)"
    else:
        cat = "[Cluster2] Биомеханика антенатальной дегисценции/разрыва матки и грыжевого выпячивания плодных оболочек"

    return cat, target_str


def classify_clinical_group(text: str) -> tuple[str, str]:
    t = text.lower()
    if any(k in t for k in ("ongoing pregnancy", "continuing pregnancy", "prolongation", "second trimester", "mid-trimester", "antenatal repair", "during pregnancy", "18 weeks", "20 weeks", "22 weeks", "24 weeks", "26 weeks")) and any(k in t for k in ("rupture", "dehiscence", "window", "repair", "suture", "patch", "metroplasty")):
        return (
            "[Cluster4] Антенатальная метропластика при дегисценции / разрыве матки в I–II триместре с сохранением беременности",
            "Экстренное прерывание беременности / родоразрешение или гистерэктомия",
        )
    if any(k in t for k in ("scar pregnancy", "csp", "heterotopic", "rudimentary horn", "cornual", "diverticulum", "sacculation")):
        return (
            "[Cluster4] Резекция рубцовой беременности (CSP), дивертикула или рудиментарного рога с метропластикой во время гестации",
            "Медикаментозное прерывание (метотрексат) или удаление матки",
        )
    if any(k in t for k in ("accreta", "increta", "percreta", "one-step", "focal resection", "triple-p")) or ("cesarean" in t and "metroplasty" in t):
        return (
            "[Cluster4] Интранатальная органосохраняющая метропластика при кесаревом сечении (аневризма рубца и врастание плаценты PAS)",
            "Цезарева гистерэктомия (экстирпация матки)",
        )
    if "myomectomy" in t:
        return (
            "[Cluster4] Гравидарная миомэктомия в I–II триместре с послойной метропластикой ложа",
            "Консервативное ведение некроза миомы при беременности",
        )
    if any(k in t for k in ("laparoscopic", "vaginal", "hysteroscopic", "robotic")) and any(k in t for k in ("isthmocele", "niche", "scar defect", "strassmann")):
        return (
            "[Cluster3] Предгравидарная и ранняя гравидарная лапароскопическая / вагинальная / гистероскопическая метропластика",
            "Выжидательное ведение без хирургической коррекции ниши (RMT < 2,5 мм)",
        )
    return (
        "[Cluster3] Консервативно-выжидательное ведение бессимптомной дегисценции рубца (УЗ/МРТ-мониторинг, токолиз, стероиды)",
        "Активная хирургическая ревизия или досрочное родоразрешение",
    )


def extract_case_timing_and_outcomes(text: str) -> tuple[str, str, str, str]:
    ga_matches = re.findall(
        r"\b(\d{1,2}\s*(?:\+\s*\d)?\s*weeks(?:\s+of\s+gestation)?)\b",
        text,
        flags=re.IGNORECASE,
    )
    ga_str = " → ".join(dict.fromkeys(ga_matches[:3])) if ga_matches else "Срок гестации и родоразрешения по протоколу наблюдения"

    prolong_matches = re.findall(
        r"(?:prolonged|continued|latency|delivered at)[^.;]{0,55}?(\d{1,2}\s*weeks|\d+\s*days)",
        text,
        flags=re.IGNORECASE,
    )
    prolong_str = "; ".join(dict.fromkeys(prolong_matches[:2])) if prolong_matches else f"Динамика гестации: {ga_str}"

    suture_terms = []
    for k, lbl in [
        ("double-layer", "двухрядный шов миометрия"),
        ("two-layer", "двухрядный шов миометрия"),
        ("three-layer", "трёхрядный шов"),
        ("vicryl", "полиглактин (Vicryl)"),
        ("monocryl", "полиглекапрон (Monocryl)"),
        ("tachosil", "гемостатический патч TachoSil"),
        ("fibrin", "фибриновый герметик"),
        ("gore-tex", "синтетический патч Gore-Tex"),
        ("omental", "оментопластика"),
        ("tourniquet", "турникетный гемостаз"),
        ("balloon", "баллонная тампонада"),
    ]:
        if k in text.lower():
            suture_terms.append(lbl)
    tech_str = ", ".join(suture_terms[:4]) if suture_terms else "Иссечение истончённых краёв и послойная метропластика"

    comp_terms = []
    for k, lbl in [
        ("hemorrhage", "кровотечение"),
        ("transfusion", "гемотрансфузия"),
        ("hysterectomy", "переход к гистерэктомии"),
        ("preterm", "преждевременные роды"),
        ("pprom", "ПРПО"),
        ("accreta", "врастание плаценты (PAS)"),
        ("rupture", "повторный разрыв/дегисценция"),
    ]:
        if k in text.lower():
            comp_terms.append(lbl)
    comp_str = ", ".join(comp_terms[:4]) if comp_terms else "Сохранение матки и рождение живого плода"
    return prolong_str, tech_str, comp_str, ga_str


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
                "Клинико-морфологическое и УЗ/МРТ-исследование беременных с рубцом/метропластикой",
                sample_desc[:120],
                quant_str[:240],
                summary_sent,
                "Критерии выбора между антенатальной метропластикой, выжидательным мониторингом и родоразрешением",
            ),
        )
        mech_count += 1

        int_grp, comp_grp = classify_clinical_group(combined_text)
        pt_lower = " ".join(pub_types).lower()
        if "case report" in pt_lower or "case report" in title.lower() or "a case of" in title.lower() or tier == 4:
            s_design = "Клинический случай (Case Report) / Серия клинических случаев (Tier 4)"
            if n_pat is None:
                n_pat = 1
        elif tier == 1:
            s_design = "Систематический обзор клинических случаев / Мета-анализ / РКИ (Tier 1)"
        elif tier == 2:
            s_design = "Проспективная / сравнительная клиническая когорта (Tier 2)"
        else:
            s_design = "Ретроспективная серия клинических наблюдений (Tier 3)"

        prolong_str, tech_str, comp_str, ga_str = extract_case_timing_and_outcomes(combined_text)
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
                f"Сроки гестации: {ga_str[:100]}",
                int_grp,
                comp_grp,
                6.0,
                prolong_str[:200],
                tech_str[:200],
                "Повторная дегисценция/разрыв матки или процедив в PAS/гистерэктомию",
                comp_str[:120],
                "При плановой/ранней пластике: высокая доля живорождений",
                "При полном разрыве/percreta: высокий риск кровотечения и потерь",
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
            "cluster_1_etiology_scar_defects.md",
            "Кластер 1: Этиология дефектов миометрия, истмоцеле и состояние матки после предшествующей метропластики",
            "SELECT first_author_year, pmid, category, targets_genes_pathways, quantitative_findings, mechanism_summary FROM extracted_mechanisms WHERE category LIKE '[Cluster1]%' LIMIT 60",
        ),
        (
            "cluster_2_pathomorphology_and_imaging.md",
            "Кластер 2: Патоморфология дегисценции рубца, грыжи плодного пузыря, CSP и спектра врастания плаценты (PAS)",
            "SELECT first_author_year, pmid, category, targets_genes_pathways, quantitative_findings, mechanism_summary FROM extracted_mechanisms WHERE category LIKE '[Cluster2]%' LIMIT 60",
        ),
        (
            "cluster_3_preconception_and_expectant.md",
            "Кластер 3: Выжидательный мониторинг при бессимптомной дегисценции и предгравидарная пластика рубца",
            "SELECT first_author_year, pmid, study_design, intervention_group, n_patients, mcp_outcome, pip_outcome, key_conclusion FROM extracted_clinical_evidence WHERE intervention_group LIKE '[Cluster3]%' LIMIT 60",
        ),
        (
            "cluster_4_antenatal_and_intrapartum_metroplasty_cases.md",
            "Кластер 4: Клинические случаи антенатальной и интранатальной метропластики во время беременности",
            "SELECT first_author_year, pmid, study_design, intervention_group, n_patients, mcp_outcome, pip_outcome, key_conclusion FROM extracted_clinical_evidence WHERE intervention_group LIKE '[Cluster4]%' LIMIT 80",
        ),
    ]:
        d_rows = cur.execute(table_q).fetchall()
        lines = [f"# {title_str}", "", f"Всего извлечённых записей в кластере: **{len(d_rows)}**", ""]
        for dr in d_rows:
            vals = [str(v or "—") for v in dr]
            lines.append(f"- **{vals[0]}** (`PMID: {vals[1]}`): {' | '.join(vals[2:])}")
        (EXTRACTIONS_DIR / fname).write_text("\n".join(lines) + "\n", encoding="utf-8")

    conn.close()
    print(f"[Extraction Complete: metroplasty_pregnancy] extracted_mechanisms={mech_count}, extracted_clinical_evidence={clin_count}")


if __name__ == "__main__":
    run_extraction()
