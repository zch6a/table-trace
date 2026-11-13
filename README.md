<div align="center">

# table-trace

**Every number in a paper's tables, read from its LaTeX source and traced to the cell it is in.** Give it an arXiv
id: it returns each table's rows and cells as data (text, result, ± spread, bold, file and line). Give it several
papers and a model: it shows what each one reports for the same model on the same benchmark, side by side.

<a href="https://github.com/zch6a/table-trace/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/zch6a/table-trace/actions/workflows/ci.yml/badge.svg"></a>
<img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue">
<img alt="No dependencies" src="https://img.shields.io/badge/dependencies-none-2ea44f">
<a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-blue"></a>

**English** · [简体中文](README.zh-CN.md)

</div>

---

```console
$ table-trace compare 1512.03385 2012.12877 2201.03545 1905.11946 --row ResNet-50 --col top-1 --col acc
     20.74 (lower is better)  1512.03385 Table 4: ResNet-50 | top-1 err.   [residual_v1_arxiv_release.tex:379]
      76.2  2012.12877 Table 5: ResNet-50 | 25M | ImNet top-1   [experiments.tex:197]
     76.13  2201.03545 Table 10: ResNet-50 (PyTorch) | IN-1K acc.   [main.tex:809]
     78.82 ± 0.07  2201.03545 Table 10: ResNet-50 (enhanced recipe) | IN-1K acc.   [main.tex:811]
        76  1905.11946 Table 2: ResNet-50 | Top-1 Acc.   [arxiv-stripped.tex:307]
  ...
```

One model, four papers: ImageNet top-1 of 76.0 (EfficientNet), 76.13 and, with a newer training recipe, 78.82 ± 0.07
(ConvNeXt), 76.2 (DeiT), and an error of 20.74 in the ResNet paper itself (79.26 accuracy, single model, its own
testing). Every number points to the table and the line it comes from, so the reason for each difference (the
recipe, the testing, the metric) is one look away.

## Why

Papers report the same model on the same benchmark with numbers several points apart: a 2026 study of geospatial
foundation models mined 10,817 results from 152 papers and found gaps of 10 to 20 points for the same model and
protocol ([arXiv:2605.12678](https://arxiv.org/abs/2605.12678)). Reading numbers from a PDF loses where they came
from; a language model reading tables can misplace a digit. table-trace reads the LaTeX the authors wrote, with rules,
and keeps the cell.

## What it reads

- **Tables**: `tabular`, `tabular*`, `tabularx`, `tabulary`, `longtable`, `array`, `tblr`; `\multicolumn` (a spanning
  header joined to the columns under it: "ImageNet Top-1"), `\multirow` (a row name filled down the rows it spans);
  booktabs rules, `\hline`, makecell's `\Xhline`, `\noalign`, and rules drawn by the paper's own macros.
- **Numbering**: Table 1, 2, … as the paper numbers them: each table caption counts, two tables side by side in one
  float are two tables, a subtable's caption is not a new one; with each table's `\label` and caption.
- **Cells**: the text as printed (the paper's `\newcommand` and `\def` macros expanded, `\textbf{}` and other formatting
  dropped, `\pm` `\dagger` `\uparrow` as ± † ↑, citations left out); the result (the first number, when the cell is a
  result: `125M` and `50 epochs` are not), its ± spread, %, bold (the authors' best) and underline (often second
  best), every number in the cell (`89.3/82.1`), and the file and line.
- **Which way is better**: from an arrow in the header or the metric's name (accuracy, BLEU, top-1 are higher; error,
  FID, latency lower), so `compare` warns when an error rate and an accuracy are side by side.
- **The source**: an arXiv id or link (the source fetched into a temporary folder, read, and deleted; three seconds
  between papers), a LaTeX project folder, or a .tex file; `\input` and `\include` followed, comments and `\iffalse`
  left out.

Tried on eleven well-known papers (ResNet, ViT, BERT, T5, LoRA, DeiT, ConvNeXt, Swin, EfficientNet, CLIP, LLaMA):
about 13,500 cells, no LaTeX left in a cell's text, ResNet's 14 tables numbered and labelled as in the paper.

## Use it

```bash
uvx --from git+https://github.com/zch6a/table-trace table-trace extract 1512.03385                 # JSON
uvx --from git+https://github.com/zch6a/table-trace table-trace extract 1512.03385 --format md     # Markdown, bold kept
uvx --from git+https://github.com/zch6a/table-trace table-trace extract paper/ --table 2 --format csv
uvx --from git+https://github.com/zch6a/table-trace table-trace compare 2010.11929 2012.12877 --row "ViT-B/16" --col ImageNet --json
```

`compare` takes `--row` and `--col` several times (other spellings: `--row ResNet-50 --row R50`) and `--caption` to keep
only tables whose caption names something. Names match by their words and numbers in order, whatever the spacing,
hyphens or case: "ResNet-50" finds "ResNet50" and "ResNet 50", not other models such as "ResNet-101",
"ResNet-50x2", "SE-ResNet-50" or "R50x1+ViT-B/16".
No dependencies; Python 3.10+.

## Limits

- LaTeX only: a paper submitted to arXiv as a PDF has no source to read. Tables drawn as images are not tables.
- A cell whose number is built by an unusual macro (a computed value, `\pgfmathprintnumber`) is read as text.
- `compare` matches names and headers; it does not know that "IN-1K acc." and "Top-1" are the same metric, or that
  two papers tested differently: it shows the headers and captions so that a reader can tell.

## Also in this toolkit

[arxiv-diff](https://github.com/zch6a/arxiv-diff) shows what changed between a paper's versions, tables included ·
[exp-tables](https://github.com/zch6a/exp-tables) makes result tables from experiment logs ·
[repro-score](https://github.com/zch6a/repro-score) scores a paper's code for reproducibility.

## License

MIT. Parts come from [paper-proof](https://github.com/zch6a/paper-proof) (the same author's, MIT). Papers' sources are
read where they are and not kept.
