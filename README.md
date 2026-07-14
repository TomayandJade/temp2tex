# temp2tex

## English

### Overview

`temp2tex` is a Codex skill for rebuilding an editable LaTeX journal template
from an official Word author template and related publisher guidance.

It is intended for `.doc`, `.docx`, `.docm`, `.dot`, `.dotx`, and `.dotm`
templates. Supporting evidence may include author instructions, sample PDFs,
reference rules, artwork requirements, and official website assets.

The default result is a class-based, Overleaf-ready package built around
`journal-template.cls` and `main.tex`.

### Capabilities

- Inspect Word styles, section geometry, headers, footers, tables, figures,
  captions, notes, references, and appendices.
- Reconstruct title pages, author and affiliation blocks, abstracts, keywords,
  hierarchical headings, body text, floats, citations, and bibliography rules.
- Apply conservative Chinese or English defaults when official requirements are
  incomplete, and record each inferred decision separately from source facts.
- Produce an editable LaTeX package instead of a flattened PDF or one-off
  manuscript conversion.
- Use optional rendering and PDF comparison tools when they are available.

### Installation

Install the source directory by placing `temp2tex/` at:

```text
<CODEX_HOME>/skills/temp2tex/
```

The directory must contain `SKILL.md` at its root. Start a new Codex session
after installation so the skill can be discovered.

Alternatively, download `temp2tex-v0.1.0.skill` from the
[v0.1.0 release](https://github.com/Tomay-hedondism/temp2tex/releases/tag/v0.1.0)
and extract it into the same location.

### Typical Use

Provide the official Word template and any available journal instructions, then
ask Codex to use the skill. For example:

```text
使用 $temp2tex 将这个期刊官方 DOCX 模板转换为可编辑的 LaTeX 模板包。
保留有来源依据的页面版式、前置信息、标题、表格、图片、注释、参考文献和附录。
对于缺失要求，请将其记录为默认值或格式缺口，而不是将其视为官方规则。
```

### Deliverables

A normal conversion produces the following editable package structure:

```text
main.tex
journal-template.cls
references.bib
figures/
assets/
template_spec.json
format_gap_log.md
README.md
```

When rendering is available, the package may also include a PDF comparison
report, layout profile, and visual diff previews.

### Evidence and Verification

Official publisher material takes precedence over inferred formatting. The
skill records source-backed rules, conservative defaults, and unresolved gaps
in separate artifacts so that the resulting template remains reviewable.

PDF comparison is an optional verification step. Missing Word, LaTeX, PDF, or
rendering tools must be reported as a verification limitation; they do not
prevent delivery of an editable, evidence-backed LaTeX package.

### Limitations

Publisher templates can contain incomplete instructions, proprietary fonts,
embedded objects, or Word-only layout behavior. Exact visual equivalence may
therefore require source inspection and local rendering on the target system.

This repository excludes publisher-owned source archives, downloaded corpus
files, and generated regression workspaces. Those materials must be obtained
and handled according to the relevant publisher terms.

### License

This project is licensed under the [Apache License 2.0](LICENSE).

---

## 中文

### 概述

`temp2tex` 是一个 Codex skill，用于依据期刊官方 Word 投稿模板及相关作者指南，重建可编辑的 LaTeX 期刊模板。

它适用于 `.doc`、`.docx`、`.docm`、`.dot`、`.dotx` 和 `.dotm` 模板。辅助证据可以包括作者指南、样刊 PDF、参考文献规则、图片规范和官网素材。

默认交付为适配 Overleaf 的类文件结构，以 `journal-template.cls` 和 `main.tex` 为核心。

### 能力范围

- 检查 Word 样式、分节版式、页眉页脚、表格、图片、题注、注释、参考文献和附录。
- 重建标题页、作者与单位信息、摘要、关键词、多级标题、正文、浮动体、引用和参考文献格式。
- 当官方要求不完整时，采用保守的中文或英文默认格式，并将推断结果与官方证据分开记录。
- 产出可继续维护的 LaTeX 模板包，而不是扁平化 PDF 或一次性的稿件转换结果。
- 在工具可用时执行渲染和 PDF 对比验证。

### 安装

将源目录 `temp2tex/` 放入以下位置：

```text
<CODEX_HOME>/skills/temp2tex/
```

该目录根部必须包含 `SKILL.md`。安装后请新建一个 Codex 会话，使系统发现该 skill。

也可以从 [v0.1.0 release](https://github.com/Tomay-hedondism/temp2tex/releases/tag/v0.1.0)
下载 `temp2tex-v0.1.0.skill`，并解压到相同位置。

### 典型用法

提供期刊官方 Word 模板及可获得的投稿指南，再要求 Codex 使用该 skill。例如：

```text
Use $temp2tex to convert this official journal DOCX template into an editable
LaTeX package. Preserve the source-backed page layout, front matter, headings,
tables, figures, notes, references, and appendices. Record missing requirements
as defaults or gaps rather than treating them as official rules.
```

### 交付物

一次常规转换会生成以下可编辑模板包结构：

```text
main.tex
journal-template.cls
references.bib
figures/
assets/
template_spec.json
format_gap_log.md
README.md
```

如果具备渲染条件，交付物还可以包含 PDF 对比报告、版式分析结果和视觉差异预览图。

### 证据与验证

官方出版社材料优先于推断出的格式。skill 会将有来源的规则、保守默认值和未解决的缺口分别记录，使模板能够被复核和维护。

PDF 对比是可选的验证步骤。缺少 Word、LaTeX、PDF 或渲染工具时，应记录验证限制，但不应阻止交付可编辑且有证据支撑的 LaTeX 模板包。

### 限制

期刊模板可能存在说明不完整、专有字体、嵌入对象或仅能在 Word 中实现的版式行为。要实现严格视觉一致，可能需要进一步检查源文件，并在目标环境中渲染验证。

本仓库不包含出版社拥有的模板源文件、下载语料或生成的回归工作区。相关材料应由使用者自行取得，并遵循出版社的适用条款。

### 许可证

本项目采用 [Apache License 2.0](LICENSE) 发布。
