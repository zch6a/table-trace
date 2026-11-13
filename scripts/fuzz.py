"""Broken LaTeX and broken archives for the readers. Mutations of a corpus of tables that use what the readers handle
(\\multicolumn, \\multirow, rules, macros, nested tabulars, subtables, \\captionof) — bytes flipped, cut short, pieces
repeated or removed, LaTeX fragments spliced in — through find_tables and the text and cell readers; and mutated
.tar.gz sources through the unpacking. A reader must give tables (or a SourceError for an archive), never another
exception, and must not be slow. Nothing is downloaded.

    uv run python scripts/fuzz.py --rounds 2000
"""

from __future__ import annotations

import argparse
import io
import random
import shutil
import sys
import tarfile
import tempfile
import time
import traceback
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))
from table_trace.compare import find, pattern  # noqa: E402
from table_trace.source import Paper, SourceError, extract, read_project  # noqa: E402
from table_trace.tables import find_tables  # noqa: E402

CORPUS = [
    (root / "tests" / "fixtures" / "paper" / "main.tex").read_text(encoding="utf-8"),
    (root / "tests" / "fixtures" / "paper" / "appendix.tex").read_text(encoding="utf-8"),
    r"""\newcommand{\thickhline}{\noalign{\global\arrayrulewidth 1pt}\hline}\newcommand{\res}[2][0.0]{#2$\pm$#1}
\begin{table*}\begin{subtable}{.5\linewidth}\caption{a}\begin{tabular}{@{}l>{\centering}p{2cm}c@{}}
\multicolumn{2}{@{}c@{}}{Head} & \multirow{-2}{*}{X} \\ \thickhline
\begin{tabular}{c} Big \\ model \end{tabular} & \res[0.3]{75.3} & \underline{.93} \\
\rowcolor[HTML]{EEEEEE} {\bf Ours} & 2018-2019 & 125m \\ \cline{1-2} \addlinespace[2pt] T5 & $^a$75.3 & 1,024 \\
\end{tabular}\end{subtable}\caption{Main}\label{tab:x}\end{table*}
\begin{figure}\begin{minipage}{.5\linewidth}\begin{tabular}{lc} A & B \\ \hline x & 1.0 \\ \end{tabular}\captionof{table}{Side}\end{minipage}\end{figure}""",
    r"""\begin{table}\caption{Models as columns}\begin{tabularx}{\linewidth}{lXX} & Ours (ViT-L/16) & BiT \\ \toprule
ImageNet & \textbf{87.76}\textsubscript{$\pm$0.03} & 87.54 \\ \iffalse $a \iff b$ \fi CIFAR-10 & 99.42 & 99.37 \\ \bottomrule
\end{tabularx}\end{table}""",
]
FRAGMENTS = ["\\", "{", "}", "&", "\\\\", "$", "%", "\\multicolumn{", "\\multirow{-3}{*}{", "\\begin{tabular}{c}", "\\end{tabular}",
             "\\hline", "\\cline{", "\\caption{", "\\label{", "\\begin{table}", "\\end{table}", "\\iffalse", "\\fi", "\\newcommand{\\z}[1]{#1#1}\\z{",
             "\\def\\a{\\a\\a}\\a", "\\textbf{", "\\pm", "1e9", "−", "\x00", "é", "\\captionof{table}{", "\\noalign{", "#1", "[", "]"]  # fmt: skip


def mutate(s: str, rng: random.Random) -> str:
    for _ in range(rng.randint(1, 6)):
        kind = rng.randrange(5)
        i = rng.randrange(len(s) + 1)
        if kind == 0:
            s = s[:i] + rng.choice(FRAGMENTS) + s[i:]
        elif kind == 1:
            s = s[: rng.randrange(len(s) + 1)]
        elif kind == 2 and s:
            s = s[:i] + s[i : i + rng.randint(1, 400)] * rng.randint(2, 6) + s[i:]
        elif kind == 3:
            s = s[:i] + s[i + rng.randint(1, 300) :]
        else:
            s = s[:i] + chr(rng.randrange(1, 0x2FFF)) + s[i:]
    return s


def source_archive(rng: random.Random) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name in ["main.tex", "sec/a.tex", "../up.tex", "/abs.tex", "fig.png"][: rng.randint(1, 5)]:
            data = mutate(rng.choice(CORPUS), rng).encode("utf-8", "replace")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    failures: list[str] = []
    slowest = (0.0, "")
    t0 = time.perf_counter()
    rows, cols = [pattern("ResNet-50"), pattern("ViT-L/16")], [pattern("Top-1", strict=False), pattern("ImageNet", strict=False)]
    with tempfile.TemporaryDirectory(prefix="table-trace-fuzz-") as tmp:
        for r in range(args.rounds):
            files = [(f"f{k}.tex", mutate(rng.choice(CORPUS), rng)) for k in range(rng.randint(1, 3))]
            t = time.perf_counter()
            try:
                tables = find_tables(files)
                for tab in tables:
                    tab.columns()
                    tab.body()
                find(Paper("fuzz", files), rows, cols, tables=tables)
            except Exception:
                failures.append(f"tables #{r}: {traceback.format_exc(limit=4)}")
            took = time.perf_counter() - t
            if took > slowest[0]:
                slowest = (took, f"tables #{r}")
            if r % 5 == 0:
                data = source_archive(rng)
                if rng.random() < 0.5:
                    b = bytearray(data)
                    for _ in range(rng.randint(1, 30)):
                        b[rng.randrange(len(b))] = rng.randrange(256)
                    data = bytes(b[: rng.randrange(len(b) + 1)] if rng.random() < 0.3 else b)
                into = Path(tmp) / f"s{r}"
                try:
                    extract(data, into)
                    main_tex = into / "main.tex"
                    if main_tex.is_file():
                        paper = read_project(main_tex)
                        find_tables(paper.files, paper.includes)
                    escaped = [p for p in Path(tmp).iterdir() if p.is_file()]  # "../up.tex" would land beside the folder
                    assert not escaped, f"a file outside its folder: {escaped}"
                except SourceError:
                    pass
                except Exception:
                    failures.append(f"archive #{r}: {traceback.format_exc(limit=4)}")
                shutil.rmtree(into, ignore_errors=True)
    print(
        f"{args.rounds} rounds (seed {args.seed}), {time.perf_counter() - t0:.0f} s: {len(failures)} failures; slowest {slowest[0]:.2f} s ({slowest[1]})"
    )
    seen = set()
    for f in failures:
        last = f.strip().splitlines()[-1]
        if last not in seen:
            seen.add(last)
            print(f)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
