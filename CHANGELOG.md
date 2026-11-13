# Changelog

## 0.1.0 — 2026-11-14

First release: every number in a paper's tables, read from its LaTeX source and traced to the cell it is in; and what
several papers report for the same model on the same benchmark, side by side.

**Reading a paper.** An arXiv id or link (the source fetched into a temporary folder, unpacked safely, read and
deleted, three seconds between papers), a LaTeX project folder, a folder of table snippets, or a .tex file; `\input`
followed, comments and `\iffalse` left out. No dependencies.

**The tables.** `tabular` and its relatives, numbered as in the paper (each table caption, two tables side by side in
one float, `\captionof{table}`, tables in `\input` files where they are included; not a subtable's caption), with label
and caption. `\multicolumn` (column specs with braces too) and `\multirow` (down or up), booktabs and other rules,
rules drawn by the paper's macros, tabulars nested in a cell, image grids left out.

**Each cell.** The text as printed (the paper's macros expanded, optional arguments included; formatting dropped;
symbols as Unicode); the result, its ± spread, %, bold and underline; every number in it; the file and line. A size
(125M), a range (2018-2019) or a column of years is not a result.

**`table-trace extract`** gives the tables as JSON, Markdown or CSV. **`table-trace compare`** finds one model's results
on one benchmark or metric across papers (names matched by their words and numbers, not by longer names: ResNet-50 is
not SE-ResNet-50, GPT-3 is not GPT-3.5), in tables either way round, with which way each column is better, a warning
when error rates and accuracies are mixed, and how far apart the numbers are.

Tried on 25 well-known papers (about 28,300 cells, no LaTeX left in a cell's text); 15,500 rounds of broken LaTeX and
archives without a failure.
