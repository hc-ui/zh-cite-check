from zh_cite_check import check_text


def test_chapter_heading_and_paren_bib_numbers():
    text = (
        "结论见[1]和[2]。\n\n"
        "第六章 参考文献\n"
        "（1） 张三. 题[J]. 刊, 2020.\n"
        "(2) 李四. 题[M]. 北京: 社, 2019.\n"
    )
    result = check_text(text)
    assert result.heading_found is True
    assert result.cited == [1, 2]
    assert result.bibliography == [1, 2]
    assert result.error_count == 0
    assert not any(i.rule_id == "W102" for i in result.issues)


def test_arabic_chapter_heading():
    result = check_text(
        "结论见[1]。\n\n第6章 参考文献\n（1） 张三. 题[J]. 刊, 2020.\n"
    )
    assert result.heading_found is True
    assert result.bibliography == [1]
    assert result.error_count == 0
