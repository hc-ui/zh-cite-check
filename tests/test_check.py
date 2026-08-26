"""Tests for zh-cite-check."""

from __future__ import annotations

import json
from pathlib import Path

from zh_cite_check import check_text
from zh_cite_check.check import render_json, render_text
from zh_cite_check.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"

GOOD = (EXAMPLES / "good.md").read_text(encoding="utf-8")
BAD = (EXAMPLES / "bad.md").read_text(encoding="utf-8")


def _ids(result):
    return [i.rule_id for i in result.issues]


def _by_rule(result, rule_id):
    return [i for i in result.issues if i.rule_id == rule_id]


# --- examples --------------------------------------------------------------

def test_good_paper_is_clean():
    result = check_text(GOOD, source="good.md")
    assert result.error_count == 0
    assert result.warning_count == 0
    assert result.heading_found is True
    assert result.cited == [1, 2, 3, 4]
    assert result.bibliography == [1, 2, 3, 4]


def test_bad_paper_reports_core_errors():
    result = check_text(BAD, source="bad.md")
    ids = set(_ids(result))
    assert "E001" in ids
    assert "E002" in ids
    assert "E003" in ids
    assert "W101" in ids
    assert result.error_count >= 3
    missing = {i.number for i in _by_rule(result, "E001")}
    assert 9 in missing
    unused = {i.number for i in _by_rule(result, "E002")}
    assert 5 in unused


# --- ranges / lists / fullwidth --------------------------------------------

def test_range_2_to_4_expands():
    text = (
        "讨论见[2-4]。\n\n"
        "参考文献\n"
        "[1] A. 题[J]. 刊, 2020.\n"
        "[2] B. 题[M]. 北京: 社, 2019.\n"
        "[3] C. 题[D]. 上海: 校, 2021.\n"
        "[4] D. 题[C]//会议. 2022: 1-8.\n"
    )
    # [2-4] first appearance starts at 2, so W101; 1 unused → E002
    result = check_text("前文[1]。" + text)
    assert result.cited == [1, 2, 3, 4]
    assert result.error_count == 0


def test_comma_list_and_consecutive_brackets():
    text = (
        "见[1,2,5]与[3][4]。\n\n"
        "参考文献\n"
        "[1] A. t[J]. x, 1.\n"
        "[2] B. t[J]. x, 1.\n"
        "[3] C. t[J]. x, 1.\n"
        "[4] D. t[J]. x, 1.\n"
        "[5] E. t[J]. x, 1.\n"
    )
    result = check_text(text)
    assert result.cited == [1, 2, 5, 3, 4]
    assert result.error_count == 0
    assert any(i.rule_id == "W101" for i in result.issues)


def test_lenticular_brackets():
    text = (
        "结论见【1】和【2，3】。\n\n"
        "参考文献\n"
        "【1】 张三. 题[J]. 刊, 2020.\n"
        "[2] 李四. 题[M]. 北京: 社, 2019.\n"
        "[3] 王五. 题[D]. 南京: 校, 2021.\n"
    )
    result = check_text(text)
    assert result.cited == [1, 2, 3]
    assert result.bibliography == [1, 2, 3]
    assert result.error_count == 0


def test_tortoise_shell_brackets():
    text = (
        "结论见〔1〕和〔2，3〕。\n\n"
        "参考文献\n"
        "〔1〕 张三. 题[J]. 刊, 2020.\n"
        "[2] 李四. 题[M]. 北京: 社, 2019.\n"
        "[3] 王五. 题[D]. 南京: 校, 2021.\n"
    )
    result = check_text(text)
    assert result.cited == [1, 2, 3]
    assert result.bibliography == [1, 2, 3]
    assert result.error_count == 0


def test_fullwidth_brackets():
    text = (
        "结论见［1］和［2，3］。\n\n"
        "参考文献\n"
        "［1］ 张三. 题[J]. 刊, 2020.\n"
        "[2] 李四. 题[M]. 北京: 社, 2019.\n"
        "[3] 王五. 题[D]. 南京: 校, 2021.\n"
    )
    result = check_text(text)
    assert result.cited == [1, 2, 3]
    assert result.bibliography == [1, 2, 3]
    assert result.error_count == 0


def test_combined_range_and_comma():
    text = (
        "见[1, 3-5, 8]。\n\n"
        "参考文献\n"
        + "".join(f"[{n}] 作者. 题[J]. 刊, 2020.\n" for n in range(1, 9))
    )
    result = check_text(text)
    assert result.cited == [1, 3, 4, 5, 8]
    unused = {i.number for i in _by_rule(result, "E002")}
    assert unused == {2, 6, 7}


