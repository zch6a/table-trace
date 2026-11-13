"""Made-up LaTeX only: no network."""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from table_trace import cli, source
from table_trace.compare import find, pattern
from table_trace.source import SourceError, extract, find_main, read_project
from table_trace.tables import direction, find_tables

FIXTURE = Path(__file__).parent / "fixtures" / "paper"


def tables_of(tex: str) -> list:
    return find_tables([("main.tex", tex)])


def test_the_fixture_paper() -> None:
    paper = read_project(FIXTURE / "main.tex")
    assert [f for f, _ in paper.files] == ["main.tex", "appendix.tex"]  # \input followed, in reading order
    t1, t2 = find_tables(paper.files)
    assert (t1.number, t1.label, t1.caption) == (1, "tab:main", "Top-1 accuracy (%) on ImageNet.")
    assert t1.columns() == ["Method", "Backbone", "ImageNet Top-1", "ImageNet Top-5"]  # the spanning header over its columns
    assert [k for _, k in t1.body()] == ["Supervised | ResNet-50", "Supervised | ResNet-101", "Ours | ResNet-50"]  # \multirow filled down
    ours = t1.rows[t1.body()[2][0]]
    assert (ours[2].value, ours[2].spread, ours[2].bold, ours[2].line) == (78.3, 0.2, True, 15)  # \best{} is the paper's \textbf
    assert ours[3].underline and ours[3].value == 94.1
    assert (t2.number, t2.file, t2.caption) == (2, "appendix.tex", "Ablation.")


def test_rules_drawn_by_macros_and_nested_braces() -> None:
    tex = r"""\newcommand{\thickhline}{\noalign{\global\savewidth\arrayrulewidth\global\arrayrulewidth 1pt}\hline\noalign{\global\arrayrulewidth\savewidth}}
\begin{table}\caption{x}\begin{tabular}{lc}
Model & Acc. \\ \thickhline
\Xhline{0.3\arrayrulewidth} ResNet-50 (PyTorch) & 76.13 \\
\specialrule{1pt}{1pt}{1pt} ResNet-50 (enhanced) & 78.82 \\
\end{tabular}\end{table}"""
    (t,) = tables_of(tex)
    assert t.header_rows == 1  # the rule a macro draws ends the header
    assert [k for _, k in t.body()] == ["ResNet-50 (PyTorch)", "ResNet-50 (enhanced)"]  # nothing of the rules in a name


def test_numbering_subtables_and_stray_tabulars() -> None:
    tex = r"""\begin{figure}\begin{tabular}{c} a \\ 1 \\ \end{tabular}\caption{A figure}\end{figure}
\begin{table}\caption{Two parts}
\begin{subtable}{.5\linewidth}\caption{left}\begin{tabular}{lc} M & A \\ \hline x & 1.0 \\ \end{tabular}\end{subtable}
\begin{subtable}{.5\linewidth}\caption{right}\begin{tabular}{lc} M & B \\ \hline y & 2.0 \\ \end{tabular}\end{subtable}
\end{table}
\begin{table*}\begin{tabular}{lc} M & C \\ \hline z & 3.0 \\ \end{tabular}\caption{Next}\label{tab:next}\end{table*}"""
    fig, left, right, nxt = tables_of(tex)
    assert fig.number is None and fig.name.startswith("table at main.tex:1")  # in a figure: no table number
    assert (left.number, right.number) == (1, 1)  # a subtable's caption is not a new table
    assert (nxt.number, nxt.label, nxt.caption) == (2, "tab:next", "Next")


def test_cells() -> None:
    tex = r"""\begin{tabular}{lcccc}
Model & BLEU $\uparrow$ & FID $\downarrow$ & Params & Pair \\ \midrule
\textsc{Big}\textsuperscript{\dag} & \textbf{28.4} (+1.2) & 3.1\% & 125M & 89.3/82.1 \\
Small & -- & {\bf 2.9} & 60M & 85.0/80.0 \\
\end{tabular}"""
    (t,) = tables_of(tex)
    big, small = t.rows[1], t.rows[2]
    assert big[0].text == "Big†" and big[1].value == 28.4 and big[1].bold and big[2].percent
    assert big[3].value is None  # 125M: a size, not a result
    assert big[4].numbers == [89.3, 82.1] and big[4].value == 89.3
    assert small[1].value is None and small[2].bold
    assert [direction(k) for k in t.columns()] == ["", "higher", "lower", "lower", ""]


