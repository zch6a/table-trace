"""table-trace: every number in a paper's tables, read from its LaTeX source and traced to the cell it is in.

table-trace extract 1512.03385                         the paper's tables as JSON (each cell: text, result, ±, bold, file:line)
table-trace extract 1512.03385 --format md             as Markdown; --format csv: one line per cell
table-trace extract paper/ --table 2                   a LaTeX project folder (or a .tex file), one table
table-trace compare 1512.03385 2012.12877 --row ResNet-50 --col top-1 --caption ImageNet
                                                       what each paper reports for a model, and how far apart

A paper is an arXiv id or link (its source is fetched into a temporary folder and deleted once read, three seconds
apart between papers), a folder holding a LaTeX project, or a .tex file. Rules, not a language model: what it
reads is in the source, and each number says where.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from dataclasses import asdict
from typing import Any

from . import __version__
from .compare import Found, find, pattern, spread_of
from .source import Paper, SourceError, load
from .tables import Table, find_tables


def table_doc(t: Table) -> dict[str, Any]:
    cols = t.columns()
    rows = []
    for i, key in t.body():
        cells = []
        for j, c in enumerate(t.rows[i]):
            if not c.text and not c.raw:
                continue
            cells.append({"column": cols[j] if j < len(cols) else f"column {j + 1}", "text": c.text, "value": c.value, "spread": c.spread,
                          "percent": c.percent, "bold": c.bold, "underline": c.underline, "line": c.line})  # fmt: skip
        rows.append({"row": key, "cells": cells})
    return {"table": t.name, "number": t.number, "label": t.label, "caption": t.caption, "file": t.file, "line": t.line,
            "columns": cols, "header": [[c.text for c in r] for r in t.rows[: t.header_rows]], "rows": rows}  # fmt: skip


def _markdown(paper: Paper, tables: list[Table]) -> str:
    out = [f"# {paper.name}" + (f" ({paper.url})" if paper.url else ""), ""]
    for t in tables:
        out.append(f"## {t.name} — {t.file}:{t.line}" + (f" ({t.label})" if t.label and t.number else ""))
        if t.caption:
            out += ["", t.caption]
        width = max((len(r) for r in t.rows), default=0)
        if not width:
            continue
        cols = t.columns()
        esc = lambda s: s.replace("|", "\\|")  # noqa: E731
        out += ["", "| " + " | ".join(esc(c) for c in cols) + " |", "|" + "---|" * width]
        for i, _ in t.body():
            cells = [esc(c.text) for c in t.rows[i]] + [""] * (width - len(t.rows[i]))
            for j, c in enumerate(t.rows[i]):
                if c.bold and c.text:
                    cells[j] = f"**{cells[j]}**"
                elif c.underline and c.text:
                    cells[j] = f"<u>{cells[j]}</u>"
            out.append("| " + " | ".join(cells) + " |")
        out.append("")
    return "\n".join(out)


def _cell(s: str) -> str:
    """Text as a CSV field a spreadsheet will not run as a formula (=, +, @, or - before a non-number)."""
    return "'" + s if s[:1] in ("=", "+", "@") or (s[:1] == "-" and not re.match(r"-[\d.]", s)) else s


def _csv(paper: Paper, tables: list[Table], w: Any) -> None:
    for t in tables:
        cols = t.columns()
        for i, key in t.body():
            for j, c in enumerate(t.rows[i]):
                if j < t.row_start(i) or not c.text:
                    continue
                w.writerow([paper.name, t.name, _cell(t.caption[:200]), _cell(key), _cell(cols[j] if j < len(cols) else ""), _cell(c.text),
                            "" if c.value is None else c.value, "" if c.spread is None else c.spread, int(c.bold), int(c.underline), t.file, c.line])  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="table-trace", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"table-trace {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)
    e = sub.add_parser("extract", help="a paper's tables, each number with its cell")
    e.add_argument("papers", nargs="+", metavar="PAPER", help="arXiv ids or links, LaTeX project folders, .tex files")
    e.add_argument("--format", choices=["json", "md", "csv"], default="json")
    e.add_argument("--table", type=int, help="only this table (its number in the paper)")
    c = sub.add_parser("compare", help="what each paper reports for a model on a benchmark")
    c.add_argument("papers", nargs="+", metavar="PAPER")
    c.add_argument("--row", action="append", required=True, help="the model (repeat for other spellings: --row ViT-B/16 --row ViT-Base)")
    c.add_argument("--col", action="append", required=True, help="the benchmark or metric, in a column header (repeatable)")
    c.add_argument("--caption", action="append", help="only tables whose caption or label names this (repeatable)")
    c.add_argument("--json", action="store_true")
    st = sub.add_parser("settings", help="how each paper evaluated on a benchmark: shots, chain of thought, decoding, harness, metric")
    st.add_argument("papers", nargs="+", metavar="PAPER")
    st.add_argument(
        "--benchmark", action="append", required=True, help="the benchmark (repeat for other spellings: --benchmark GSM8K --benchmark GSM-8K)"
    )
    st.add_argument("--evidence", action="store_true", help="show the sentence each setting was read from")
    st.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.command == "settings":
            return _settings(args)
        return _extract(args) if args.command == "extract" else _compare(args)
    except (SourceError, ValueError, OSError) as err:
        print(f"table-trace: {err}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("table-trace: stopped", file=sys.stderr)
        return 130
    except MemoryError:
        print("table-trace: out of memory reading a table (a macro that grows without end?)", file=sys.stderr)
        return 2


def _extract(args: argparse.Namespace) -> int:
    docs, buf = [], io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    if args.format == "csv":
        w.writerow(["paper", "table", "caption", "row", "column", "text", "value", "spread", "bold", "underline", "file", "line"])
    found_any, failed = False, 0
    for src in args.papers:
        try:
            paper = load(src)
        except SourceError as err:
            if len(args.papers) == 1:
                raise
            print(f"table-trace: {err}", file=sys.stderr)
            failed += 1
            continue
        tables = find_tables(paper.files, paper.includes)
        if args.table is not None:
            tables = [t for t in tables if t.number == args.table]
        found_any |= bool(tables)
        if args.format == "json":
            docs.append({"paper": paper.name, "url": paper.url, "tables": [table_doc(t) for t in tables]})
        elif args.format == "md":
            print(_markdown(paper, tables))
        else:
            _csv(paper, tables, w)
    if args.format == "json":
        print(json.dumps(docs[0] if len(docs) == 1 else docs, indent=1, ensure_ascii=False))
    elif args.format == "csv":
        sys.stdout.write(buf.getvalue())
    if failed:
        return 2
    if not found_any:
        print("table-trace: no tables found" + (f" numbered {args.table}" if args.table is not None else ""), file=sys.stderr)
        return 1
    return 0


def _settings(args: argparse.Namespace) -> int:
    from .settings import KINDS, differences, read

    bench = re.compile("|".join(pattern(b, strict=False).pattern for b in args.benchmark), re.I)
    found = []
    for src in args.papers:
        try:
            found.append(read(load(src), bench))
        except SourceError as err:
            if len(args.papers) == 1:
                raise
            print(f"table-trace: {err}", file=sys.stderr)
    if args.json:
        print(json.dumps([{"paper": s.paper, "mentions": s.mentions, "settings": {k: [asdict(e) for e in s.found.get(k, [])] for k in KINDS}}
                          for s in found], indent=1, ensure_ascii=False))  # fmt: skip
        return 0 if found else 2
    names = {"shots": "shots", "cot": "chain of thought", "decoding": "decoding", "harness": "harness", "metric": "metric"}
    for s in found:
        print(f"{s.paper}: {s.mentions} sentence(s) name {' / '.join(args.benchmark)}")
        for k in KINDS:
            ev = s.found.get(k, [])
            vals = list(dict.fromkeys(e.value for e in ev))
            where = f"  [{ev[0].file}:{ev[0].line}]" if ev else ""
            print(f"  {names[k]:17} {', '.join(vals) if vals else 'not stated'}{where}")
            if args.evidence:
                for e in ev[:3]:
                    print(f"      {e.file}:{e.line}  {e.sentence[:160]}")
        print()
    diff = differences(found)
    if len(found) > 1:
        print("Differences:" if diff else "No difference in what the papers state (which does not mean they evaluated the same way).")
        for d in diff:
            print(f"  {d}")
    return 0 if found else 2


def _compare(args: argparse.Namespace) -> int:
    rows = [pattern(r) for r in args.row]
    cols = [pattern(c, strict=False) for c in args.col]
    captions = [pattern(c, strict=False) for c in args.caption or []]
    found: list[Found] = []
    missing, failed = [], 0
    for src in args.papers:
        try:
            paper = load(src)
        except SourceError as err:
            if len(args.papers) == 1:
                raise
            print(f"table-trace: {err}", file=sys.stderr)
            failed += 1
            continue
        hits = find(paper, rows, cols, captions)
        found += hits
        if not hits:
            missing.append(paper.name)
    if args.json:
        lo_hi = spread_of(found)
        print(json.dumps({"row": args.row, "column": args.col, "found": [asdict(f) for f in found], "papers_without": missing,
                          "lowest": lo_hi[0] if lo_hi else None, "highest": lo_hi[1] if lo_hi else None}, indent=1, ensure_ascii=False))  # fmt: skip
        return 2 if failed else 0 if found else 1
    for f in found:
        sp = f" ± {f.spread:g}" if f.spread is not None else ""
        bold = " (bold)" if f.bold else ""
        bold += " (lower is better)" if f.better == "lower" else ""
        bold += " (models as columns)" if f.transposed else ""
        print(f"{f.value:>10g}{sp}{bold}  {f.paper} {f.table}: {f.row} | {f.column}   [{f.file}:{f.line}]  {f.caption[:60]}")
    lo_hi = spread_of(found)
    if lo_hi:
        papers = len({f.paper for f in found})
        print(
            f"\n{len(found)} results in {papers} paper{'s' if papers != 1 else ''}: from {lo_hi[0]:g} to {lo_hi[1]:g} (a difference of {lo_hi[1] - lo_hi[0]:.4g})"
        )
        if len({f.better for f in found if f.better}) > 1:
            print("Some columns are better higher and some lower (an accuracy and an error rate): do not compare them as one.")
        print("Columns can differ in metric or setting (top-1/top-5, resolution, pre-training): read the headers before comparing.")
    if not found:
        print(f"nothing matched --row {' / '.join(args.row)} in a column named {' / '.join(args.col)}"
              + (f" (tables captioned {' / '.join(args.caption)})" if args.caption else "")
              + ": try other spellings (--row may be given several times) or the metric's name in --col", file=sys.stderr)  # fmt: skip
    elif missing:
        print(f"no match in: {', '.join(missing)}", file=sys.stderr)
    return 2 if failed else 0 if found else 1


if __name__ == "__main__":
    raise SystemExit(main())
