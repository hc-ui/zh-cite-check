"""zh-cite-check: match in-text citation numbers to a numbered bibliography."""

from .check import CheckResult, Issue, check_text

__version__ = "0.1.3"

__all__ = ["check_text", "CheckResult", "Issue", "__version__"]
