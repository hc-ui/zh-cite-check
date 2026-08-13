"""Command-line interface: ``zh-cite-check thesis.md [--json]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .check import check_text, render_json, render_text


def _read_input(path_arg: str) -> tuple[str, str]:
    """Return (text, source_name); tolerate Windows GBK files."""
    if path_arg == "-":
        data = sys.stdin.buffer.read()
        for encoding in ("utf-8-sig", "gbk"):
            try:
                return data.decode(encoding), "-"
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace"), "-"
    path = Path(path_arg)
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return data.decode(encoding), str(path)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), str(path)


def main(argv: list[str] | None = None) -> int:
    # Chinese messages must not crash on non-UTF-8 consoles (e.g. cp437)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError):
            pass

    parser = argparse.ArgumentParser(
        prog="zh-cite-check",
        description=(
            "检查中文/中英文学术论文正文中的引用序号（[1]、[1-3]、［1］等）"
            "是否与参考文献表一一对应。"
        ),
        epilog="示例：zh-cite-check thesis.md    zh-cite-check thesis.md --json    zh-cite-check -",
    )
    parser.add_argument(
        "input",
        help="论文文本文件路径（Markdown / 纯文本），使用 - 从标准输入读取",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出检查结果")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    try:
        text, source_name = _read_input(args.input)
    except OSError as exc:
        print(f"无法读取输入：{exc}", file=sys.stderr)
        return 2

    result = check_text(text, source=source_name)
    print(render_json(result, source_name) if args.json else render_text(result, source_name))
    return 1 if result.error_count else 0


if __name__ == "__main__":
    sys.exit(main())
