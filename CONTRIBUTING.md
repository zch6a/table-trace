# Contributing

```bash
uv sync
uv run pytest -q                 # made-up LaTeX: no network
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run table-trace extract tests/fixtures/paper --format md
```

## Where things are

| Path | What it does |
| --- | --- |
| `src/table_trace/source.py` | a paper from arXiv (fetched, unpacked safely, deleted), a folder or a .tex file; `\input` followed |
| `src/table_trace/text.py` | a cell's LaTeX as printed: the paper's macros expanded, formatting dropped, symbols as Unicode |
| `src/table_trace/tables.py` | the tables: numbers and captions, rows and cells, results, ±, bold, underline, file and line |
| `src/table_trace/compare.py` | one model on one benchmark across papers: name patterns, matching cells |
| `src/table_trace/cli.py` | `extract` (JSON, Markdown, CSV) and `compare` |

## A table it reads wrongly

Add the smallest LaTeX that shows it to `tests/test_tables.py` (a table, its expected rows or cells), then fix the
reader. Real papers are the best test: `table-trace extract <id> --format md` and compare with the PDF.