def test_compare_finds_one_model_across_papers(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    (other / "main.tex").write_text(
        r"""\documentclass{article}\begin{document}
\begin{table}\caption{ImageNet results}\begin{tabular}{lcc} Model & top-1 err. & Top-1 \\ \hline
ResNet50 & 23.9 & 76.1 \\ SE-ResNet-50 & 22.1 & 77.9 \\ ResNet-50-D & 21.0 & 79.0 \\ \end{tabular}\end{table}
\end{document}""",
        encoding="utf-8",
    )
    rows, cols = [pattern("ResNet-50")], [pattern("top-1", strict=False)]
    found = find(read_project(FIXTURE / "main.tex"), rows, cols) + find(read_project(other / "main.tex"), rows, cols)
    assert [(f.value, f.row) for f in found] == [(76.1, "Supervised | ResNet-50"), (78.3, "Ours | ResNet-50"), (23.9, "ResNet50"), (76.1, "ResNet50")]
    assert [f.better for f in found][2:] == ["lower", "higher"]  # the error rate is said to be one
    assert find(read_project(other / "main.tex"), rows, cols, [pattern("CIFAR", strict=False)]) == []  # a caption filter


def test_unpacking_is_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in [
            ("main.tex", b"\\documentclass{x}\\begin{document}\\end{document}"),
            ("../evil.tex", b"x"),
            ("/abs.tex", b"x"),
            ("fig.png", b"x"),
        ]:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    written = extract(buf.getvalue(), tmp_path / "src")
    assert [p.name for p in written] == ["main.tex"]  # nothing outside the folder, nothing but .tex-like files
    assert not (tmp_path / "evil.tex").exists()
    monkeypatch.setattr(source, "MAX_UNPACKED", 10)
    with pytest.raises(SourceError, match="unpacks to more than"):
        extract(buf.getvalue(), tmp_path / "small")
    with pytest.raises(SourceError, match="damaged"):
        extract(b"\x1f\x8b" + b"not gzip", tmp_path / "bad")


def test_inputs_stay_in_the_project(tmp_path: Path) -> None:
    (tmp_path / "secret.tex").write_text("SECRET", encoding="utf-8")
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "main.tex").write_text(
        "\\documentclass{a}\\begin{document}\\input{../secret}\\input{/etc/passwd}\\input{part}\\end{document}", encoding="utf-8"
    )
    (proj / "part.tex").write_text("inside", encoding="utf-8")
    assert find_main(proj) == proj / "main.tex"
    paper = read_project(proj / "main.tex")
    assert [f for f, _ in paper.files] == ["main.tex", "part.tex"]