# --- false positives -------------------------------------------------------

def test_markdown_links_ignored():
    text = (
        "参见 [相关工作](https://example.com/1) 与论文[1]。\n"
        "图片 ![图1](./fig1.png) 不是引用。\n\n"
        "参考文献\n"
        "[1] 张三. 题[J]. 刊, 2020.\n"
    )
    result = check_text(text)
    assert result.cited == [1]
    assert result.error_count == 0
    assert not any("example.com" in (i.message or "") for i in result.issues)


def test_markdown_link_that_looks_like_cite_ignored():
    text = (
        "不要把 [1](https://doi.org/10.0/xyz) 当引用，真正的是[2]。\n\n"
        "参考文献\n"
        "[1] A. t[J]. x, 1.\n"
        "[2] B. t[J]. x, 1.\n"
    )
    result = check_text(text)
    assert result.cited == [2]
    unused = {i.number for i in _by_rule(result, "E002")}
    assert unused == {1}


def test_type_markers_ignored_in_bibliography():
    text = (
        "正文引用[1]和[2]。\n\n"
        "参考文献\n"
        "[1] 张三. 题名[J]. 某学报, 2020, 1(1): 1-8.\n"
        "[2] 李四. 书名[M]. 北京: 科学出版社, 2019.\n"
        "    另见电子版[EB/OL]. [2024-05-06]. https://example.com.\n"
    )
    result = check_text(text)
    assert result.cited == [1, 2]
    assert result.bibliography == [1, 2]
    assert result.error_count == 0
    # [J] / [M] / [EB/OL] / date must not become cite numbers or extra bib items
    assert 2024 not in result.cited
    assert "J" not in str(result.cited)


def test_type_marker_in_body_not_a_cite():
    text = (
        "期刊论文的文献类型标识为[J]，专著为[M]，真正引用是[1]。\n\n"
        "参考文献\n"
        "[1] 张三. 题[J]. 刊, 2020.\n"
    )
    result = check_text(text)
    assert result.cited == [1]
    assert result.error_count == 0


def test_fenced_code_not_scanned():
    text = (
        "正文[1]。\n\n"
        "```python\nprint('[2] not a cite')\n```\n\n"
        "参考文献\n"
        "[1] A. t[J]. x, 1.\n"
        "[2] B. t[J]. x, 1.\n"
    )
    result = check_text(text)
    assert result.cited == [1]
    unused = {i.number for i in _by_rule(result, "E002")}
    assert unused == {2}


# --- rules -----------------------------------------------------------------

def test_e001_missing_bibliography_entry():
    text = (
        "见[1]和[3]。\n\n"
        "参考文献\n"
        "[1] A. t[J]. x, 1.\n"
        "[2] B. t[J]. x, 1.\n"
    )
    result = check_text(text)
    e001 = _by_rule(result, "E001")
    assert [i.number for i in e001] == [3]
    assert e001[0].line >= 1


def test_e002_unused_reference():
    text = (
        "只引用[1]。\n\n"
        "参考文献\n"
        "[1] A. t[J]. x, 1.\n"
        "[2] B. t[J]. x, 1.\n"
    )
    result = check_text(text)
    e002 = _by_rule(result, "E002")
    assert [i.number for i in e002] == [2]


def test_e003_gap_and_duplicate():
    text = (
        "见[1][2][4]。\n\n"
        "参考文献\n"
        "[1] A. t[J]. x, 1.\n"
        "[2] B. t[J]. x, 1.\n"
        "[2] C. t[J]. x, 1.\n"
        "[4] D. t[J]. x, 1.\n"
    )
    result = check_text(text)
    e003 = _by_rule(result, "E003")
    assert len(e003) == 1
    msg = e003[0].message
    assert "3" in msg or "缺" in msg
    assert "重复" in msg


def test_e003_does_not_start_at_one():
    text = (
        "见[2]。\n\n"
        "参考文献\n"
        "[2] A. t[J]. x, 1.\n"
        "[3] B. t[J]. x, 1.\n"
    )
    result = check_text(text)
    assert _by_rule(result, "E003")
    assert {i.number for i in _by_rule(result, "E002")} == {3}


def test_w101_out_of_order_first_appearance():
    text = (
        "先写[2]再写[1]。\n\n"
        "参考文献\n"
        "[1] A. t[J]. x, 1.\n"
        "[2] B. t[J]. x, 1.\n"
    )
    result = check_text(text)
    w101 = _by_rule(result, "W101")
    assert len(w101) == 1
    assert result.error_count == 0  # both cited, numbering contiguous


