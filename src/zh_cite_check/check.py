"""Match in-text citation numbers against a numbered bibliography.

Designed for Chinese / mixed-language theses that use sequential numeric
citations (顺序编码制): ``[1]``, ``[1,2,5]``, ``[1-3]``, fullwidth ``［1］``,
and a ``参考文献`` list. Zero third-party dependencies.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Sequence, Tuple

# --- public models ---------------------------------------------------------

@dataclass(frozen=True)
class Issue:
    """A single checker finding."""

    rule_id: str
    severity: str  # "error" | "warning"
    message: str
    line: int = 0  # 1-based; 0 = document-level
    column: int = 0  # 1-based
    number: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CheckResult:
    """Outcome of :func:`check_text`."""

    issues: List[Issue] = field(default_factory=list)
    cited: List[int] = field(default_factory=list)
    bibliography: List[int] = field(default_factory=list)
    heading_found: bool = False
    source: str = ""

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "cited": self.cited,
            "bibliography": self.bibliography,
            "heading_found": self.heading_found,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [i.to_dict() for i in self.issues],
        }


# --- constants / regexes ---------------------------------------------------

_FW_TABLE = str.maketrans(
    "０１２３４５６７８９，．－—–～",
    "0123456789,.-~~-",
)

# GB/T 7714 document-type / carrier markers must never be treated as cites.
_TYPE_MARKERS = frozenset(
    {
        "J", "M", "D", "C", "N", "R", "S", "P", "Z", "G", "A",
        "PP", "DS", "DB", "CP", "EB", "OL", "PK", "ST", "MM",
        "J/OL", "M/OL", "D/OL", "C/OL", "N/OL", "R/OL", "S/OL",
        "DB/OL", "CP/OL", "EB/OL", "J/CD", "M/CD", "DB/CD", "CP/CD",
        "C/CD", "S/CD",
    }
)

_HEADING_RE = re.compile(
    r"""
    ^\s{0,3}
    (?:\#{1,6}\s+)?
    (?:\d+[.\uff0e\u3001]\s*)?
    (?:[（(]?\s*[一二三四五六七八九十0-9]+\s*[）)]\s*)?
    (?:\*{1,2}|_{1,2})?
    (参考文献|参考书目|引用文献|参考资料|References|Bibliography|Works\s+Cited)
    (?:\*{1,2}|_{1,2})?
    \s*[:：]?
    (?:\s*\{\#[^}]+\})?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

_STOP_HEADING_RE = re.compile(
    r"""
    ^\s{0,3}
    (?:\#{1,6}\s+)?
    (?:\*{1,2}|_{1,2})?
    (致谢|謝誌|鸣谢|鳴謝|附录|附錄|Acknowledgements?|Acknowledgments?|
     Appendix|Appendices|攻读学位期间|发表的学术论文|作者简介)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# [1]  [1].  ［1］  【1】  then optional punct and some entry text
_BIB_BRACKET_RE = re.compile(
    r"^(\s*)[\[［【〔]\s*(\d{1,3})\s*[\]］】〕]\s*[.\uff0e、]?\s*\S"
)
# 1.  1、  1．  (space required after ASCII period to avoid "1.5")
_BIB_DOT_RE = re.compile(r"^(\s*)(\d{1,3})\s*(?:[、．]|\.\s)\s*\S")

_DATE_RE = re.compile(r"^\d{4}[-./]\d{1,2}[-./]\d{1,2}$")

# Inner of a numeric cite: 1 / 1,2,5 / 1-3 / 1, 2-4, 7
_CITE_INNER_RE = re.compile(
    r"^\d+(?:\s*[,，、]\s*\d+|\s*[-–—~～－]\s*\d+)*$"
)

_BRACKET_RE = re.compile(r"[\[［【〔]([^\[［【〔\]］】〕]{0,80})[\]］】〕]")

_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_MD_LINK_RE = re.compile(
    r"!?\[(?:[^\]]|\n)*?\]\([^)]*\)",
    re.MULTILINE,
)
_MD_DEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s+\S", re.MULTILINE)

_MAX_CITE = 999


# --- helpers ---------------------------------------------------------------

def _norm(s: str) -> str:
    return s.translate(_FW_TABLE)


def _mask_keep_newlines(text: str, start: int, end: int) -> str:
    chunk = text[start:end]
    masked = "".join("\n" if ch == "\n" else " " for ch in chunk)
    return text[:start] + masked + text[end:]


def _mask_fenced_code(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: List[str] = []
    fence: Optional[str] = None
    for line in lines:
        stripped = line.lstrip()
        m = _FENCE_RE.match(stripped)
        if fence is None:
            if m:
                fence = m.group(1)[0]
                out.append("\n" if line.endswith("\n") else "")
            else:
                out.append(line)
        else:
            out.append("".join("\n" if c == "\n" else " " for c in line))
            if m and m.group(1)[0] == fence:
                fence = None
    return "".join(out)


def _mask_matches(text: str, pattern: re.Pattern) -> str:
    for m in reversed(list(pattern.finditer(text))):
        text = _mask_keep_newlines(text, m.start(), m.end())
    return text


def _mask_non_cite_noise(text: str) -> str:
    """Blank out markdown constructs that are not in-text citations."""
    text = _mask_fenced_code(text)
    text = _mask_matches(text, _MD_LINK_RE)
    text = _mask_matches(text, _MD_DEF_RE)
    text = _mask_matches(text, _INLINE_CODE_RE)
    return text


def _line_col(text: str, index: int) -> Tuple[int, int]:
    """1-based line and column for a 0-based string index."""
    line = text.count("\n", 0, index) + 1
    last_nl = text.rfind("\n", 0, index)
    col = index + 1 if last_nl < 0 else index - last_nl
    return line, col


def _looks_like_heading(line: str) -> bool:
    return bool(_HEADING_RE.match(line.strip()) or _STOP_HEADING_RE.match(line.strip()))


def _bib_start_num(line: str) -> Optional[Tuple[int, int]]:
    """If *line* opens a bibliography item, return (number, column)."""
    raw = line.rstrip("\n")
    m = _BIB_BRACKET_RE.match(raw)
    if m:
        return int(m.group(2)), len(m.group(1)) + 1
    m = _BIB_DOT_RE.match(raw)
    if m:
        return int(m.group(2)), len(m.group(1)) + 1
    return None


def _find_heading(lines: Sequence[str]) -> Optional[int]:
    for i, line in enumerate(lines):
        if _HEADING_RE.match(line.strip()):
            return i
    return None


def _find_stop(lines: Sequence[str], start: int) -> int:
    for i in range(start, len(lines)):
        if _STOP_HEADING_RE.match(lines[i].strip()):
            return i
    return len(lines)


def _iter_bib_blocks(lines: Sequence[str]) -> List[Tuple[int, int]]:
    """Inclusive-start, exclusive-end blocks of consecutive bib entries."""
    blocks: List[Tuple[int, int]] = []
    n = len(lines)
    i = 0
    while i < n:
        if _bib_start_num(lines[i]) is None:
            i += 1
            continue
        start = i
        i += 1
        while i < n:
            if _bib_start_num(lines[i]) is not None:
                i += 1
                continue
            if _looks_like_heading(lines[i]):
                break
            if not lines[i].strip():
                k = i + 1
                while k < n and not lines[k].strip():
                    k += 1
                if k < n and (
                    _bib_start_num(lines[k]) is not None
                    or (lines[k].strip() and not _looks_like_heading(lines[k]))
                ):
                    i = k
                    continue
                break
            # continuation of the current entry
            i += 1
        blocks.append((start, i))
    return blocks


def _locate_bibliography(
    lines: Sequence[str],
) -> Tuple[int, int, bool]:
    """Return (start, end, heading_found) as half-open line indices.

    ``(-1, -1, False)`` means no bibliography was found.
    """
    heading = _find_heading(lines)
    if heading is not None:
        start = heading + 1
        end = _find_stop(lines, start)
        return start, end, True

    blocks = _iter_bib_blocks(lines)
    if not blocks:
        return -1, -1, False

    start, end = blocks[-1]
    last_content = max(
        (i for i, ln in enumerate(lines) if ln.strip()),
        default=0,
    )
    # Trailing run: ends near EOF, or sits in the latter half of the file.
    near_end = end >= last_content - 25
    latter_half = start >= max(len(lines) // 2, 1)
    if near_end or latter_half:
        return start, end, False
    return -1, -1, False


def _parse_bibliography(
    lines: Sequence[str], start: int, end: int
) -> List[Tuple[int, int, int]]:
    """Return list of (number, line_1based, column)."""
    entries: List[Tuple[int, int, int]] = []
    if start < 0:
        return entries
    for i in range(start, min(end, len(lines))):
        found = _bib_start_num(lines[i])
        if found is None:
            continue
        num, col = found
        entries.append((num, i + 1, col))
    return entries


def _parse_cite_inner(inner: str) -> Optional[List[int]]:
    """Parse ``1,2,5`` / ``1-3`` / ``1, 2-4``. ``None`` = not a citation."""
    inner = _norm(inner).strip()
    if not inner:
        return None
    compact = inner.replace(" ", "")
    if compact.upper() in _TYPE_MARKERS:
        return None
    if _DATE_RE.match(compact):
        return None
    if not _CITE_INNER_RE.match(inner):
        return None

    numbers: List[int] = []
    for part in re.split(r"[,，、]", inner):
        part = part.strip()
        if not part:
            continue
        if re.search(r"[-–—~～－]", part):
            bits = re.split(r"[-–—~～－]", part, maxsplit=1)
            try:
                lo, hi = int(bits[0].strip()), int(bits[1].strip())
            except (TypeError, ValueError):
                return None
            if lo < 1 or hi < 1 or lo > _MAX_CITE or hi > _MAX_CITE:
                return None
            if lo > hi:
                numbers.extend([lo, hi])
            elif hi - lo > 500:
                numbers.extend([lo, hi])
            else:
                numbers.extend(range(lo, hi + 1))
        else:
            try:
                n = int(part)
            except ValueError:
                return None
            if n < 1 or n > _MAX_CITE:
                return None
            numbers.append(n)
    return numbers or None


@dataclass(frozen=True)
class _Cite:
    numbers: Tuple[int, ...]
    line: int
    column: int
    raw: str


def _extract_citations(body: str) -> List[_Cite]:
    """Collect numeric square-bracket citations from the paper body."""
    masked = _mask_non_cite_noise(body)
    cites: List[_Cite] = []
    prev_end = -1
    prev_was_non_cite = False

    for m in _BRACKET_RE.finditer(masked):
        inner = m.group(1)
        nums = _parse_cite_inner(inner)
        # ``[text][1]`` markdown reference: skip the numeric half.
        adjacent_ref = prev_was_non_cite and m.start() == prev_end
        if nums is None:
            prev_end = m.end()
            prev_was_non_cite = True
            continue
        if adjacent_ref:
            prev_end = m.end()
            prev_was_non_cite = False
            continue
        line, col = _line_col(body, m.start())
        raw = body[m.start() : m.end()]
        cites.append(_Cite(tuple(nums), line, col, raw))
        prev_end = m.end()
        prev_was_non_cite = False
    return cites


# --- checker ---------------------------------------------------------------

def check_text(text: str, source: str = "") -> CheckResult:
    """Check that in-text citation numbers match the numbered bibliography."""
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    start, end, heading_found = _locate_bibliography(lines)
    entries = _parse_bibliography(lines, start, end)
    bib_nums = [n for n, _, _ in entries]
    bib_set = set(bib_nums)

    if start >= 0:
        body = "\n".join(lines[:start])
    else:
        body = text

    cites = _extract_citations(body)
    cited_ordered: List[int] = []
    seen_cite = set()
    for c in cites:
        for n in c.numbers:
            if n not in seen_cite:
                seen_cite.add(n)
                cited_ordered.append(n)

    issues: List[Issue] = []

    if not heading_found and start >= 0:
        issues.append(
            Issue(
                rule_id="W102",
                severity="warning",
                message=(
                    "未找到「参考文献 / References」标题，"
                    "已将尚未连续编号行视为参考文献表"
                ),
                line=start + 1,
            )
        )

    # E001: cited number missing from bibliography (first occurrence only)
    seen_e001 = set()
    for c in cites:
        for n in c.numbers:
            if n not in bib_set and n not in seen_e001:
                seen_e001.add(n)
                issues.append(
                    Issue(
                        rule_id="E001",
                        severity="error",
                        message=f"文中引用 [{n}]，参考文献中无对应条目",
                        line=c.line,
                        column=c.column,
                        number=n,
                    )
                )

    # E002: bibliography entry never cited
    cited_set = set(cited_ordered)
    for n, ln, col in entries:
        if n not in cited_set:
            issues.append(
                Issue(
                    rule_id="E002",
                    severity="error",
                    message=f"参考文献 [{n}] 从未在正文中被引用",
                    line=ln,
                    column=col,
                    number=n,
                )
            )

    # E003: numbers not contiguous from 1 (gap / duplicate / not starting at 1)
    if bib_nums:
        unique_sorted = sorted(set(bib_nums))
        expected = list(range(1, unique_sorted[-1] + 1))
        missing = [k for k in expected if k not in bib_set]
        dupes = sorted({k for k in bib_nums if bib_nums.count(k) > 1})
        parts: List[str] = []
        shown = "、".join(f"[{k}]" for k in bib_nums)
        if unique_sorted != expected or dupes or bib_nums != unique_sorted:
            if missing:
                parts.append("缺 " + "、".join(f"[{k}]" for k in missing))
            if dupes:
                parts.append("重复 " + "、".join(f"[{k}]" for k in dupes))
            if unique_sorted[0] != 1 and not missing:
                parts.append("未从 [1] 起编")
            if not parts:
                # order is not 1..n even if the set is correct
                parts.append("未按 1, 2, 3… 顺序排列")
            issues.append(
                Issue(
                    rule_id="E003",
                    severity="error",
                    message=(
                        f"参考文献序号不连续或重复：现有 {shown}"
                        + (f"（{'；'.join(parts)}）" if parts else "")
                    ),
                    line=entries[0][1],
                    column=entries[0][2],
                )
            )

    # W101: first in-text appearance is not 1, 2, 3, …
    first_pos = {}
    for c in cites:
        for n in c.numbers:
            if n not in first_pos:
                first_pos[n] = (c.line, c.column, c.raw)
    expected_next = 1
    for n in cited_ordered:
        if n != expected_next:
            ln, col, _raw = first_pos[n]
            issues.append(
                Issue(
                    rule_id="W101",
                    severity="warning",
                    message=(
                        "正文首次出现的引用序号不是按递增顺序（顺序编码制）："
                        f"第 {ln} 行首次出现 [{n}]，此时尚未按序出现 [{expected_next}]。"
                        "实际首次出现顺序为 "
                        + ", ".join(str(x) for x in cited_ordered)
                    ),
                    line=ln,
                    column=col,
                    number=n,
                )
            )
            break
        expected_next += 1

    issues.sort(key=lambda i: (i.line or 0, i.column or 0, i.rule_id))
    return CheckResult(
        issues=issues,
        cited=cited_ordered,
        bibliography=bib_nums,
        heading_found=heading_found,
        source=source,
    )


def render_text(result: CheckResult, source: str = "") -> str:
    """Human-readable report (Chinese), matching gbt7714-lint style."""
    name = source or result.source or "(stdin)"
    n_cite = len(result.cited)
    n_bib = len(result.bibliography)
    lines = [f"检查 {name}：正文引用 {n_cite} 个编号，参考文献 {n_bib} 条"]
    if not result.issues:
        lines.append("  未发现问题。")
    else:
        for iss in result.issues:
            loc = f"第{iss.line}行 " if iss.line else ""
            if iss.column:
                loc = f"第{iss.line}行第{iss.column}列 "
            label = "错误" if iss.severity == "error" else "警告"
            lines.append(f"  {loc}[{iss.rule_id}] {label}：{iss.message}")
    lines.append(
        f"合计：{result.error_count} 个错误，{result.warning_count} 个警告"
    )
    return "\n".join(lines)


def render_json(result: CheckResult, source: str = "") -> str:
    data = result.to_dict()
    if source:
        data["source"] = source
    return json.dumps(data, ensure_ascii=False, indent=2)
