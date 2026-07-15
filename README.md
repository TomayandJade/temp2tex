# temp2tex

## English

### Overview

`temp2tex` is a Codex skill for reconstructing an editable LaTeX journal
template from an official non-LaTeX author template, primarily Microsoft Word
files, together with supporting publisher material.

It is designed to guide an agent through evidence-based reconstruction rather
than produce a one-shot conversion. The target is a maintainable journal
template package, normally centred on `journal-template.cls` and `main.tex`.

### Supported Sources

- Word templates: `.doc`, `.docx`, `.docm`, `.dot`, `.dotx`, and `.dotm`
- Official author instructions, reference rules, artwork guidance, and journal
  web pages
- Official sample PDFs or published samples when they provide relevant layout
  evidence

The skill supports English, Chinese, and bilingual templates. When official
requirements are incomplete, it records a conservative language-appropriate
default instead of presenting it as a publisher rule.

### Reconstruction Method

The skill keeps the work on the template-reconstruction path:

1. Inspect the official source and build a paragraph/run, table, drawing, note,
   and page-furniture evidence ledger.
2. Classify each source unit by manuscript role and map it to one editable
   LaTeX owner, or record a default or unresolved gap.
3. Build and compile a representative `.cls + main.tex` package that exercises
   the applicable title, metadata, abstract, headings, body, tables, figures,
   notes, references, and appendix behavior.
4. Audit evidence coverage before adjusting layout. An initial converter output
   is a draft for review, not evidence of fidelity.
5. When source rendering is available, compare PDFs using the same fixture and
   a role-level content contract before promoting any layout calibration.

Tables are audited as structured content, including cell text, grid, merge,
fill, and caption behavior. PDF comparison may exclude differing raster-image
interiors from a format metric, but it still checks image geometry, captions,
spacing, wrapping, and page flow.

### Deliverables

An ordinary conversion produces an editable package with at least:

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

When the Word source is structurally readable, the package also preserves
`word_format_ledger.json`. When source inspection is available, it includes
`source_inventory.json` and `source_feature_coverage.json`. Optional rendering
work may add a comparison report, layout profile, and diff previews.

### Installation

Install the `temp2tex/` directory under the Codex skills directory:

```text
<CODEX_HOME>/skills/temp2tex/
```

The directory must contain `SKILL.md` at its root. Start a new Codex session
after installation so the skill is discovered.

