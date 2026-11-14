"""table-trace settings, on made-up papers (no network)."""

from __future__ import annotations

import re

from table_trace.cli import main
from table_trace.settings import differences, read
from table_trace.source import Paper

A = Paper(
    "paper-a",
    [
        (
            "main.tex",
            r"""We evaluate on MMLU in the 5-shot setting with greedy decoding, using lm-evaluation-harness.
On GSM8K we use eight chain-of-thought exemplars and report maj@8 accuracy.
We report 0-shot results for all tasks except MMLU (5-shot) and GSM8K (8-shot).
Of 50 random examples on GSM8K, all were correct.
\begin{table}[t]\centering
\begin{tabular}{lc} Model & MMLU \\ Ours & 70.1 \\ \end{tabular}
\caption{MMLU accuracy (5-shot), temperature 0.}
\end{table}
""",
        )
    ],
)
B = Paper(
    "paper-b",
    [
        (
            "main.tex",
            r"""We report MMLU (0 shot), BBH (3 shot), and AGI Eval (3--5 shot) with OpenCompass.
""",
        )
    ],
)


def test_settings_of_one_paper():
    s = read(A, re.compile(r"\bMMLU\b"))
    assert s.values("shots") == ["5-shot"]  # "0-shot for all tasks except MMLU (5-shot)": the one next to the name
    assert s.values("decoding")[:2] == ["greedy", "temperature 0"]
    assert s.values("harness") == ["lm-evaluation-harness"] and "accuracy" in s.values("metric")
    g = read(A, re.compile(r"\bGSM8K\b"))
    assert g.values("shots") == ["8-shot"]  # eight exemplars; not the 50 random examples of the error analysis
    assert g.values("cot") == ["chain-of-thought"] and "maj@8" in g.values("decoding")


def test_differences_and_clauses():
    b = read(B, re.compile(r"\bMMLU\b"))
    assert b.values("shots") == ["0-shot"] and b.values("harness") == ["OpenCompass"]  # MMLU's clause, not BBH's 3-shot
    diff = differences([read(A, re.compile(r"\bMMLU\b")), b])
    assert any(d.startswith("shots: paper-a: 5-shot; paper-b: 0-shot") for d in diff)
    assert any(d.startswith("harness: paper-a: lm-evaluation-harness; paper-b: OpenCompass") for d in diff)
    assert any(d.startswith("decoding: greedy, temperature 0 in paper-a; not stated in paper-b") for d in diff)


def test_cli(tmp_path, capsys):
    for p in (A, B):
        d = tmp_path / p.name
        d.mkdir()
        (d / "main.tex").write_text("\\documentclass{article}\\begin{document}\n" + p.files[0][1] + "\\end{document}\n", encoding="utf-8")
    assert main(["settings", str(tmp_path / "paper-a"), str(tmp_path / "paper-b"), "--benchmark", "MMLU"]) == 0
    out = capsys.readouterr().out
    assert "paper-a: " in out and "shots             5-shot" in out and "Differences:" in out
    assert main(["settings", str(tmp_path / "paper-a"), "--benchmark", "MMLU", "--json"]) == 0
    assert '"value": "5-shot"' in capsys.readouterr().out
