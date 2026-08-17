"""Command-line interface: ``zh-cite-check thesis.md [--json]``."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import __version__
from .check import check_text, render_json, render_text


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _read_clipboard() -> str:
    if sys.platform == "win32":
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-Clipboard -Raw",
            ],
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            err = _decode(completed.stderr).strip() or "Get-Clipboard failed"
            raise OSError(err)
        return _decode(completed.stdout)
    for command in (["pbpaste"], ["xclip", "-selection", "clipboard", "-o"]):
        try:
            completed = subprocess.run(command, capture_output=True, check=False)
        except OSError:
            continue
        if completed.returncode == 0:
            return _decode(completed.stdout)
    raise OSError("clipboard is not available on this system")


def _read_input(path_arg: str) -> tuple[str, str]:
    """Return (text, source_name); tolerate Windows GBK files."""
    if path_arg == "-":
        data = sys.stdin.buffer.read()
        return _decode(data), "-"
    path = Path(path_arg)
    return _decode(path.read_bytes()), str(path)


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
        epilog="示例：zh-cite-check thesis.md    zh-cite-check --clip    zh-cite-check -",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="论文文本文件路径（Markdown / 纯文本），使用 - 从标准输入读取",
    )
    parser.add_argument(
        "--clip",
        action="store_true",
        help="从系统剪贴板读取（适合从 Word 复制后直接检查）",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出检查结果")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    if args.clip:
        try:
            text, source_name = _read_clipboard(), "<clipboard>"
        except OSError as exc:
            print(f"无法读取剪贴板：{exc}", file=sys.stderr)
            return 2
    elif args.input:
        try:
            text, source_name = _read_input(args.input)
        except OSError as exc:
            print(f"无法读取输入：{exc}", file=sys.stderr)
            return 2
    else:
        parser.error("请提供论文文件，或使用 --clip / -")

    if not text.strip():
        print("没有可检查的文本（文件或剪贴板是空的）。", file=sys.stderr)
        return 2

    result = check_text(text, source=source_name)
    print(render_json(result, source_name) if args.json else render_text(result, source_name))
    return 1 if result.error_count else 0


if __name__ == "__main__":
    sys.exit(main())
