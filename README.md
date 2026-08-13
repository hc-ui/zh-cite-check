# zh-cite-check

[![CI](https://github.com/hc-ui/zh-cite-check/actions/workflows/ci.yml/badge.svg)](https://github.com/hc-ui/zh-cite-check/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://github.com/hc-ui/zh-cite-check)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**检查中文学术论文正文引用序号与参考文献表是否一一对应。**

A zero-dependency checker for sequential numeric citations (`[1]`, `[1-3]`, `［1］`, …) in Chinese and mixed-language papers. Paste a thesis chapter, get a rule-by-rule report: every in-text number must exist in the list, every list item must be cited, and the numbering must be contiguous from 1.

与 [gbt7714-lint](https://github.com/hc-ui/gbt7714-lint) **互补**：那个工具查 GB/T 7714 **著录格式**，本工具查 **序号是否对得上**。学位论文交付前两条流水线一起跑，格式和索引各管各的。