Alternatively, download `temp2tex-v0.1.1.skill` from the
[v0.1.1 release](https://github.com/TomayandJade/temp2tex/releases/tag/v0.1.1)
and extract it into the same location.

### Typical Use

Provide the official Word template and any available author instructions, then
ask Codex to load the skill:

```text
Use $temp2tex to rebuild this official journal DOCX template as an editable
LaTeX package. Work role by role from the Word evidence, preserve the source
formatting for the title, front matter, headings, tables, figures, notes,
references, and appendices, and record unsupported requirements as defaults or
gaps rather than as official rules.
```

### Verification

Compilation and PDF comparison are important checks, but missing local Word,
TeX, or rendering tools do not block delivery of an editable package. The
handoff must state the available evidence, completed checks, unresolved gaps,
and exact commands for pending verification.

For skill development or an explicit Word-versus-LaTeX request, the repository
also includes tools and guidance for same-content regression. A benchmark does
not replace the evidence ledger for the journal currently being reconstructed.

### Scope And Limitations

Publisher templates can contain incomplete rules, proprietary fonts, embedded
objects, and Word-specific layout behavior. Exact visual matching may require
additional official evidence and local rendering. This repository does not
include publisher-owned templates, downloaded source corpora, or generated
regression workspaces; obtain and handle those materials under the applicable
publisher terms.

### License

Released under the [Apache License 2.0](LICENSE).

---

## 中文

### 概述

`temp2tex` 是一个 Codex skill，用于依据期刊官方的非 LaTeX 投稿模板，尤其是
Microsoft Word 模板，以及相关作者指南，重建可编辑的 LaTeX 期刊模板。

它并不把任务当作一次性格式转换，而是引导模型按证据逐项重建。默认交付为便于
维护的模板包，核心文件通常是 `journal-template.cls` 和 `main.tex`。

### 支持的来源

- Word 模板：`.doc`、`.docx`、`.docm`、`.dot`、`.dotx`、`.dotm`
- 官方作者指南、参考文献规则、图件要求和期刊网站说明
- 能提供相关版式证据的官方样刊 PDF 或已发表样例

该 skill 支持英文、中文和中英文双语模板。官方要求不完整时，会采用保守且符合
语言习惯的默认格式，并明确标记为默认值，不会将其表述为官方规则。

### 重建方法

skill 通过以下流程让模型始终围绕模板重建工作：

1. 检查官方来源，建立段落与连续 run、表格、图形、注释和页眉页脚的证据账本。
2. 为每个来源单元判定稿件角色，并映射到一个可编辑的 LaTeX 格式所有者；无法
   确定时记录默认值或格式缺口。
3. 构建并编译覆盖标题、前置信息、摘要、各级标题、正文、表格、图片、注释、
   参考文献和附录的代表性 `.cls + main.tex` 模板包。
4. 在调整版式前完成证据覆盖审计。任何初始转换结果都只是待审计草稿，不能作为
   格式一致或任务完成的依据。
5. 在可渲染来源文件时，使用同一份测试内容和角色级文本契约比较 PDF，之后才允许
   推广版式校准结果。

表格会作为结构化内容审计，包括单元格文字、网格线、合并、底纹和题注。PDF 对比
可以在格式指标中忽略不同的位图内部内容，但仍会检查图片的尺寸、位置、题注、
留白、环绕和后续页面流；表格不会被忽略或栅格化处理。

### 交付物

常规转换至少交付以下可编辑文件：

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

Word 来源可被结构化读取时，交付物还会保留 `word_format_ledger.json`。完成来源
检查时，还会包含 `source_inventory.json` 与 `source_feature_coverage.json`。完成可选
渲染验证后，可额外提供对比报告、版式分析和差异预览图。

### 安装

将 `temp2tex/` 目录安装到 Codex skills 目录：

```text
<CODEX_HOME>/skills/temp2tex/
```

目录根部必须包含 `SKILL.md`。安装后新建一个 Codex 会话，使系统重新发现该 skill。

也可以从 [v0.1.1 发布页](https://github.com/TomayandJade/temp2tex/releases/tag/v0.1.1)
下载 `temp2tex-v0.1.1.skill`，并解压到同一位置。

### 典型用法

提供官方 Word 模板和可获得的作者指南后，请 Codex 加载该 skill。例如：

```text
使用 $temp2tex 将这份期刊官方 DOCX 模板重建为可编辑的 LaTeX 模板包。请从 Word
证据出发，按稿件角色逐项处理标题、前置信息、各级标题、表格、图片、注释、参考
文献和附录的格式；无法确认的要求请记录为默认值或格式缺口，不要表述为官方规则。
```

### 验证

编译和 PDF 对比很重要，但本地缺少 Word、TeX 或渲染工具时，仍应交付可编辑模板包。
交付说明必须写清可用证据、已完成检查、未解决缺口，以及待执行验证的具体命令。

当用户明确要求 Word 与 LaTeX 对比，或正在改进 skill 本身时，仓库还提供同稿回归
测试工具和方法。回归结果不能替代当前期刊模板的逐项证据账本。

### 范围与限制

期刊模板可能包含不完整要求、专有字体、嵌入对象和仅能在 Word 中实现的版式行为。
要达到严格视觉一致，可能仍需更多官方证据和本地渲染验证。仓库不包含出版社拥有
的模板、下载语料或生成的回归工作区；相关材料应由使用者自行取得并遵守适用的
出版社条款。

### 许可证

本项目采用 [Apache License 2.0](LICENSE) 发布。
