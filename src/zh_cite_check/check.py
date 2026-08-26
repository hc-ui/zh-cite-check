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
    (?:第\s*[一二三四五六七八九十百零〇0-9]+\s*[章节節篇]\s*)?
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
# （1）  (1)  （1）.  — common in thesis bibliographies; not used for in-text cites
_BIB_PAREN_RE = re.compile(r"^(\s*)[（(]\s*(\d{1,3})\s*[）)]\s*[.\uff0e、]?\s*\S")

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
