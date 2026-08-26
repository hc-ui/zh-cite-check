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