def test_arabic_numbered_heading_is_recognized():
    text = (
        "见[1]。\n\n"
        "1. 参考文献\n"
        "[1] A. t[J]. x, 1.\n"
    )
    result = check_text(text)
    assert result.heading_found is True
    assert result.cited == [1]
    assert result.bibliography == [1]
    assert result.error_count == 0


def test_w102_fallback_without_heading():
    text = (
        "正文引用[1]和[2]。\n\n"
        "[1] 张三. 题[J]. 刊, 2020.\n"
        "[2] 李四. 题[M]. 北京: 社, 2019.\n"
    )
    result = check_text(text)
    assert result.heading_found is False
    w102 = _by_rule(result, "W102")
    assert w102
    assert "文末" in w102[0].message
    assert result.cited == [1, 2]
    assert result.bibliography == [1, 2]
    assert result.error_count == 0


def test_dot_and_ideographic_comma_bib_numbers():
    text = (
        "见[1][2]。\n\n"
        "参考文献\n"
        "1. 张三. 题[J]. 刊, 2020.\n"
        "2、李四. 题[M]. 北京: 社, 2019.\n"
    )
    result = check_text(text)
    assert result.bibliography == [1, 2]
    assert result.error_count == 0


def test_stops_before_acknowledgements():
    text = (
        "见[1]。\n\n"
        "参考文献\n"
        "[1] A. t[J]. x, 1.\n\n"
        "致谢\n"
        "感谢导师[2]的指导。\n"
    )
    result = check_text(text)
    assert result.cited == [1]
    assert result.bibliography == [1]
    # [2] in 致谢 is after the bib heading stop — not in body
    assert result.error_count == 0


def test_no_issues_on_empty():
    result = check_text("")
    assert result.issues == []
    assert result.cited == []
    assert result.bibliography == []


def test_render_json_and_text():
    result = check_text(GOOD, source="good.md")
    dumped = json.loads(render_json(result, "good.md"))
    assert dumped["error_count"] == 0
    assert dumped["cited"] == [1, 2, 3, 4]
    text = render_text(result, "good.md")
    assert "未发现问题" in text
    assert "good.md" in text


# --- CLI -------------------------------------------------------------------

def test_cli_good_example_exit_zero(capsys):
    code = main([str(EXAMPLES / "good.md")])
    captured = capsys.readouterr()
    assert code == 0
    assert "未发现问题" in captured.out


def test_cli_bad_example_exit_one(capsys):
    code = main([str(EXAMPLES / "bad.md")])
    captured = capsys.readouterr()
    assert code == 1
    assert "E001" in captured.out
    assert "E002" in captured.out


def test_cli_json_flag(capsys):
    code = main([str(EXAMPLES / "good.md"), "--json"])
    captured = capsys.readouterr()
    assert code == 0
    data = json.loads(captured.out)
    assert data["error_count"] == 0
    assert data["bibliography"] == [1, 2, 3, 4]


def test_cli_stdin(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin.buffer.read", lambda: GOOD.encode("utf-8")
    )
    code = main(["-"])
    capsys.readouterr()
    assert code == 0


def test_cli_missing_file():
    code = main(["/nonexistent/zh-cite-check-nope.md"])
    assert code == 2


def test_read_clipboard_tries_wayland_tools(monkeypatch):
    import subprocess

    from zh_cite_check.cli import _read_clipboard

    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        if command[0] == "wl-paste":
            completed = subprocess.CompletedProcess(command, 0, stdout=b"ok", stderr=b"")
            return completed
        raise OSError("missing")

    monkeypatch.setattr("zh_cite_check.cli.sys.platform", "linux")
    monkeypatch.setattr("zh_cite_check.cli.subprocess.run", fake_run)
    assert _read_clipboard() == "ok"
    assert ["wl-paste"] in calls


def test_cli_clip(monkeypatch, capsys):
    monkeypatch.setattr("zh_cite_check.cli._read_clipboard", lambda: GOOD)
    code = main(["--clip"])
    captured = capsys.readouterr()
    assert code == 0
    assert "未发现问题" in captured.out


def test_cli_requires_input_or_clip():
    import pytest

    with pytest.raises(SystemExit):
        main([])


def test_cli_empty_clipboard(monkeypatch, capsys):
    monkeypatch.setattr("zh_cite_check.cli._read_clipboard", lambda: "\n")
    assert main(["--clip"]) == 2
    assert "空" in capsys.readouterr().err