def test_the_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["extract", str(FIXTURE)]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert [t["table"] for t in doc["tables"]] == ["Table 1", "Table 2"] and doc["tables"][0]["rows"][2]["cells"][2]["value"] == 78.3
    assert cli.main(["extract", str(FIXTURE), "--format", "md", "--table", "1"]) == 0
    md = capsys.readouterr().out
    assert "**78.3±0.2**" in md and "Table 2" not in md
    assert cli.main(["extract", str(FIXTURE), "--format", "csv"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("paper,table,caption,row,column,text,value") and any(",78.3,0.2,1,0,main.tex,15" in x for x in lines)
    assert cli.main(["compare", str(FIXTURE), "--row", "ResNet-50", "--col", "Top-1"]) == 0
    out = capsys.readouterr().out
    assert "76.1" in out and "78.3 ± 0.2 (bold)" in out and "from 76.1 to 78.3" in out
    assert cli.main(["extract", str(FIXTURE), "--table", "9"]) == 1
    assert "no tables found numbered 9" in capsys.readouterr().err
    assert cli.main(["extract", "not-a-paper"]) == 2
    assert "not an arXiv id" in capsys.readouterr().err
    # an arXiv id: fetched (here, a made-up source), read, and the temporary folder removed
    seen: list[Path] = []

    def fake_fetch(aid: str, into: Path, timeout: float = 60.0) -> None:
        seen.append(into)
        (into / "main.tex").write_text((FIXTURE / "main.tex").read_text(encoding="utf-8").replace("\\input{appendix}", ""), encoding="utf-8")

    monkeypatch.setattr(source, "fetch", fake_fetch)
    assert cli.main(["extract", "arXiv:2401.00001v2", "--format", "md"]) == 0
    assert "# 2401.00001v2 (https://arxiv.org/abs/2401.00001v2)" in capsys.readouterr().out
    assert seen and not seen[0].exists()


def test_two_tables_side_by_side_in_one_float() -> None:
    # ResNet's Tables 4 and 5: one table float, two minipages, each with its own caption and label
    tex = r"""\begin{table}
\begin{minipage}{.5\linewidth}\begin{tabular}{lc} M & e \\ \hline a & 1.0 \\ \end{tabular}\caption{Single models.}\label{tab:single}\end{minipage}
\begin{minipage}{.5\linewidth}\begin{tabular}{lc} M & e \\ \hline b & 2.0 \\ \end{tabular}\caption{Ensembles.}\label{tab:ensemble}\end{minipage}
\end{table}
\begin{table}\begin{tabular}{lc} M & e \\ \hline c & 3.0 \\ \end{tabular}\caption{After.}\end{table}"""
    single, ensemble, after = tables_of(tex)
    assert (single.number, single.label, single.caption) == (1, "tab:single", "Single models.")
    assert (ensemble.number, ensemble.label, ensemble.caption) == (2, "tab:ensemble", "Ensembles.")
    assert after.number == 3


def test_layout_tabulars_and_text_tables() -> None:
    tex = r"""\begin{figure}\begin{tabular}{ll}\toprule \includegraphics{a.png} & \includegraphics{b.png} \\ \bottomrule\end{tabular}\caption{Plots}\end{figure}
\begin{table}\caption{Prompts}\begin{tabular}{l}\toprule Context \\ \midrule The cat sat. \\ It was warm. \\ \bottomrule\end{tabular}\end{table}
\begin{table}\caption{Words only}\begin{tabular}{ll} Task & Prompt \\ QA & Answer it. \\ NLI & Does it follow? \\ \bottomrule\end{tabular}\end{table}"""
    prompts, words = tables_of(tex)  # the figure's tabular of images is not a table
    assert prompts.header_rows == 1 and [k for _, k in prompts.body()] == ["The cat sat.", "It was warm."]
    assert words.header_rows == 0  # no rule under a header, no results: the closing rule does not make all rows a header
    assert len(words.body()) == 3


def test_odd_sources(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    snippets = tmp_path / "tables"
    snippets.mkdir()
    (snippets / "b.tex").write_text(
        r"\begin{table}\caption{B}\begin{tabular}{lc} M & A \\ \hline x & 2.0 \\ \end{tabular}\end{table}", encoding="utf-8"
    )
    (snippets / "a.tex").write_text(
        r"\begin{table}\caption{A}\begin{tabular}{lc} M & A \\ \hline x & 1.0 \\ \end{tabular}\end{table}", encoding="utf-8"
    )
    assert cli.main(["extract", str(snippets), "--format", "csv"]) == 0  # no main file: every .tex file, in name order
    out = capsys.readouterr().out
    assert out.index(",1.0,") < out.index(",2.0,")
    assert cli.main(["extract", str(tmp_path / "nope.tex")]) == 2
    assert "no such file or folder" in capsys.readouterr().err
    assert cli.main(["extract", str(tmp_path / "empty")]) == 2
    assert cli.main(["compare", str(FIXTURE), "--row", "BERT", "--col", "Top-1"]) == 1
    assert "nothing matched --row BERT in a column named Top-1" in capsys.readouterr().err
    assert cli.main(["compare", str(FIXTURE), "--row=---", "--col", "Top-1"]) == 2
    assert "no words or numbers" in capsys.readouterr().err


def test_review_round_2_numbering(tmp_path: Path) -> None:
    # a caption after its subtables, far into the file, is the table's
    tex = (
        "\n" * 300
        + r"""\begin{table}
\begin{subtable}{.5\linewidth}\caption{a}\begin{tabular}{lc} M & A \\ \hline x & 1.0 \\ \end{tabular}\end{subtable}
\begin{subtable}{.5\linewidth}\caption{b}\begin{tabular}{lc} M & A \\ \hline y & 2.0 \\ \end{tabular}\end{subtable}
\caption{Main}\label{tab:main}\end{table}"""
    )
    a, b = tables_of(tex)
    assert (a.number, a.caption, a.label) == (b.number, b.caption, b.label) == (1, "Main", "tab:main")
    # a table in an \input file is numbered where the file is included
    proj = tmp_path / "p"
    proj.mkdir()
    tab = lambda c: r"\begin{table}\caption{CAP}\begin{tabular}{lc} M & A \\ \hline x & 1.0 \\ \end{tabular}\end{table}".replace("CAP", c)  # noqa: E731
    (proj / "main.tex").write_text(
        r"\documentclass{a}\begin{document}" + tab("First") + r"\input{t2}" + tab("Third") + r"\end{document}", encoding="utf-8"
    )
    (proj / "t2.tex").write_text(tab("Second"), encoding="utf-8")
    paper = read_project(proj / "main.tex")
    assert sorted((t.number, t.caption) for t in find_tables(paper.files, paper.includes)) == [(1, "First"), (2, "Second"), (3, "Third")]
    # a table captioned with \captionof{table} in a figure's minipage is numbered, and so the next one is Table 2
    tex = r"""\begin{figure}\begin{minipage}{.5\linewidth}\begin{tabular}{lc} M & A \\ \hline x & 1.0 \\ \end{tabular}\captionof{table}{Side}\end{minipage}\end{figure}
""" + tab("Next")
    side, nxt = tables_of(tex)
    assert (side.number, side.caption, nxt.number) == (1, "Side", 2)


def test_review_round_2_parsing() -> None:
    # a tabular nested in a cell: the outer table keeps every row, the inner one is the cell's text
    (t,) = tables_of(r"""\begin{tabular}{lc} Model & Acc. \\ \hline
\begin{tabular}{c} Big \\ model \end{tabular} & 1.0 \\ Ours & 2.0 \\ \end{tabular}""")
    assert [k for _, k in t.body()] == ["Big model", "Ours"] and t.rows[2][1].value == 2.0
    # a rule's arguments are its own: the next cell is not swallowed
    (t,) = tables_of(r"""\begin{tabular}{lc} Model & Acc. \\ \hline {\bf Ours} & 2.0 \\ \cline{1-2} {\em Two} & 3.0 \\
\addlinespace {\it Three} & 4.0 \\ \rowcolor{gray!20}{\bf Four} & 5.0 \\ \rowcolor[HTML]{EEEEEE} Five & 6.0 \\ \end{tabular}""")
    assert [k for _, k in t.body()] == ["Ours", "Two", "Three", "Four", "Five"]
    # a column spec with braces in \multicolumn; a spanning header in the only header row
    (t,) = tables_of(r"""\begin{tabular}{lcc} Model & \multicolumn{2}{@{}c@{}}{ImageNet} \\ \hline x & 1.0 & 2.0 \\ \end{tabular}""")
    assert t.columns() == ["Model", "ImageNet", "ImageNet (2)"]
    # \multirow{-2}: the text is written in the last row of its span and covers the row above
    (t,) = tables_of(r"""\begin{tabular}{llc} G & M & A \\ \hline & a & 1.0 \\ \multirow{-2}{*}{Group} & b & 2.0 \\ \end{tabular}""")
    assert [k for _, k in t.body()] == ["Group | a", "Group | b"]
    # a column of years describes the rows; it is not a result
    (t,) = tables_of(r"""\begin{tabular}{lcc} Model & Year & Acc. \\ \hline BERT & 2019 & 80.1 \\ T5 & 2020 & 82.3 \\ \end{tabular}""")
    assert [k for _, k in t.body()] == ["BERT | 2019", "T5 | 2020"] and t.rows[1][2].value == 80.1


def test_review_round_2_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    risky = tmp_path / "risky"
    risky.mkdir()
    (risky / "main.tex").write_text(
        r"\documentclass{a}\begin{document}\begin{table}\caption{x}\begin{tabular}{lc} M & A \\ \hline =HYPERLINK(1) & 1.0 \\ -0.5 & 2.0 \\ \end{tabular}\end{table}\end{document}",
        encoding="utf-8",
    )
    assert cli.main(["extract", str(risky), "--format", "csv"]) == 0
    out = capsys.readouterr().out
    assert ",'=HYPERLINK(1)," in out and ",'=" not in out.replace(",'=HYPERLINK", "")  # a formula is quoted, a number not
    # one paper that cannot be read does not stop the others; the run says so with exit 2
    assert cli.main(["extract", str(FIXTURE), str(tmp_path / "nope.tex"), "--format", "md"]) == 2
    io = capsys.readouterr()
    assert "Table 1" in io.out and "no such file or folder" in io.err
