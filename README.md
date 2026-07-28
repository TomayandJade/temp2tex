# temp2tex

## English

### Overview

`temp2tex` is a Codex skill for rebuilding an editable LaTeX journal-template
package from an official non-LaTeX author template, especially a Microsoft
Word template, together with available publisher guidance.

The skill guides an agent through evidence-led reconstruction. Its default
output is a maintainable package centred on `journal-template.cls` and
`main.tex`, with source evidence, recorded defaults, and unresolved gaps kept
separate from publisher requirements.

### Capabilities

- Inspect `.doc`, `.docx`, `.docm`, `.dot`, `.dotx`, `.dotm`, and `.rtf`
  templates, including paragraph/run formatting, tables, notes, headers,
  footers, drawings, styles, and page settings.
- Reconstruct title pages, author and affiliation blocks, abstracts, keywords,
  headings, body text, equations, figures, tables, captions, notes,
  references, appendices, and page furniture as editable LaTeX behavior.
- Support English, Chinese, and bilingual templates, with conservative
  language-appropriate defaults when the official source is incomplete.
- Keep each observed source feature in an evidence and ownership audit. A
  feature is mapped to editable LaTeX, recorded as a default or guidance item,
  marked unobservable, or left explicitly unresolved.
- Treat title, author, and affiliation styles as candidates when their meaning
  is ambiguous. A ledger-bound semantic confirmation prevents author-facing
  instructions from being promoted into final front-matter mappings.
- Use PDF comparison when source rendering is available. Image interiors may
  differ, while image geometry, captions, tables, spacing, wrapping, and page
  flow remain part of the visual check.

### Typical Workflow

1. Confirm official sources and preserve their provenance.
2. Build a Word-format ledger before drafting LaTeX.
3. Resolve front matter and map source units in bounded review batches.
4. Build `journal-template.cls` for reusable presentation behavior and
   `main.tex` for editable manuscript content and fixtures.
5. Run package, evidence, and mapping audits. Record a clear handoff status.
6. Compile and compare PDFs when the necessary local tools and a comparable
   source render are available.

An ordinary conversion produces a usable package without forcing a full
cross-publisher benchmark. Regression tooling is reserved for skill
development or an explicitly requested comparison task.

### Deliverables

An ordinary conversion delivers at least:

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

When source inspection is possible, the package also contains the Word-format
ledger and source-inventory evidence. Mapping and rendering artifacts are
added when their corresponding checks have run.

### Installation

Install the `temp2tex/` directory under your Codex skills directory:

```text
<CODEX_HOME>/skills/temp2tex/
```

The installed directory must contain `SKILL.md` at its root. Start a new
Codex session after installation.

Alternatively, download `temp2tex-v0.2.0.skill` from the
[v0.2.0 release](https://github.com/TomayandJade/temp2tex/releases/tag/v0.2.0)
and extract it into the same location.

### Typical Request

```text
Use $temp2tex to rebuild this official journal Word template as an editable
LaTeX package. Work from the Word evidence unit by unit. Preserve supported
formatting for front matter, headings, tables, figures, notes, references, and
appendices. Keep publisher rules, conservative defaults, and unresolved gaps
separate, then provide the verification status and next required check.
```

### Verification And Limits

The skill records what has been inspected, mapped, compiled, or visually
checked. Missing local Word, TeX, or rendering tools do not prevent delivery
of an editable package; the resulting handoff documents the pending commands
and limitations.

Publisher templates can include proprietary fonts, embedded objects, and
Word-specific behavior. Exact visual matching may require additional official
evidence and a same-content rendered comparison. This repository excludes
publisher-owned templates, downloaded corpora, and generated regression
workspaces.

### License

Released under the [Apache License 2.0](LICENSE).

---

## 中文

### 概述

`temp2tex` 是一个 Codex skill，用于依据期刊官方的非 LaTeX 投稿模板，尤其是
Microsoft Word 模板，以及可获得的作者指南，重建可编辑的 LaTeX 期刊模板包。

该 skill 引导模型按证据逐项完成重建。默认交付物以
`journal-template.cls` 和 `main.tex` 为核心，并将官方要求、保守默认值和未解决
的格式缺口分别记录，便于后续核验和维护。

### 能力范围

- 检查 `.doc`、`.docx`、`.docm`、`.dot`、`.dotx`、`.dotm` 和 `.rtf` 模板，覆盖
  段落与字符 run 格式、表格、注释、页眉页脚、图形、样式和页面设置。
- 将标题页、作者与单位信息、摘要、关键词、各级标题、正文、公式、图片、表格、
  题注、脚注、参考文献、附录和页面元素重建为可编辑的 LaTeX 行为。
- 支持英文、中文和中英文双语模板；当官方信息不完整时，采用与语言习惯相符的
  保守默认格式，并明确记录其来源。
- 为每项可观测的源格式建立证据与归属审计：映射到可编辑 LaTeX、作为默认值或
  指导信息保留、标记为不可观测，或明确保留为未解决项。
- 标题、作者和单位样式在语义不明确时会先作为候选项。账本绑定的语义确认步骤可
  防止填写说明被误写入最终的前置信息映射。
- 在可获取源文件渲染结果时进行 PDF 对比。图片内部内容可以不同，但图片几何、
  题注、表格、间距、换行和页面流仍属于检查范围。

### 典型流程

1. 确认官方来源并保存其出处信息。
2. 先建立 Word 格式账本，再起草 LaTeX 模板。
3. 以有限批次完成前置信息确认和源单元映射。
4. 用 `journal-template.cls` 承担可复用的版式规则，用 `main.tex` 保存可编辑的
   稿件内容和测试样稿。
5. 执行模板包、证据和映射审计，并记录明确的交接状态。
6. 当本地工具和可比源渲染齐备时，编译并比较 PDF。

普通转换任务可以直接交付可用模板包，无需自动启动跨出版社的完整回归。回归工具
服务于 skill 开发或用户明确要求的对比任务。

### 交付物

普通转换至少交付：

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

当源模板可被结构化检查时，模板包还会保留 Word 格式账本和源文件清单。已执行的
映射审计和渲染验证会附带相应记录。

### 安装

将 `temp2tex/` 目录安装到 Codex skills 目录：

```text
<CODEX_HOME>/skills/temp2tex/
```

安装目录根部必须包含 `SKILL.md`。安装后新建一个 Codex 会话，使其重新发现该
skill。

也可以从 [v0.2.0 发布页](https://github.com/TomayandJade/temp2tex/releases/tag/v0.2.0)
下载 `temp2tex-v0.2.0.skill`，并解压到同一位置。

### 典型请求

```text
使用 $temp2tex 将这份期刊官方 Word 模板重建为可编辑的 LaTeX 模板包。请以 Word
证据为基础逐项处理，保留前置信息、标题、表格、图片、脚注、参考文献和附录中有
官方依据的格式；将官方规则、保守默认值和未解决缺口分开记录，并说明验证状态和
下一步需要执行的检查。
```

### 验证与限制

该 skill 会记录已完成的检查、映射、编译和视觉验证。本地缺少 Word、TeX 或渲染
工具时，仍可交付可编辑模板包；交接说明会列出待执行的命令和限制。

期刊模板可能包含专有字体、嵌入对象和仅能在 Word 中实现的版式行为。要达到严格的
视觉一致性，通常还需要更多官方证据和同稿渲染对比。本仓库不包含出版社拥有版权的
模板、下载语料或生成的回归工作区。

### 许可证

本项目采用 [Apache License 2.0](LICENSE) 发布。
