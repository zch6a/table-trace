# Changelog

## 0.1.0 — unreleased

First release.

- `table-trace extract`: a paper's tables from its LaTeX source (an arXiv id or link, a folder, a .tex file), numbered
  as in the paper, with label and caption; each cell's text, result, ± spread, %, bold, underline, every number in it,
  file and line; JSON, Markdown or CSV.
- `table-trace compare`: what several papers report for one model on one benchmark or metric, each number with its
  table and line, which way its column is better, and how far apart they are; tables with the models as columns are
  read the other way round.
- No dependencies; nothing of the papers is kept.
