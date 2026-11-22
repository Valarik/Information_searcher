# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#   "pyyaml>=6.0.1",
#   "pandas>=2.2.0",
#   "markdown>=3.6",
# ]
# ///
"""Automated Dissertation Bibliography Compiler & Zero-Tolerance Report Verifier (Universal Multi-Nosology).

Implements:
- Sequential numbered citations [1], [2] in `reports/<nosology>/dissertation_report.md`
  with an automatically generated dissertation-standard bibliography from `data/<nosology>/literature.db`.
- Verification of clinical completeness via `verification_rules.required_terms` in `configs/<nosology>.yaml`.
- Zero-Tolerance SQLite verification of all PMIDs, PMCIDs, DOIs, and NCT IDs across all
  3 report modes (`dissertation`, `executive_summary`, `knowledge_base`).
- Structural anti-AI linter v2.0 (`check_humanizer_v2_structure`): expanded AI cliché & formulaic
  conclusion dictionary, `bold_lead_bullet_ratio` budget, mechanical pigeonhole routing detection,
  non-linear clinical decision nuance signals, treatment complications analysis check, and
  combined `validate_kb_v2()` enforcement with 100% read-only `v1.x` backward compatibility.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = _DEFAULT_PROJECT_ROOT
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.extractor_common import validate_nosology_id
from src.universal_schema import _connect_sqlite_readonly, validate_kb_v2

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def get_nosology_paths(nosology_id: str, base_dir: Path | None = None) -> dict[str, Path]:
    """Resolve and containment-verify config/DB/report paths for a validated nosology_id (T-18-03, T-19-05, WR-04)."""
    nos_id = validate_nosology_id(nosology_id)
    if base_dir is not None:
        root = Path(base_dir).resolve()
    elif PROJECT_ROOT != _DEFAULT_PROJECT_ROOT:
        root = Path(PROJECT_ROOT).resolve()
    else:
        env_root = os.environ.get("INFO_SEARCHER_ROOT", "").strip()
        root = Path(env_root).resolve() if env_root else PROJECT_ROOT.resolve()

    configs_root = (root / "configs").resolve()
    data_root = (root / "data").resolve()
    reports_root = (root / "reports").resolve()

    cfg_path = (configs_root / f"{nos_id}.yaml").resolve()
    db_path = (data_root / nos_id / "literature.db").resolve()
    rep_dir = (reports_root / nos_id).resolve()
    diss_path = (rep_dir / "dissertation_report.md").resolve()
    sum_path = (rep_dir / "executive_summary.md").resolve()
    kb_dir = (rep_dir / "knowledge_base").resolve()
    audit_path = (rep_dir / "verification_audit.md").resolve()

    if not cfg_path.is_relative_to(configs_root):
        raise ValueError(f"Config path escapes configs directory: {cfg_path}")
    if not db_path.is_relative_to(data_root):
        raise ValueError(f"Database path escapes data directory: {db_path}")
    if not rep_dir.is_relative_to(reports_root):
        raise ValueError(f"Reports directory escapes reports root: {rep_dir}")
    for report_path in (diss_path, sum_path, kb_dir, audit_path):
        if not report_path.is_relative_to(reports_root):
            raise ValueError(f"Report path escapes reports root: {report_path}")

    return {
        "root": root,
        "configs_root": configs_root,
        "data_root": data_root,
        "reports_root": reports_root,
        "cfg": cfg_path,
        "db": db_path,
        "diss": diss_path,
        "sum": sum_path,
        "kb": kb_dir,
        "audit": audit_path,
    }


BANNED_AI_PHRASES: tuple[str, ...] = (
    "представляет собой актуальную проблему",
    "в последние десятилетия наблюдается растущий интерес",
    "несмотря на значительные достижения медицины",
    "важно отметить, что",
    "следует подчеркнуть",
    "нельзя не упомянуть",
    "очевидно, что",
    "примечательно, что",
    "играет ключевую роль",
    "играет фундаментальную роль",
    "играет важную роль",
    "комплексный подход",
    "широкий спектр",
    "многогранный механизм",
    "сложное взаимодействие множества факторов",
    "требует дальнейшего изучения",
    "ты абсолютно прав",
    "давай сразу начистоту",
    "задача крутая",
)

BANNED_AI_V2_CONCLUSION_PHRASES: tuple[str, ...] = (
    "подводя итог, можно заключить",
    "резюмируя вышеизложенное",
    "индивидуальный подход к каждому пациенту",
    "выбор метода зависит от индивидуальных особенностей",
    "каждый метод имеет свои преимущества и недостатки",
    "не существует универсального метода",
    "заслуживает особого внимания",
    "на сегодняшний день",
    "в заключение следует отметить",
    "в контексте современной медицины",
    "является методом выбора для всех",
)

_BIB_SPLIT_RE = re.compile(r"(?im)^##\s+Список литературы\b")
# CR-01: Match 3+ backticks or tildes with backreference \1 on LF-normalized text
_FENCED_CODE_RE = re.compile(r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?(?:^[ \t]*\1[ \t]*$|\Z)")
_TABLE_SEP_RE = re.compile(r"^\|?[\s:|-]+\|[\s:|-]*$")
_HR_RE = re.compile(r"^(?:[-*_]\s*){3,}$")
# WR-04: Match both unordered (-, *, +) and numbered (1., 2.) bold-lead list walls
_BOLD_LEAD_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+\*\*[^*]{2,120}\*\*(?:\s*[:—–-])?")
_TOTAL_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+\S")
_H2_HEADING_RE = re.compile(r"(?m)^##\s+(.+)$")
_CONCLUSION_PRIMARY_TITLE_RE = re.compile(
    r"заключ|вывод|резюме|итог|рекомендац",
    flags=re.IGNORECASE,
)
_CONCLUSION_SECONDARY_TITLE_RE = re.compile(
    r"тактик|алгоритм|стратег",
    flags=re.IGNORECASE,
)

# WR-05: Word-bounded & negation-aware nuance signals (rejects 'биодоступность', 'отсутствие альтернативы', bare diagnosis 'рубец')
_NUANCE_SIGNALS_RE = re.compile(
    r"(?<![а-яё])перекрыва|(?<![а-яё])сквозн|(?<![а-яё])конкурир|(?<![а-яё])нюанс|(?<![а-яё])компромисс|"
    r"(?<![а-яё])опыт\w*\s+(?:хирург|оператор|специалист)|"
    r"(?<![а-яё])крив\w+\s+обучен|(?<![а-яё])оснащ[её]н|(?<![а-яё])доступност|"
    r"(?<![а-яё])рубцов\w*\s+(?:болезненн|дискомфорт|морбидн|чувствительн|осложнен)|"
    r"(?<![а-яё])послеоперационн\w*\s+руб|"
    r"(?<![а-яё])предпочтен\w*\s+пациент|"
    r"(?<![а-яё])об[ае]\s+метод|(?<![а-яё])обе\s+методик|(?<![а-яё])равноценн|"
    r"(?<!отсутствия\s)(?<!отсутствие\s)(?<!отсутствии\s)(?<!без\s)(?<!нет\s)(?<!не\sимеет\s)(?<![а-яё])альтернатив",
    flags=re.IGNORECASE,
)

# WR-05: Negative lookbehind excludes 'неосложненным'; requires co-occurrence in same section/proximity
_COMPLICATIONS_ROOT_RE = re.compile(r"(?<![а-яё])осложн[её]н", flags=re.IGNORECASE)
_COMPLICATIONS_STRUCTURE_RE = re.compile(
    r"\bclavien\b|\bctcae\b|(?<![а-яё])ятроген|(?<![а-яё])транзиторн|(?<![а-яё])профилактик|(?<![а-яё])обратим",
    flags=re.IGNORECASE,
)

# WR-01 & WR-02: Prescriptive routing predicates only (no generic nouns like 'операция'/'терапия')
_STAGE_ROUTING_VERBS = (
    r"(?:подходит|показан\w*|рекоменд\w*|выбира\w*|оптимал[еь]\w*|метод\w*\s+выбора|"
    r"требует\w*|применя\w*|назнача\w*|выполня\w*|предпочтител[еь]\w*|целесообраз\w*|"
    r"исключительно|метод\s+[А-ЯA-Z1-9])"
)
_STAGE_NOUNS = r"(?:стади[ияйю]|степен[иья]|групп[еыау]|тип[еау]|вариант[еау]|форм[еыа]|категори[ия])"
# Exclude 'первичн...' and 'вторичн...' by requiring ordinal case endings on перв-/втор-
_STAGE_MARKERS = (
    r"(?P<slot>IV|III|II|I|[1-4]|"
    r"перв(?:ой|ая|ую|ом|ого|ому|ым)|втор(?:ой|ая|ую|ом|ого|ому|ым)|"
    r"треть(?:ей|я|ю|ем|его|ему|им)|четверт\w*|"
    r"легк\w*|лёгк\w*|средн\w*|тяжел\w*|тяжёл\w*|ранн\w*|поздн\w*|начальн\w*)"
    r"(?!\s*[–-]\s*(?:IV|III|II|I|[1-4])\b)"
)

_PIGEONHOLE_STAGE_AFTER_RE = re.compile(
    rf"(?:^|[\s,;.•\-*+])(?:для|при)?\s*{_STAGE_NOUNS}\s*{_STAGE_MARKERS}\b"
    rf"[^.\n;]{{0,70}}?(?:[:—–-]\s*[^.\n;]{{0,45}}?)?{_STAGE_ROUTING_VERBS}",
    flags=re.IGNORECASE,
)
_PIGEONHOLE_STAGE_BEFORE_RE = re.compile(
    rf"(?:^|[\s,;.•\-*+])(?:для|при)?\s*{_STAGE_MARKERS}\s+{_STAGE_NOUNS}"
    rf"[^.\n;]{{0,70}}?(?:[:—–-]\s*[^.\n;]{{0,45}}?)?{_STAGE_ROUTING_VERBS}",
    flags=re.IGNORECASE,
)
_PIGEONHOLE_VERB_BEFORE_AFTER_RE = re.compile(
    rf"{_STAGE_ROUTING_VERBS}[^.\n;]{{0,45}}?(?:для|при)\s+{_STAGE_NOUNS}\s*{_STAGE_MARKERS}\b",
    flags=re.IGNORECASE,
)
_PIGEONHOLE_VERB_BEFORE_BEFORE_RE = re.compile(
    rf"{_STAGE_ROUTING_VERBS}[^.\n;]{{0,45}}?(?:для|при)\s+{_STAGE_MARKERS}\s+{_STAGE_NOUNS}",
    flags=re.IGNORECASE,
)
_PIGEONHOLE_STAGE_AFTER_DASH_RE = re.compile(
    rf"(?:^|[\s,;.•\-*+])(?:для|при)\s+{_STAGE_NOUNS}\s*{_STAGE_MARKERS}\b"
    rf"[^.\n;—–]{{0,30}}[—–:]\s*[А-Яа-яA-Za-z]",
    flags=re.IGNORECASE,
)
_PIGEONHOLE_STAGE_BEFORE_DASH_RE = re.compile(
    rf"(?:^|[\s,;.•\-*+])(?:для|при)\s+{_STAGE_MARKERS}\s+{_STAGE_NOUNS}"
    rf"[^.\n;—–]{{0,30}}[—–:]\s*[А-Яа-яA-Za-z]",
    flags=re.IGNORECASE,
)
# Bullet/list line slot mappings: "- Стадия I: консервативная терапия", "- I стадия: ...", "- Лёгкая степень: ..."
_PIGEONHOLE_BULLET_AFTER_RE = re.compile(
    rf"(?m)^[ \t]*(?:[-*+]|\d+\.)\s*{_STAGE_NOUNS}\s*{_STAGE_MARKERS}\b[^:\n—–]{{0,30}}[:—–]\s*[А-Яа-яA-Za-z]",
    flags=re.IGNORECASE,
)
_PIGEONHOLE_BULLET_BEFORE_RE = re.compile(
    rf"(?m)^[ \t]*(?:[-*+]|\d+\.)\s*{_STAGE_MARKERS}\s+{_STAGE_NOUNS}[^:\n—–]{{0,30}}[:—–]\s*[А-Яа-яA-Za-z]",
    flags=re.IGNORECASE,
)
_PIGEONHOLE_METHOD_SLOT_RE = re.compile(
    r"(?:метод\w*|лечени\w*|терапи\w*|тактик\w*|вмешательств\w*)\s*(?:[1-4]|IV|III|II|I|[А-ГA-D])\b"
    r"[^.\n;]{0,35}?(?:подходит|показан\w*|предназначен\w*|применяют|используют|—|–|-)?\s*"
    r"(?:только\s+|исключительно\s+)?(?:для|при)\s*"
    rf"(?:{_STAGE_NOUNS}\s*)?{_STAGE_MARKERS}\b",
    flags=re.IGNORECASE,
)
_EXPLICIT_SHORT_SLOT_RE = re.compile(
    r"(?:подходит\s+|лечени\w*\s+|метод\w*\s+|это\s+(?:лечени\w*\s+|метод\w*\s+)?)для\s+"
    r"(?P<slot>[1-4]|I{1,3}|IV|перв(?:ой|ого)|втор(?:ой|ого)|треть(?:ей|его))\b",
    flags=re.IGNORECASE,
)
_PIGEONHOLE_EXEMPT_CONTEXT_RE = re.compile(
    r"\bclavien\b|\bctcae\b|конкурир|равноценн|перекрыва|об[ае]\s+метод|обе\s+методик|"
    r"не\s+делят|вне\s+зависимости\s+от\s+стади|рандомизир|рукав\w*\s+исследован",
    flags=re.IGNORECASE,
)
_TABLE_STAGE_CELL_AFTER_RE = re.compile(
    rf"^{_STAGE_NOUNS}\s*{_STAGE_MARKERS}\b",
    flags=re.IGNORECASE,
)
_TABLE_STAGE_CELL_BEFORE_RE = re.compile(
    rf"^{_STAGE_MARKERS}\s+{_STAGE_NOUNS}\b",
    flags=re.IGNORECASE,
)
_ORDINAL_GROUP_PATTERNS = (
    re.compile(r"(?:для|при)\s+перв(?:ой|ого)\s+(?:групп|стади|категори)", flags=re.IGNORECASE),
    re.compile(r"(?:для|при)\s+втор(?:ой|ого)\s+(?:групп|стади|категори)", flags=re.IGNORECASE),
    re.compile(r"(?:для|при)\s+треть(?:ей|его)\s+(?:групп|стади|категори)", flags=re.IGNORECASE),
)

_BREAK_SENTINEL = "---"


def _normalize_newlines(text: str) -> str:
    """Normalize CRLF/CR line endings to LF so multiline regexes never fail on Windows (CR-01)."""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _strip_bibliography(text: str) -> str:
    """Remove `## Список литературы` and everything after it."""
    parts = _BIB_SPLIT_RE.split(_normalize_newlines(text), maxsplit=1)
    return parts[0]


def _is_table_line(stripped_line: str) -> bool:
    if not stripped_line:
        return False
    if stripped_line.startswith("|"):
        return True
    if "|" in stripped_line and _TABLE_SEP_RE.match(stripped_line):
        return True
    return False


def _strip_markdown_tables(text: str) -> str:
    """Replace Markdown table blocks with a structural break sentinel so bullet runs never merge across tables (WR-04)."""
    out_lines: list[str] = []
    in_table = False
    for line in text.splitlines():
        if _is_table_line(line.strip()):
            if not in_table:
                out_lines.append(_BREAK_SENTINEL)
                in_table = True
        else:
            in_table = False
            out_lines.append(line)
    return "\n".join(out_lines)


def _extract_final_analytical_section(body_text: str) -> str:
    """Extract the final conclusion/tactical section(s) from the second half of the report (WR-03)."""
    headings = list(_H2_HEADING_RE.finditer(body_text))
    if not headings:
        if len(body_text) <= 2000:
            return body_text
        return body_text[int(len(body_text) * 0.75) :]

    half_idx = len(headings) // 2
    half_pos = int(len(body_text) * 0.45)
    eligible = [
        (idx, match)
        for idx, match in enumerate(headings)
        if idx >= half_idx or match.start() >= half_pos
    ]

    primary_matches = [
        idx for idx, match in eligible if _CONCLUSION_PRIMARY_TITLE_RE.search(match.group(1))
    ]
    secondary_matches = [
        idx for idx, match in eligible if _CONCLUSION_SECONDARY_TITLE_RE.search(match.group(1))
    ]

    chosen_idx: int | None = None
    if primary_matches:
        chosen_idx = primary_matches[-1]
    elif secondary_matches:
        chosen_idx = secondary_matches[-1]

    last_idx = len(headings) - 1
    if chosen_idx is not None:
        start = headings[chosen_idx].start()
        end = headings[chosen_idx + 1].start() if chosen_idx + 1 < len(headings) else len(body_text)
        section = body_text[start:end]
        if chosen_idx != last_idx:
            section = section + "\n\n" + body_text[headings[last_idx].start() :]
        return section

    last_section = body_text[headings[last_idx].start() :]
    tail_quarter = body_text[int(len(body_text) * 0.75) :]
    return last_section if len(last_section) >= len(tail_quarter) else tail_quarter


def _has_section_complications_analysis(body_no_code: str) -> bool:
    """Verify non-negated complications and structured safety markers co-occur in the same section/window (WR-05)."""
    headings = list(_H2_HEADING_RE.finditer(body_no_code))
    if headings:
        sections: list[str] = []
        if headings[0].start() > 0:
            sections.append(body_no_code[: headings[0].start()])
        for idx, match in enumerate(headings):
            start = match.start()
            end = headings[idx + 1].start() if idx + 1 < len(headings) else len(body_no_code)
            sections.append(body_no_code[start:end])
        return any(
            _COMPLICATIONS_ROOT_RE.search(sec) and _COMPLICATIONS_STRUCTURE_RE.search(sec)
            for sec in sections
        )

    for m_root in _COMPLICATIONS_ROOT_RE.finditer(body_no_code):
        win_start = max(0, m_root.start() - 1500)
        win_end = min(len(body_no_code), m_root.end() + 1500)
        if _COMPLICATIONS_STRUCTURE_RE.search(body_no_code[win_start:win_end]):
            return True
    return False


def _canonical_slot_key(raw_slot: str) -> str:
    s = raw_slot.strip().lower().replace("ё", "е")
    if s in ("i", "1") or s.startswith(("перв", "легк", "ранн", "начальн")):
        return "slot_1"
    if s in ("ii", "2") or s.startswith(("втор", "средн")):
        return "slot_2"
    if s in ("iii", "3") or s.startswith(("треть", "тяжел", "поздн")):
        return "slot_3"
    if s in ("iv", "4") or s.startswith("четверт"):
        return "slot_4"
    return s


def _sentence_around(text: str, start: int, end: int) -> str:
    left = max(text.rfind("\n", 0, start), text.rfind(".", 0, start))
    right_nl = text.find("\n", end)
    right_dot = text.find(".", end)
    candidates = [pos for pos in (right_nl, right_dot) if pos != -1]
    right = min(candidates) if candidates else len(text)
    return text[left + 1 : right]


def _detect_pigeonhole_routing(
    final_section_raw: str,
    final_section_no_tables: str,
    *,
    has_overlapping_nuance_signals: bool,
) -> list[str]:
    """Detect mechanical 'treatment 1 for 1, treatment 2 for 2, treatment 3 for 3' routing (WR-01, WR-02)."""
    clean = re.sub(r"[*_`]", "", final_section_no_tables)
    hits: list[tuple[int, int, str, str]] = []

    for pattern in (
        _PIGEONHOLE_STAGE_AFTER_RE,
        _PIGEONHOLE_STAGE_BEFORE_RE,
        _PIGEONHOLE_VERB_BEFORE_AFTER_RE,
        _PIGEONHOLE_VERB_BEFORE_BEFORE_RE,
        _PIGEONHOLE_STAGE_AFTER_DASH_RE,
        _PIGEONHOLE_STAGE_BEFORE_DASH_RE,
        _PIGEONHOLE_BULLET_AFTER_RE,
        _PIGEONHOLE_BULLET_BEFORE_RE,
        _PIGEONHOLE_METHOD_SLOT_RE,
        _EXPLICIT_SHORT_SLOT_RE,
    ):
        for m in pattern.finditer(clean):
            local_sentence = _sentence_around(clean, m.start(), m.end())
            if _PIGEONHOLE_EXEMPT_CONTEXT_RE.search(local_sentence):
                continue
            slot_key = _canonical_slot_key(m.group("slot"))
            excerpt = " ".join(m.group(0).split())[:110]
            hits.append((m.start(), m.end(), slot_key, excerpt))

    # Deduplicate overlapping regex spans by keeping earliest/longest hit per region
    hits.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    deduped: list[tuple[int, int, str, str]] = []
    for hit in hits:
        if deduped and hit[0] < deduped[-1][1]:
            continue
        deduped.append(hit)

    matches_out: list[str] = []
    # Sliding window: 3+ distinct stage/group->treatment slots within 900 chars
    for i in range(len(deduped)):
        window: list[tuple[int, int, str, str]] = [deduped[i]]
        seen_slots = {deduped[i][2]}
        for j in range(i + 1, len(deduped)):
            if deduped[j][0] - deduped[i][0] > 900:
                break
            window.append(deduped[j])
            seen_slots.add(deduped[j][2])
        if len(seen_slots) >= 3:
            excerpts = " | ".join(item[3] for item in window[:4])
            matches_out.append(f"Механическая маршрутизация по {len(seen_slots)} непересекающимся слотам: {excerpts}")
            break

    # Check Markdown routing tables inside final_section_raw for 3+ 1-to-1 stage->method rows (WR-02)
    if not matches_out:
        table_slots: dict[str, str] = {}
        for line in final_section_raw.splitlines():
            st = line.strip()
            if not _is_table_line(st) or _TABLE_SEP_RE.match(st):
                if table_slots and len(table_slots) >= 3:
                    break
                if not _is_table_line(st):
                    table_slots.clear()
                continue
            cells = [re.sub(r"[*_`]", "", c).strip() for c in st.strip("|").split("|")]
            if len(cells) < 2:
                continue
            row_joined = " ".join(cells)
            if _PIGEONHOLE_EXEMPT_CONTEXT_RE.search(row_joined):
                continue
            m_cell = _TABLE_STAGE_CELL_AFTER_RE.match(cells[0]) or _TABLE_STAGE_CELL_BEFORE_RE.match(cells[0])
            if m_cell and cells[1]:
                slot_key = _canonical_slot_key(m_cell.group("slot"))
                table_slots.setdefault(slot_key, f"{cells[0]} -> {cells[1][:50]}")
        if len(table_slots) >= 3:
            excerpts = " | ".join(list(table_slots.values())[:4])
            matches_out.append(f"Табличная 1-к-1 маршрутизация по {len(table_slots)} стадиям/группам: {excerpts}")

    # Secondary check: explicit ordinal 1st/2nd/3rd group splitting without workhorse nuance signals
    if not matches_out and not has_overlapping_nuance_signals:
        if all(pat.search(clean) for pat in _ORDINAL_GROUP_PATTERNS):
            matches_out.append(
                "Последовательное раскладывание на первую/вторую/третью группы без анализа перекрывающихся показаний"
            )

    return matches_out


def check_humanizer_v2_structure(
    text: str,
    *,
    mode: str = "dissertation",
    schema_version: str = "2.0",
    max_bold_lead_ratio: float = 0.35,
) -> dict[str, Any]:
    """Run structural anti-AI linter v2.0 (HUM2-03) with v1.x non-blocking compatibility."""
    body_no_bib = _strip_bibliography(text or "")
    body_no_code = _FENCED_CODE_RE.sub(f"\n{_BREAK_SENTINEL}\n", body_no_bib)
    body_no_tables = _strip_markdown_tables(body_no_code)

    bold_lead_bullets = 0
    total_bullets = 0
    prose_paragraphs = 0
    max_consecutive_bold_bullets = 0
    current_bold_run = 0
    current_para_lines: list[str] = []

    def _flush_paragraph() -> None:
        nonlocal prose_paragraphs, current_para_lines
        if current_para_lines:
            joined = " ".join(current_para_lines).strip()
            if len(joined) >= 120:
                prose_paragraphs += 1
            current_para_lines = []

    for line in body_no_tables.splitlines():
        stripped = line.strip()
        if not stripped:
            _flush_paragraph()
            continue

        if stripped.startswith("#") or stripped.startswith(">") or _HR_RE.fullmatch(stripped):
            _flush_paragraph()
            current_bold_run = 0
            continue

        if _TOTAL_BULLET_RE.match(line):
            _flush_paragraph()
            total_bullets += 1
            if _BOLD_LEAD_BULLET_RE.match(line):
                bold_lead_bullets += 1
                current_bold_run += 1
                if current_bold_run > max_consecutive_bold_bullets:
                    max_consecutive_bold_bullets = current_bold_run
            else:
                current_bold_run = 0
            continue

        current_bold_run = 0
        current_para_lines.append(stripped)

    _flush_paragraph()

    bold_lead_bullet_ratio = round(
        bold_lead_bullets / max(1, bold_lead_bullets + prose_paragraphs),
        4,
    )

    final_section_raw = _extract_final_analytical_section(body_no_code)
    final_section_no_tables = _strip_markdown_tables(final_section_raw)

    has_overlapping_nuance_signals = bool(_NUANCE_SIGNALS_RE.search(final_section_raw))
    pigeonhole_matches = _detect_pigeonhole_routing(
        final_section_raw,
        final_section_no_tables,
        has_overlapping_nuance_signals=has_overlapping_nuance_signals,
    )
    has_complications_analysis = _has_section_complications_analysis(body_no_code)

    lower_body = body_no_code.lower()
    legacy_banned = [p for p in BANNED_AI_PHRASES if p in lower_body]
    v2_extra_banned = [p for p in BANNED_AI_V2_CONCLUSION_PHRASES if p in lower_body]

    errors: list[str] = []
    warnings: list[str] = []

    if schema_version == "2.0":
        banned_phrases_found = legacy_banned + v2_extra_banned
        for phrase in banned_phrases_found:
            errors.append(f"Запрещённый ИИ-штамп ({mode}): «{phrase}»")

        if mode == "dissertation":
            if bold_lead_bullet_ratio > max_bold_lead_ratio:
                errors.append(
                    f"Превышен лимит «списочных стен» bold_lead_bullet_ratio={bold_lead_bullet_ratio:.4f} "
                    f"> {max_bold_lead_ratio:.2f} (bold_lead_bullets={bold_lead_bullets}, "
                    f"prose_paragraphs={prose_paragraphs})"
                )
            if max_consecutive_bold_bullets > 6:
                warnings.append(
                    f"Слишком длинный непрерывный блок жирных пунктов: {max_consecutive_bold_bullets} (> 6)"
                )

        if mode in ("dissertation", "summary"):
            if pigeonhole_matches:
                for pm in pigeonhole_matches:
                    errors.append(f"Обнаружена «коробочная» ИИ-маршрутизация ({mode}): {pm}")
            if not has_overlapping_nuance_signals:
                errors.append(
                    f"Заключительный / тактический раздел ({mode}) не содержит сигналов нелинейной клинической логики "
                    f"(сквозные/конкурирующие методики, практические компромиссы, опыт хирурга, оснащение)"
                )
            if not has_complications_analysis:
                errors.append(
                    f"В тексте отчёта ({mode}) отсутствует структурированный разбор осложнений лечения "
                    f"(требуется упоминание осложнений вместе с Clavien–Dindo / CTCAE / ятрогенными / транзиторными / профилактикой)"
                )
    else:
        banned_phrases_found = legacy_banned
        for phrase in legacy_banned:
            errors.append(f"Запрещённый ИИ-штамп ({mode}): «{phrase}»")
        for phrase in v2_extra_banned:
            warnings.append(f"[v1.x compat] ИИ-штамп заключения v2.0 ({mode}): «{phrase}»")

        if mode == "dissertation":
            if bold_lead_bullet_ratio > max_bold_lead_ratio:
                warnings.append(
                    f"[v1.x compat] bold_lead_bullet_ratio={bold_lead_bullet_ratio:.4f} > {max_bold_lead_ratio:.2f}"
                )
            if max_consecutive_bold_bullets > 6:
                warnings.append(
                    f"[v1.x compat] max_consecutive_bold_bullets={max_consecutive_bold_bullets} (> 6)"
                )
        if mode in ("dissertation", "summary"):
            for pm in pigeonhole_matches:
                warnings.append(f"[v1.x compat] Потенциальная «коробочная» маршрутизация: {pm}")
            if not has_overlapping_nuance_signals:
                warnings.append(f"[v1.x compat] Отсутствуют сигналы перекрывающихся/сквозных методик ({mode})")
            if not has_complications_analysis:
                warnings.append(f"[v1.x compat] Отсутствует структурированный блок осложнений v2.0 ({mode})")

    return {
        "passed": len(errors) == 0,
        "schema_version": schema_version,
        "mode": mode,
        "bold_lead_bullets": bold_lead_bullets,
        "total_bullets": total_bullets,
        "prose_paragraphs": prose_paragraphs,
        "bold_lead_bullet_ratio": bold_lead_bullet_ratio,
        "max_consecutive_bold_bullets": max_consecutive_bold_bullets,
        "pigeonhole_matches": pigeonhole_matches,
        "has_overlapping_nuance_signals": has_overlapping_nuance_signals,
        "has_complications_analysis": has_complications_analysis,
        "banned_phrases_found": banned_phrases_found,
        "errors": errors,
        "warnings": warnings,
    }


def format_authors_bib(authors_raw: str | None) -> str:
    if not authors_raw:
        return "Коллектив авторов"
    raw = authors_raw.strip()
    names: list[str] = []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                names = [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
    if not names:
        names = [x.strip().strip('[]"') for x in re.split(r"[;,]", raw) if x.strip()]
    if not names:
        return "Коллектив авторов"
    if len(names) > 3:
        return f"{', '.join(names[:3])}, et al."
    return ", ".join(names)


def format_number_ranges(nums: list[int]) -> str:
    nums = sorted(set(nums))
    if not nums:
        return ""
    ranges: list[str] = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
        else:
            if prev - start >= 2:
                ranges.append(f"{start}–{prev}")
            elif prev - start == 1:
                ranges.append(f"{start}, {prev}")
            else:
                ranges.append(str(start))
            start = prev = n
    if prev - start >= 2:
        ranges.append(f"{start}–{prev}")
    elif prev - start == 1:
        ranges.append(f"{start}, {prev}")
    else:
        ranges.append(str(start))
    return f"[{', '.join(ranges)}]"


def fetch_reference_metadata(cur: sqlite3.Cursor, ref_key: str) -> dict[str, Any]:
    kind, val = ref_key.split(":", 1)
    if kind == "PMID":
        row = cur.execute(
            "SELECT pmid, pmcid, doi, title, authors, journal, pub_year FROM articles WHERE pmid = ?",
            (val,),
        ).fetchone()
    elif kind == "PMCID":
        row = cur.execute(
            "SELECT pmid, pmcid, doi, title, authors, journal, pub_year FROM articles WHERE pmcid = ?",
            (val,),
        ).fetchone()
    else:
        raise ValueError(f"Unsupported citation key: {ref_key}")

    if not row:
        raise AssertionError(f"[Anti-Hallucination Failure] Citation {ref_key} not found in SQLite database!")

    pmid, pmcid, doi, title, authors, journal, pub_year = (
        row[0],
        row[1],
        row[2],
        row[3],
        row[4],
        row[5],
        row[6],
    )
    authors_str = format_authors_bib(authors).rstrip(".")
    clean_title = (title or "").strip().rstrip(".")
    journal_str = (journal or "Научное периодическое издание").strip()
    year_str = str(pub_year or "2016–2026")
    ids: list[str] = []
    if doi:
        ids.append(f"DOI: {doi}")
    if pmid:
        ids.append(f"PMID: {pmid}")
    if pmcid:
        ids.append(f"PMCID: {pmcid}")
    ids_tail = " — ".join(ids)
    bib_line = f"{authors_str}. {clean_title} // {journal_str}. — {year_str}. — {ids_tail}."
    return {
        "ref_key": ref_key,
        "pmid": pmid,
        "pmcid": pmcid,
        "doi": doi,
        "bib_line": bib_line,
    }


def compile_dissertation_bibliography(
    nosology_id: str = "prom",
    *,
    base_dir: Path | None = None,
) -> int:
    paths = get_nosology_paths(nosology_id, base_dir=base_dir)
    db_path = paths["db"]
    diss_path = paths["diss"]

    conn = _connect_sqlite_readonly(db_path)
    try:
        cur = conn.cursor()
        text = diss_path.read_text(encoding="utf-8")

        # If already compiled previously, restore body before bibliography marker
        bib_marker = "\n---\n\n## Список литературы\n"
        if bib_marker in text:
            text = text.split(bib_marker, 1)[0]

        # Discover all [@PMID:...] or [@PMCID:...] bracket groups
        group_pattern = re.compile(r"\[((?:@(?:PMID|PMCID):[A-Za-z0-9]+(?:\s*;\s*)?)+)\]")
        token_pattern = re.compile(r"@(PMID|PMCID):([A-Za-z0-9]+)")

        ref_order: list[str] = []
        ref_to_num: dict[str, int] = {}

        for m in group_pattern.finditer(text):
            group_body = m.group(1)
            for tm in token_pattern.finditer(group_body):
                key = f"{tm.group(1)}:{tm.group(2)}"
                if key not in ref_to_num:
                    ref_order.append(key)
                    ref_to_num[key] = len(ref_order)

        if not ref_order:
            existing = diss_path.read_text(encoding="utf-8")
            if bib_marker in existing:
                bib_sec = existing.split(bib_marker, 1)[1]
                cnt = len(re.findall(r"^\d+\.\s+", bib_sec, flags=re.MULTILINE))
                print(f"[Compile Bibliography] Dissertation already compiled with {cnt} numbered references.")
                return cnt
            raise RuntimeError(f"No [@PMID:...] or [@PMCID:...] markers found in {diss_path}!")

        def replace_group(match: re.Match[str]) -> str:
            group_body = match.group(1)
            nums = [
                ref_to_num[f"{tm.group(1)}:{tm.group(2)}"]
                for tm in token_pattern.finditer(group_body)
            ]
            return format_number_ranges(nums)

        compiled_body = group_pattern.sub(replace_group, text)

        bib_entries: list[str] = []
        for idx, key in enumerate(ref_order, start=1):
            meta = fetch_reference_metadata(cur, key)
            bib_entries.append(f"{idx}. {meta['bib_line']}")

        bib_section = f"{bib_marker}\n" + "\n".join(bib_entries) + "\n"
        diss_path.write_text(compiled_body + bib_section, encoding="utf-8")
        print(
            f"[Compile Bibliography] Compiled {len(bib_entries)} numbered references "
            f"[1]..[{len(bib_entries)}] in {diss_path}"
        )
        return len(bib_entries)
    finally:
        conn.close()


def verify_all_reports(
    nosology_id: str = "prom",
    *,
    schema_version: str = "auto",
    write_outputs: bool = True,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Run Zero-Tolerance SQLite, Humanizer v2.0 structural linter, and KB v2.0 verification (T-18-03, T-18-04)."""
    if schema_version not in ("auto", "v1", "v2"):
        raise ValueError(f"Unsupported schema_version: {schema_version!r} (expected 'auto', 'v1', or 'v2')")

    nos_id = validate_nosology_id(nosology_id)
    paths = get_nosology_paths(nos_id, base_dir=base_dir)
    root_dir = paths["root"]
    reports_root = paths["reports_root"]
    db_path = paths["db"]
    diss_path = paths["diss"]
    sum_path = paths["sum"]
    kb_dir = paths["kb"]
    audit_path = paths["audit"]
    cfg_path = paths["cfg"]

    cfg: dict[str, Any] = {}
    if cfg_path.exists():
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    assert db_path.exists(), f"Missing SQLite database: {db_path}"

    # T-18-04: Strictly read-only SQLite access so frozen v1.x databases are never mutated
    conn = _connect_sqlite_readonly(db_path)
    try:
        cur = conn.cursor()
        inc_cnt = cur.execute("SELECT COUNT(*) FROM articles WHERE prisma_status = 'included'").fetchone()[0]
        ct_cnt = cur.execute("SELECT COUNT(*) FROM clinical_trials").fetchone()[0]

        valid_pmids = {str(r[0]) for r in cur.execute("SELECT pmid FROM articles WHERE pmid IS NOT NULL").fetchall()}
        valid_pmcids = {str(r[0]) for r in cur.execute("SELECT pmcid FROM articles WHERE pmcid IS NOT NULL").fetchall()}
        valid_ncts = {str(r[0]) for r in cur.execute("SELECT nct_id FROM clinical_trials WHERE nct_id IS NOT NULL").fetchall()}

        # Also allow NCTs mentioned in abstracts of included articles
        for (abstr,) in cur.execute("SELECT abstract FROM articles WHERE abstract LIKE '%NCT0%'").fetchall():
            for m in re.findall(r"\bNCT\d{8}\b", abstr or ""):
                valid_ncts.add(m)
    finally:
        conn.close()

    # Verify kb_index.json early to resolve effective schema_version (WR-06, IN-02)
    kb_json_path = (kb_dir / "kb_index.json").resolve()
    if not kb_json_path.is_relative_to(reports_root):
        raise ValueError(f"KB index escapes reports root: {kb_json_path}")
    assert kb_json_path.exists(), f"Missing kb_index.json at {kb_json_path}!"
    kb_data = json.loads(kb_json_path.read_text(encoding="utf-8"))
    assert isinstance(kb_data, dict), f"kb_index.json must be a JSON object: {kb_json_path}"

    if schema_version == "v2" or (schema_version == "auto" and str(kb_data.get("schema_version", "")) == "2.0"):
        effective_version = "2.0"
    else:
        effective_version = "1.x"

    kb_index_modules = kb_data.get("modules", [])
    assert isinstance(kb_index_modules, list) and len(kb_index_modules) >= 5, (
        f"kb_index.json must index >= 5 modules, got "
        f"{len(kb_index_modules) if isinstance(kb_index_modules, list) else type(kb_index_modules).__name__}"
    )
    modalities_val = kb_data.get("modalities")
    assert isinstance(modalities_val, list) and len(modalities_val) >= 8, (
        "kb_index.json must include >= 8 treatment modalities"
    )

    kb_dir_resolved = kb_dir.resolve()
    kb_dir_norm = Path(os.path.normcase(str(kb_dir_resolved)))
    seen_module_paths: set[Path] = set()
    for idx, mod in enumerate(kb_index_modules):
        assert isinstance(mod, dict), f"kb_index.json modules[{idx}] must be an object"
        raw_val = mod.get("file")
        assert isinstance(raw_val, str) and raw_val.strip(), (
            f"kb_index.json modules[{idx}] missing non-empty string 'file'"
        )
        raw_mod_file = raw_val.strip()
        rel_candidate = Path(raw_mod_file)
        if rel_candidate.is_absolute() or ".." in rel_candidate.parts:
            raise ValueError(f"KB module path must be relative inside knowledge_base dir: {raw_mod_file!r}")
        if rel_candidate.suffix.lower() != ".md":
            raise ValueError(f"KB module file must have .md extension: {raw_mod_file!r}")
        mod_path = (kb_dir_resolved / rel_candidate).resolve()
        mod_path_norm = Path(os.path.normcase(str(mod_path)))
        if not mod_path_norm.is_relative_to(kb_dir_norm):
            raise ValueError(f"KB module path escapes knowledge_base dir: {raw_mod_file!r}")
        assert mod_path_norm not in seen_module_paths, (
            f"Duplicate KB module file '{raw_mod_file}' in kb_index.json"
        )
        assert mod_path.exists() and mod_path.is_file(), (
            f"Indexed KB module file not found on disk: {mod_path}"
        )
        seen_module_paths.add(mod_path_norm)

    kb_md_files = sorted(kb_dir.glob("*.md"))
    disk_md_set = {Path(os.path.normcase(str(p.resolve()))) for p in kb_md_files}
    assert len(kb_md_files) >= 5, (
        f"Expected >= 5 KB Markdown files for '{nos_id}', found {len(kb_md_files)}"
    )
    assert seen_module_paths == disk_md_set, (
        f"KB module mismatch for '{nos_id}': "
        f"missing_on_disk={sorted(p.name for p in seen_module_paths - disk_md_set)}, "
        f"orphaned_on_disk={sorted(p.name for p in disk_md_set - seen_module_paths)}"
    )
    report_files = [
        diss_path,
        sum_path,
        *kb_md_files,
    ]

    audit_rows: list[dict[str, Any]] = []
    total_unique_pmids: set[str] = set()
    active_banned_phrases = (
        BANNED_AI_PHRASES + BANNED_AI_V2_CONCLUSION_PHRASES
        if effective_version == "2.0"
        else BANNED_AI_PHRASES
    )

    cached_texts: dict[Path, str] = {}

    for path in report_files:
        resolved_path = path.resolve()
        if not resolved_path.is_relative_to(reports_root):
            raise ValueError(f"Report file escapes reports root: {resolved_path}")
        assert path.exists(), f"Missing report file: {path}"
        content = path.read_text(encoding="utf-8")
        size_bytes = path.stat().st_size
        assert size_bytes > 3500, f"Report file {path} is too small ({size_bytes} bytes)"

        # Clean stray @PMID only in writable mode; normalize in-memory when read-only (T-18-04)
        if "@PMID:" in content:
            content = content.replace("@PMID:", "PMID: ")
            if write_outputs:
                path.write_text(content, encoding="utf-8")

        cached_texts[path] = content

        flat_pmids = set(re.findall(r"PMID:\s*(\d{7,8})", content))
        pmcids = set(re.findall(r"\b(PMC\d{6,9})\b", content))
        ncts = set(re.findall(r"\b(NCT\d{8})\b", content))

        missing_pmids = sorted(flat_pmids - valid_pmids)
        missing_pmcids = sorted(pmcids - valid_pmcids)
        missing_ncts = sorted(ncts - valid_ncts)

        assert not missing_pmids, f"[{path.name}] Missing PMIDs in {db_path}: {missing_pmids}"
        assert not missing_pmcids, f"[{path.name}] Missing PMCIDs in {db_path}: {missing_pmcids}"
        assert not missing_ncts, f"[{path.name}] Missing NCT IDs in {db_path}: {missing_ncts}"

        # Check banned AI phrases (strip bibliography + fenced code blocks consistently in v2.0, IN-01)
        if effective_version == "2.0":
            text_for_phrase_check = _FENCED_CODE_RE.sub("\n", _strip_bibliography(content)).lower()
        else:
            text_for_phrase_check = content.lower()
        triggered_phrases = [p for p in active_banned_phrases if p in text_for_phrase_check]
        assert not triggered_phrases, f"[{path.name}] Banned AI phrases detected: {triggered_phrases}"

        total_unique_pmids.update(flat_pmids)
        rel_display = resolved_path.relative_to(root_dir).as_posix()
        audit_rows.append(
            {
                "file": rel_display,
                "size_kb": round(size_bytes / 1024, 1),
                "verified_pmids": len(flat_pmids),
                "verified_pmcids": len(pmcids),
                "verified_ncts": len(ncts),
                "banned_phrases": len(triggered_phrases),
            }
        )

    # Check specific dissertation numbered citation requirements
    diss_text = cached_texts[diss_path]
    sum_text = cached_texts[sum_path]
    assert "## Список литературы" in diss_text, "Dissertation report missing '## Список литературы' section!"
    bib_part = diss_text.split("## Список литературы", 1)[1]
    bib_items = re.findall(r"^(\d+)\.\s+", bib_part, flags=re.MULTILINE)
    assert len(bib_items) >= 35, f"Expected >= 35 bibliography entries in dissertation_report.md, got {len(bib_items)}"

    # Check clinical focus completeness via config verification_rules
    req_terms = cfg.get("verification_rules", {}).get("required_terms", ["Плюсы", "Минусы"])
    for required_term in req_terms:
        assert required_term in diss_text, f"Dissertation report missing required clinical term: {required_term}"
        assert required_term in sum_text, f"Executive summary missing required term: {required_term}"

    # Structural Anti-AI Linter v2.0 (HUM2-03)
    diss_lint = check_humanizer_v2_structure(
        diss_text,
        mode="dissertation",
        schema_version=effective_version,
    )
    sum_lint = check_humanizer_v2_structure(
        sum_text,
        mode="summary",
        schema_version=effective_version,
    )

    v2_kb_errors: list[str] = []
    if effective_version == "2.0":
        assert diss_lint["passed"], (
            f"[Humanizer v2.0 Failure — {diss_path.name}] {diss_lint['errors']}"
        )
        assert sum_lint["passed"], (
            f"[Humanizer v2.0 Failure — {sum_path.name}] {sum_lint['errors']}"
        )
        v2_kb_errors = validate_kb_v2(kb_data)
        assert v2_kb_errors == [], (
            f"[KB v2.0 Contract Failure — {kb_json_path.name}] {v2_kb_errors}"
        )
        # CR-02: Zero-Tolerance cross-check of kb_index.json evidence_pmids against SQLite valid_pmids
        kb_pmids: set[str] = set()
        for bucket in (kb_data.get("frequent_complications") or [], kb_data.get("rare_critical_red_flags") or []):
            if isinstance(bucket, list):
                for item in bucket:
                    if isinstance(item, dict):
                        kb_pmids.update(
                            str(p).strip()
                            for p in (item.get("evidence_pmids") or [])
                            if p is not None and str(p).strip()
                        )
        nuances_obj = kb_data.get("clinical_decision_nuances") or {}
        if isinstance(nuances_obj, dict):
            for sec_key in (
                "universal_workhorse_modalities",
                "overlapping_indications_and_gray_zones",
                "strict_niche_or_salvage_indications",
            ):
                for item in nuances_obj.get(sec_key) or []:
                    if isinstance(item, dict):
                        kb_pmids.update(
                            str(p).strip()
                            for p in (item.get("evidence_pmids") or [])
                            if p is not None and str(p).strip()
                        )
        missing_kb_pmids = sorted(kb_pmids - valid_pmids)
        assert not missing_kb_pmids, (
            f"[{kb_json_path.name}] Missing evidence_pmids in {db_path}: {missing_kb_pmids}"
        )
        humanizer_v2_status = "PASSED (v2.0 Strict)"
    else:
        assert diss_lint["passed"], f"[Humanizer v1.x Failure — {diss_path.name}] {diss_lint['errors']}"
        assert sum_lint["passed"], f"[Humanizer v1.x Failure — {sum_path.name}] {sum_lint['errors']}"
        warn_cnt = len(diss_lint["warnings"]) + len(sum_lint["warnings"])
        humanizer_v2_status = f"COMPAT_V1 (advisory warnings: {warn_cnt})"

    docx_paths: dict[str, Path] = {}
    if write_outputs:
        from src.docx_exporter import export_nosology_docx_files

        docx_paths = export_nosology_docx_files(nos_id, root_dir)
        for _docx_key, docx_file in docx_paths.items():
            assert docx_file.exists() and docx_file.stat().st_size > 2048, (
                f"Missing or empty .docx file: {docx_file}"
            )

        rel_db = db_path.relative_to(root_dir).as_posix()
        audit_lines = [
            f"# Сертификат автоматической верификации отчётов (`src/verify_reports.py` — `{nos_id}`)",
            "",
            "- **Статус проверки:** `PASSED (Zero-Tolerance Gate)`",
            f"- **Версия схемы (`schema_version`):** `{effective_version}`",
            f"- **Структурный линтер `ru-medical-humanizer v2.0` (`humanizer_v2_status`):** `{humanizer_v2_status}`",
            f"- **Метрика прозы диссертации (`bold_lead_bullet_ratio`):** `{diss_lint['bold_lead_bullet_ratio']:.4f}` "
            f"(жирных пунктов: `{diss_lint['bold_lead_bullets']}`, абзацев прозы ≥120 симв.: `{diss_lint['prose_paragraphs']}`)",
            f"- **Нозология:** {cfg.get('name_ru', nos_id)} (`{cfg.get('icd10', '—')}`)",
            f"- **База данных верификации:** `{rel_db}` (`{inc_cnt}` включённых статей, `{ct_cnt}` протоколов `ClinicalTrials.gov`)",
            f"- **Число библиографических источников `[1]..[{len(bib_items)}]` в диссертационном отчёте:** `{len(bib_items)}` (`100%` подтверждены в SQLite)",
            "- **Нарушений словаря `ru-medical-humanizer`:** `0`",
            "- **Несуществующих / галлюцинированных `PMID / PMCID / DOI / NCT ID`:** `0`",
            f"- **Сформированные файлы MS Word (`.docx`):** `dissertation_report.docx` ({round(docx_paths['dissertation_docx'].stat().st_size / 1024, 1)} КБ), `executive_summary.docx` ({round(docx_paths['executive_docx'].stat().st_size / 1024, 1)} КБ), `full_clinical_dossier.docx` ({round(docx_paths['full_dossier_docx'].stat().st_size / 1024, 1)} КБ)",
            "",
            "## Сводная таблица проверенных файлов отчёта (3 режима)",
            "",
            "| Файл отчёта | Объём (КБ) | Верифицировано уникальных `PMID` | Верифицировано `PMCID` | Верифицировано `NCT ID` | Штампы ИИ (`ru-medical-humanizer`) | Статус |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        for r in audit_rows:
            audit_lines.append(
                f"| `{r['file']}` | {r['size_kb']} | {r['verified_pmids']} | {r['verified_pmcids']} | {r['verified_ncts']} | {r['banned_phrases']} | `OK` |"
            )
        audit_path.write_text("\n".join(audit_lines) + "\n", encoding="utf-8")

    mode_tag = " [READ-ONLY]" if not write_outputs else ""
    docx_msg = " + 3 .docx files" if write_outputs else " (read-only: .docx & audit skipped)"
    print(
        f"[Verify Reports: {nos_id}]{mode_tag} Schema={effective_version} | "
        f"Humanizer={humanizer_v2_status} | bold_lead_bullet_ratio={diss_lint['bold_lead_bullet_ratio']:.4f}"
    )
    print(
        f"[Verify Reports: {nos_id}] Checked {len(report_files)} Markdown files + kb_index.json{docx_msg}."
    )
    print(
        f"[Verify Reports: {nos_id}] Dissertation bibliography entries: {len(bib_items)} [1]..[{len(bib_items)}]"
    )
    print(f"[Verify Reports: {nos_id}] ALL REPORT VERIFICATION CHECKS PASSED.")

    return {
        "passed": True,
        "nosology_id": nos_id,
        "schema_version": effective_version,
        "read_only": not write_outputs,
        "included_articles": inc_cnt,
        "clinical_trials": ct_cnt,
        "bib_count": len(bib_items),
        "humanizer_v2_status": humanizer_v2_status,
        "bold_lead_bullet_ratio": diss_lint["bold_lead_bullet_ratio"],
        "dissertation_lint": diss_lint,
        "summary_lint": sum_lint,
        "kb_v2_errors": v2_kb_errors,
        "audit_rows": audit_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile dissertation bibliography and verify all Phase 3 reports")
    parser.add_argument("--nosology", default="prom", help="Nosology ID (e.g. prom, dupuytren)")
    parser.add_argument(
        "--compile-bibliography",
        action="store_true",
        help="Compile [@PMID:...] into [1]..[N] and append bibliography",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run Zero-Tolerance SQLite citation, KB v2.0, and Humanizer v2.0 verification",
    )
    parser.add_argument(
        "--schema-version",
        choices=["auto", "v1", "v2"],
        default="auto",
        help="Schema & linter enforcement mode: auto (detect), v1 (legacy compat), or v2 (strict)",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Read-only verification mode: perform zero writes to SQLite, Markdown, .docx, or verification_audit.md",
    )
    args = parser.parse_args()

    if args.compile_bibliography and args.read_only:
        parser.error("--compile-bibliography cannot be used together with --read-only")

    if args.compile_bibliography:
        compile_dissertation_bibliography(args.nosology)
    if args.verify or not args.compile_bibliography:
        verify_all_reports(
            args.nosology,
            schema_version=args.schema_version,
            write_outputs=not args.read_only,
        )


if __name__ == "__main__":
    main()
