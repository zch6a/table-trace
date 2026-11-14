---
name: table-trace
description: Read the exact numbers in a paper's result tables (from its arXiv LaTeX source, each with its table, row, column, file and line), or compare what several papers report for the same model on the same benchmark, with table-trace. Use when the user asks for a paper's reported results, a baseline's numbers, or why papers disagree on a model's score.
license: MIT
compatibility: Needs Python 3.10+ and uv. Runs table-trace with uvx from GitHub (git+https://github.com/zch6a/table-trace@v0). Fetches each paper's source from arXiv (three seconds apart); a local LaTeX folder needs no network.
metadata:
  homepage: https://github.com/zch6a/table-trace
---

# A paper's table numbers, traced, with table-trace

```bash
uvx --from git+https://github.com/zch6a/table-trace@v0 table-trace extract 2010.11929 --format md          # every table
uvx --from git+https://github.com/zch6a/table-trace@v0 table-trace extract 2010.11929 --table 2            # one table, JSON
uvx --from git+https://github.com/zch6a/table-trace@v0 table-trace compare 2010.11929 2012.12877 --row "ViT-B/16" --col ImageNet --json
```

- Quote numbers with where they are: "Table 5, row ResNet-50, column ImNet top-1: 76.2 (experiments.tex:197)". Bold
  means the authors marked it best; `better` says whether the column is higher or lower is better.
- In `compare`, read each result's column and caption before calling two numbers the same measurement: top-1 and
  top-5, an error rate and an accuracy, another resolution or pre-training are different. Give the alternative
  spellings of a model with several `--row` (`--row ResNet-50 --row R50`).
  `--caption ImageNet` keeps only tables whose caption names the benchmark when the columns name only the metric
  ("top-1 err."). A table with the models as columns is read the other way round (`transposed` in the JSON).
- A paper submitted as a PDF only has no source: say so rather than guess its numbers.

## Are two scores comparable?

`table-trace settings PAPER... --benchmark NAME` (repeat `--benchmark` for spellings) reads how each paper evaluated
on that benchmark: shots, chain of thought, decoding, harness, metric, with file and line (`--evidence` for the
sentences). Use it before comparing numbers from different papers; say which settings differ or are not stated, and
quote the evidence rather than guessing a setting a paper does not state.
