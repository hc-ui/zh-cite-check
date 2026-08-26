# zh-cite-check

[![CI](https://github.com/hc-ui/zh-cite-check/actions/workflows/ci.yml/badge.svg)](https://github.com/hc-ui/zh-cite-check/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://github.com/hc-ui/zh-cite-check)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

正文写着 `[7]`，参考文献表里却没有第 7 条？这个工具查的就是这件事。

粘一篇论文进去：每个正文序号都得在表里，每条文献都得被引用过，编号还得从 1 连着。零依赖。

和 [gbt7714-lint](https://github.com/hc-ui/gbt7714-lint) 互补：那个查 **GB/T 7714 怎么写**，这个查 **序号对不对**。交论文前两条一起跑。

English: sequential citation checker for `[1]` / `[1-3]` — unused, missing, and out-of-order numbers.

## 为什么需要它

高校论文和期刊投稿普遍采用 GB/T 7714 **顺序编码制**：正文用 `[1]`、`[1,2,5]`、`[1-3]` 引用，文末 `参考文献` 按出现顺序编号。Word / Markdown 里改段落、删文献、合并章节之后，最常见的事故不是格式细节，而是：

- 正文还写着 `[7]`，参考文献表已经没有第 7 条
- 表里留着从未被引用的条目（导师一眼能看出来）
- `[1] [2] [4]` 跳号，或两条都标成 `[3]`
- 正文第一次出现的序号不是 1、2、3…（和表的排列不一致）

`gbt7714-lint` 解决「这一条怎么著录」；`zh-cite-check` 解决「正文和表是不是同一套编号」。两者都是纯文本、零依赖、可进 CI。

## 安装

```bash
pip install git+https://github.com/hc-ui/zh-cite-check.git
```

无第三方依赖，Python 3.9+。尚未上 PyPI，请从 Git 安装。开发：

```bash
pip install -e ".[dev]"
pytest
```

## 使用

```bash
# 检查一篇 Markdown / 纯文本论文
zh-cite-check thesis.md

# 从 Word 复制后直接检查剪贴板
zh-cite-check --clip

# 机器可读输出（供脚本 / CI 使用）
zh-cite-check thesis.md --json

# 从管道读取
zh-cite-check - < thesis.md
Get-Clipboard | zh-cite-check -      # PowerShell
pbpaste | zh-cite-check -            # macOS
```

存在 **错误**（E 类）时退出码为 1；仅有警告时为 0。

检查输出示例：

```text
检查 thesis.md：正文引用 4 个编号，参考文献 3 条
  第3行第12列 [E001] 错误：文中引用 [9]，参考文献中无对应条目
  第12行 [E002] 错误：参考文献 [5] 从未在正文中被引用
  第10行 [E003] 错误：参考文献序号不连续或重复：现有 [1]、[2]、[5]（缺 [3]、[4]）
  第1行 [W101] 警告：正文首次出现的引用序号不是按递增顺序（顺序编码制）
合计：3 个错误，1 个警告
```

也可以作为 Python 库调用：

```python
from zh_cite_check import check_text

result = check_text(open("thesis.md", encoding="utf-8").read())
for issue in result.issues:
    print(issue.rule_id, issue.line, issue.message)
# result.error_count / result.warning_count
# result.cited  → 正文首次出现顺序
# result.bibliography → 表中的序号（含重复）
```

## 识别范围

**正文引用**

| 写法 | 示例 | 展开为 |
|------|------|--------|
| 单个 | `[1]`、`［1］`（全角括号）、`【1】` | 1 |
| 连写 | `[1][2]` | 1, 2 |
| 逗号列表 | `[1,2,5]`、`[1, 2, 5]`、`[1，2]` | 1, 2, 5 |
| 范围 | `[1-3]`、`[2-4]`、`[1–3]` | 1, 2, 3 / 2, 3, 4 |
| 组合 | `[1, 3-5, 8]` | 1, 3, 4, 5, 8 |

为避免把 `(1) 首先……` 这类列举当成引用，**只认方括号**，不认圆括号 `（1）`。

**故意忽略**

- Markdown 链接 `[说明](https://example.com)`、图片、参考式链接、链接定义、围栏/行内代码
- GB/T 7714 文献类型 / 载体标识：`[J]` `[M]` `[D]` `[EB/OL]` `[J/OL]` 等
- 看起来像日期的方括号 `[2024-05-06]`

**参考文献表**

1. 定位标题行：`参考文献` / `参考书目` / `引用文献` / `References` / `Bibliography`（允许 Markdown 标题与加粗）。其后直到 `致谢` / `附录` / `Acknowledgements` 等节为表。
2. 若没有标题，则把**文末连续编号行**当作表，并给出 W102。
3. 条目开头支持 `[1]`、`[1].`、`1.`、`1、`。

## 规则一览

| 规则 | 级别 | 说明 |
|------|------|------|
| E001 | 错误 | 正文引用的序号在参考文献表中没有对应条目 |
| E002 | 错误 | 参考文献表中的条目从未在正文中被引用 |
| E003 | 错误 | 参考文献序号不从 1 连续编号（缺号、重复、未按序） |
| W101 | 警告 | 正文中各序号的**首次出现**不是 1, 2, 3…（顺序编码制） |
| W102 | 警告 | 未找到参考文献标题，已使用文末连续编号行作为回退 |

## Features (English)

- **Index, not format.** Companion to [gbt7714-lint](https://github.com/hc-ui/gbt7714-lint): that linter checks GB/T 7714—2025 *punctuation and fields*; this one checks that citation *numbers* in the body and the list actually match.
- **Real parser.** Ranges, comma lists, consecutive `[1][2]`, fullwidth brackets, UTF-8 and GBK files. Not a toy regex over the whole file.
- **Low false positives.** Markdown links, fenced code, and GB/T document-type markers (`[J]`, `[M]`, `[EB/OL]`) are not citations. Round-bracket enumerations are ignored on purpose.
- **Zero dependencies.** Pure standard library, Python 3.9+, offline.
- **Scriptable.** `--json` and exit code `1` when errors remain, for CI and editor integrations.

## 局限与说明

- 本工具核验**序号对应关系**，不核验文献是否真实存在，也不检查著录格式（格式请用 [gbt7714-lint](https://github.com/hc-ui/gbt7714-lint)）。
- 作者-年份制 `(Zhang, 2023)` 不在范围内。
- 解析器面向学位论文常见 Markdown / 纯文本形态；遇到误报或漏报，欢迎[提 issue](https://github.com/hc-ui/zh-cite-check/issues) 并附上片段。

## 贡献

欢迎 issue 与 PR。跑测试：

```bash
pip install -e ".[dev]"
pytest
```

## License

[MIT](LICENSE)
