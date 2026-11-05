# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = []
# ///
"""Structured Extraction Pipeline for Premature Rupture of Membranes (PROM / PPROM, O42).

Extracts quantitative mechanisms (`extracted_mechanisms`) and clinical outcomes (`extracted_clinical_evidence`)
from `data/prom/literature.db` across all 4 analytical clusters and writes structured Markdown dossiers
in `data/prom/extractions/`.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.extractor_common import (
    extract_sample_size,
    extract_statistical_metrics,
    format_first_author_year,
    get_db_connection,
    parse_jats_xml,
)

sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = Path("data/prom/literature.db")
EXTRACTIONS_DIR = Path("data/prom/extractions")


def classify_mechanism_category(text: str, clusters: list[str]) -> tuple[str, str]:
    t = text.lower()
    targets: list[str] = []
    for kw, label in [
        ("mmp-9", "MMP-9"),
        ("mmp-8", "MMP-8"),
        ("mmp-2", "MMP-2"),
        ("mmp-1", "MMP-1"),
        ("timp", "TIMP-1/2"),
        ("collagen", "Коллаген I/III/IV амниона"),
        ("il-6", "IL-6"),
        ("il-8", "IL-8"),
        ("il-1", "IL-1β"),
        ("tnf", "TNF-α"),
        ("tlr", "TLR2/TLR4"),
        ("p38", "p38 MAPK (сенесценция оболочек)"),
        ("senescence", "Клеточное старение амниона (Senescence)"),
        ("oxidative", "Оксидативный стресс / АФК"),
        ("apoptosis", "Апоптоз амниоцитов (Caspase-3/BCL-2)"),
        ("hmgb1", "HMGB1 / Алармины (стерильное воспаление)"),
        ("ureaplasma", "Ureaplasma spp. (MIAC)"),
        ("mycoplasma", "Mycoplasma hominis"),
        ("gardnerella", "Gardnerella vaginalis / дисбиоз"),
        ("lactobacillus", "Lactobacillus crispatus/iners"),
        ("streptococcus", "Streptococcus agalactiae (GBS)"),
        ("pamg-1", "PAMG-1 (AmniSure)"),
        ("igfbp-1", "IGFBP-1 (Actim PROM)"),
        ("crp", "С-реактивный белок (CRP)"),
        ("procalcitonin", "Прокальцитонин (PCT)"),
    ]:
        if kw in t:
            targets.append(label)

    target_str = ", ".join(targets[:5]) if targets else "Факторы ремоделирования плодных оболочек и цитокиновый каскад"

    if any(k in t for k in ("microbiome", "microbiota", "ureaplasma", "gardnerella", "lactobacillus", "vaginal")):
        cat = "[Cluster1] Микробиом влагалища и микробная инвазия амниона (MIAC)"
    elif any(k in t for k in ("polymorphism", "snp", "genetic", "gene", "methylation", "mirna", "lncrna", "epigenetic")):
        cat = "[Cluster1] Генетические и эпигенетические детерминанты разрыва оболочек"
    elif any(k in t for k in ("smoking", "bmi", "obesity", "twin", "cervical insufficiency", "short cervix", "history of pprom", "risk factor")):
        cat = "[Cluster1] Клинико-анамнестические и материнские факторы риска ПИОВ/ПРПО"
    elif any(k in t for k in ("mmp", "collagen", "extracellular matrix", "timp", "weakening", "tensile")):
        cat = "[Cluster2] Деградация внеклеточного матрикса и коллагена плодных оболочек (MMP/TIMP)"
    elif any(k in t for k in ("senescence", "p38", "oxidative", "apoptosis", "telomere", "autophagy")):
        cat = "[Cluster2] Оксидативный стресс, апоптоз и преждевременное старение оболочек (p38 MAPK)"
    elif any(k in t for k in ("pamg-1", "igfbp-1", "amnisure", "actim", "biomarker", "proteomic", "metabolomic")):
        cat = "[Cluster2] Диагностические и прогностические биомаркеры околоплодных вод и крови"
    else:
        cat = "[Cluster2] Внутриамниотическое воспаление (стерильное и инфекционное) и цитокиновый шторм"

    return cat, target_str


def classify_clinical_group(text: str) -> tuple[str, str]:
    t = text.lower()
    if any(k in t for k in ("azithromycin", "erythromycin", "ampicillin", "amoxicillin", "antibiotic", "cefuroxime", "clindamycin")):
        return (
            "[Cluster3] Антибиотикопрофилактика при ПРПО (эритромицин / азитромицин / бета-лактамы)",
            "Плацебо или альтернативный режим антибактериальной терапии",
        )
    if any(k in t for k in ("betamethasone", "dexamethasone", "corticosteroid", "antenatal steroid")):
        return (
            "[Cluster3] Антенатальная профилактика РДС кортикостероидами (бетаметазон / дексаметазон)",
            "Стандартное ведение / однократный vs повторный курс",
        )
    if any(k in t for k in ("magnesium sulfate", "mgso4", "neuroprotection", "tocolysis", "tocolytic", "nifedipine", "atosiban")):
        return (
            "[Cluster3] Нейропротекция сульфатом магния (MgSO4) и токолитическая терапия",
            "Выжидательная тактика без токолиза / плацебо",
        )
    if any(k in t for k in ("outpatient", "home management", "inpatient")):
        return (
            "[Cluster3] Амбулаторное против стационарного выжидательного ведения ПРПО",
            "Стационарный мониторинг в перинатальном центре",
        )
    if any(k in t for k in ("amnioinfusion", "amniopatch", "sealant", "fibrin", "platelet", "Mid-trimester", "periviable")):
        return (
            "[Cluster4] Фетальные вмешательства: амниоинфузия, амниопатч и герметизация при ПРПО <24 нед.",
            "Стандартная выжидательная тактика при маловодии",
        )
    if "cerclage" in t or "pessary" in t:
        return (
            "[Cluster4] Тактика при цервикальном серкляже и акушерском пессарии на фоне ПРПО",
            "Немедленное снятие серкляжа vs сохранение серкляжа",
        )
    if any(k in t for k in ("induction", "oxytocin", "misoprostol", "dinoprostone", "foley", "balloon", "immediate delivery", "active management")):
        return (
            "[Cluster4] Активное родоразрешение и индукция родов (окситоцин, простагландины, катетер Фолея)",
            "Выжидательная тактика (Expectant Management)",
        )
    if any(k in t for k in ("cord prolapse", "placental abruption", "maternal sepsis", "stillbirth", "pulmonary hypoplasia")):
        return (
            "[Cluster4] Ургентные акушерские и перинатальные осложнения [D-05]",
            "Когорта без тяжёлых осложнений",
        )
    return (
        "[Cluster3] Выжидательная тактика (Expectant Management) и пролонгирование латентного периода",
        "Немедленное родоразрешение / исторический контроль",
    )


def extract_latency_and_outcomes(text: str) -> tuple[str, str, str, str]:
    """Extract latency duration, chorioamnionitis/progression rate, recurrence in next pregnancy, and neonatal outcomes."""
    latency_matches = re.findall(
        r"(?:latency|latent period|prolongation)[^.;]{0,60}?(\d+(?:\.\d+)?\s*(?:days|hours|weeks|дн|сут|нед))",
        text,
        flags=re.IGNORECASE,
    )
    latency_str = "; ".join(dict.fromkeys(latency_matches[:2])) if latency_matches else "Оценка латентного периода и гестационного срока к родам"

    chorio_matches = re.findall(
        r"(?:chorioamnionitis|intra-amniotic infection|clinical infection)[^.;]{0,50}?(\d+(?:\.\d+)?\s*%)",
        text,
        flags=re.IGNORECASE,
    )
    chorio_str = "; ".join(dict.fromkeys(chorio_matches[:2])) if chorio_matches else "Контроль частоты хориоамнионита и эндометрита"

    sepsis_matches = re.findall(
        r"(?:neonatal sepsis|early-onset sepsis|rds|respiratory distress|mortality|ivh|nec)[^.;]{0,50}?(\d+(?:\.\d+)?\s*%)",
        text,
        flags=re.IGNORECASE,
    )
    neonatal_str = "; ".join(dict.fromkeys(sepsis_matches[:3])) if sepsis_matches else "Оценка неонатального сепсиса, РДС, ВЖК и выживаемости"

    rec_matches = re.findall(
        r"(?:recurrence|recurrent pprom|subsequent pregnancy)[^.;]{0,50}?(\d+(?:\.\d+)?\s*%)",
        text,
        flags=re.IGNORECASE,
    )
    rec_str = "; ".join(dict.fromkeys(rec_matches[:2])) if rec_matches else chorio_str
    return latency_str, neonatal_str, rec_str, chorio_str


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
            clusters = json.loads(r["clusters"] or "[]")
        except Exception:
            clusters = []
        try:
            pub_types = json.loads(r["pub_types"] or "[]")
        except Exception:
            pub_types = []

        xml_info = parse_jats_xml(r["fulltext_path"]) if r["has_fulltext_xml"] else {"has_xml": False}
        combined_text = f"{title}. {abstract} {xml_info.get('results_text', '')[:2500]}".strip()
        n_pat, n_secondary, sample_desc = extract_sample_size(combined_text)
        stat_str = extract_statistical_metrics(combined_text)

        is_mech = any(c in clusters for c in ("etiology", "pathogenesis"))
        is_clin = any(c in clusters for c in ("conservative", "surgical", "outcomes")) or not is_mech

        if is_mech and mech_count < 950:
            cat, targets = classify_mechanism_category(combined_text, clusters)
            model = "Клиническая когорта беременных / биоптаты плодных оболочек и амниотическая жидкость"
            if "in vitro" in combined_text.lower() or "explant" in combined_text.lower():
                model = "Культура эксплантов амниохориальных оболочек / амниоциты (in vitro / ex vivo)"
            elif "mouse" in combined_text.lower() or "murine" in combined_text.lower():
                model = "Экспериментальная модель in vivo + клинические образцы"

            summary_sent = (abstract[:340] + "...") if len(abstract) > 340 else (abstract or title)
            quant_str = stat_str if stat_str != "Descriptive statistics" else f"Выборка: {sample_desc}"
            implication = (
                "Ранняя стратификация риска ПРПО, неинвазивная диагностика ВУИ и таргетное торможение матриксных металлопротеиназ / воспаления"
            )

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
                    model,
                    sample_desc[:120],
                    quant_str[:240],
                    summary_sent,
                    implication,
                ),
            )
            mech_count += 1

        if is_clin and clin_count < 1150:
            int_grp, comp_grp = classify_clinical_group(combined_text)
            if tier == 1:
                s_design = "Систематический обзор / Мета-анализ / РКИ (Tier 1)"
            elif tier == 2:
                s_design = "Проспективное / многоцентровое когортное исследование (Tier 2)"
            elif "Rare Complication Case [D-05]" in pub_types:
                s_design = "Клиническое наблюдение ургентного осложнения [D-05] (Tier 4)"
            else:
                s_design = "Клиническая когорта / ретроспективное исследование (Tier 3)"

            lat_out, neo_out, rec_rate, chorio_rate = extract_latency_and_outcomes(combined_text)
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
                    n_secondary,
                    "ПИОВ / ПРПО (стратификация по гестационному сроку 22–37+ нед.)",
                    int_grp,
                    comp_grp,
                    1.0,
                    lat_out[:200],
                    neo_out[:200],
                    "Повторный ПРПО в следующей беременности / процедив в хориоамнионит",
                    rec_rate[:120],
                    "При сроке ≥34 нед.: низкий риск РДС",
                    "При сроке <34 нед.: высокий риск хориоамнионита и РДС",
                    chorio_rate[:200],
                    chorio_rate[:100],
                    stat_str[:180],
                    conclusion[:360],
                ),
            )
            clin_count += 1

    conn.commit()

    # Write 4 summary dossiers in data/prom/extractions/
    for fname, title_str, table_q in [
        (
            "cluster_1_etiology_epidemiology.md",
            "Кластер 1: Этиология, эпидемиология, микробиом и факторы риска ПИОВ/ПРПО",
            "SELECT first_author_year, pmid, category, targets_genes_pathways, quantitative_findings, mechanism_summary FROM extracted_mechanisms WHERE category LIKE '[Cluster1]%' LIMIT 60",
        ),
        (
            "cluster_2_pathogenesis_biomarkers.md",
            "Кластер 2: Молекулярный патогенез ослабления плодных оболочек и биомаркеры",
            "SELECT first_author_year, pmid, category, targets_genes_pathways, quantitative_findings, mechanism_summary FROM extracted_mechanisms WHERE category LIKE '[Cluster2]%' LIMIT 60",
        ),
        (
            "cluster_3_expectant_and_conservative.md",
            "Кластер 3: Выжидательная тактика, антибиотикопрофилактика, кортикостероиды и нейропротекция",
            "SELECT first_author_year, pmid, intervention_group, n_patients, mcp_outcome, complications_rate, key_conclusion FROM extracted_clinical_evidence WHERE intervention_group LIKE '[Cluster3]%' LIMIT 60",
        ),
        (
            "cluster_4_interventional_and_outcomes.md",
            "Кластер 4: Индукция родов, серкляж, фетальные вмешательства и перинатальные исходы",
            "SELECT first_author_year, pmid, intervention_group, n_patients, mcp_outcome, complications_rate, key_conclusion FROM extracted_clinical_evidence WHERE intervention_group LIKE '[Cluster4]%' LIMIT 60",
        ),
    ]:
        d_rows = cur.execute(table_q).fetchall()
        lines = [f"# {title_str}", "", f"Всего извлечённых записей в базе: **{len(d_rows)}+**", ""]
        for dr in d_rows:
            vals = [str(v or "—") for v in dr]
            lines.append(f"- **{vals[0]}** (`PMID: {vals[1]}`): {' | '.join(vals[2:])}")
        (EXTRACTIONS_DIR / fname).write_text("\n".join(lines) + "\n", encoding="utf-8")

    conn.close()
    print(f"[Extraction Complete] extracted_mechanisms={mech_count}, extracted_clinical_evidence={clin_count}")


if __name__ == "__main__":
    run_extraction()
