r"""How each paper evaluated on a benchmark: the settings that make two scores comparable or not.

    table-trace settings 2307.09288 2302.13971 --benchmark MMLU

For each paper, the sentences (and table captions) that name the benchmark are read for:

- shots: "5-shot", "zero-shot", "few-shot (k=8)";
- chain of thought: "chain-of-thought", "CoT";
- decoding: greedy, temperature, top-p / nucleus, beam search, sampling, maj@k, pass@k;
- harness: lm-evaluation-harness, OpenCompass, HELM, EvalPlus, the official evaluation script;
- metric: accuracy, exact match, F1, pass@1, BLEU, ROUGE.

Each value is shown with the file and line it was read from; a setting a paper does not state is "not stated", which
is itself the finding: the score cannot be compared on it. Rules on the words; nothing is guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .source import Paper
from .text import plain

KINDS = ("shots", "cot", "decoding", "harness", "metric")
RULES: dict[str, list[tuple[re.Pattern[str], str | None]]] = {
    "shots": [
        (re.compile(r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|sixteen|\d{1,2})[\s-]shots?\b", re.I), None),
        (re.compile(r"\bk\s*=\s*(\d{1,2})\s*(?:shots|examples|demonstrations|in-context)", re.I), None),
        (re.compile(r"\b(few)[\s-]shot\b", re.I), None),
        (
            re.compile(
                r"\b(one|two|three|four|five|six|seven|eight|nine|ten|sixteen|\d{1,2})\s+(?:[\w-]+\s+){0,2}?(?:exemplars|demonstrations|in-context\s+examples)\b",
                re.I,
            ),
            None,
        ),
    ],
    "cot": [(re.compile(r"\bchain[\s-]of[\s-]thoughts?\b|\bCoT\b"), "chain-of-thought")],
    "decoding": [
        (re.compile(r"\bgreedy(?:\s+decoding)?\b", re.I), "greedy"),
        (re.compile(r"\btemperature\s*(?:of\s*|=\s*|\(\s*T\s*=\s*)?(\d(?:\.\d+)?)", re.I), "temperature {0}"),
        (re.compile(r"\b(?:top-?p|nucleus)\s*(?:sampling)?\s*(?:of\s*|=\s*|p\s*=\s*)?(0?\.\d+|1\.0)", re.I), "top-p {0}"),
        (re.compile(r"\bbeam\s+(?:search\s+)?(?:size|width)?\s*(?:of\s*|=\s*)?(\d{1,2})", re.I), "beam {0}"),
        (re.compile(r"\bmaj@(\d+)", re.I), "maj@{0}"),
        (re.compile(r"\bmajority\s+vot(?:e|ing)\b", re.I), "majority vote"),
        (re.compile(r"\bpass@(\d+)", re.I), "pass@{0}"),
        (re.compile(r"\bself-consistency\b", re.I), "self-consistency"),
    ],
    "harness": [
        (
            re.compile(r"\blm[\s-]eval(?:uation)?[\s-]harness\b|\blm-eval\b|\bEleuther(?:AI)?'?s?\s+(?:evaluation\s+)?harness\b", re.I),
            "lm-evaluation-harness",
        ),
        (re.compile(r"\bOpenCompass\b", re.I), "OpenCompass"),
        (re.compile(r"\bHELM\b"), "HELM"),
        (re.compile(r"\bEvalPlus\b", re.I), "EvalPlus"),
        (re.compile(r"\bofficial\s+(?:evaluation\s+)?(?:script|code|implementation|toolkit|protocol)\b", re.I), "the official script"),
        (re.compile(r"\bVLMEvalKit\b|\blmms-eval\b", re.I), None),
    ],
    "metric": [
        (re.compile(r"\bexact[\s-]match\b|\bEM\b"), "exact match"),
        (re.compile(r"\baccuracy\b|\bacc\.", re.I), "accuracy"),
        (re.compile(r"\bF1\b"), "F1"),
        (re.compile(r"\bBLEU\b"), "BLEU"),
        (re.compile(r"\bROUGE(?:-[L12])?\b"), None),
    ],
}
NUM_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "sixteen": "16",
}


@dataclass
class Evidence:
    value: str
    file: str
    line: int
    sentence: str


@dataclass
class Settings:
    paper: str
    mentions: int = 0  # sentences naming the benchmark
    found: dict[str, list[Evidence]] = field(default_factory=dict)

    def values(self, kind: str) -> list[str]:
        return list(dict.fromkeys(e.value for e in self.found.get(kind, [])))


def _sentences(text: str) -> list[tuple[int, str]]:
    """(offset, sentence) of a file's text, sentences split on . ! ? followed by a space and a capital, or a blank line."""
    out, start = [], 0
    for m in re.finditer(r"(?<=[.!?])\s+(?=[A-Z\\])|\n\s*\n", text):
        out.append((start, text[start : m.start()]))
        start = m.end()
    out.append((start, text[start:]))
    return out


def _value(kind: str, m: re.Match[str], label: str | None) -> str:
    if kind == "shots":
        n = m.group(1).lower()
        return f"{NUM_WORDS.get(n, n)}-shot" if n != "few" else "few-shot"
    if label is None:
        return m.group(0)
    return label.format(*(g or "" for g in m.groups()))


FLOATS = re.compile(r"\\begin\{(table\*?|tabular\*?|tabularx|longtable|figure\*?|algorithm\*?)\}.*?\\end\{\1\}", re.S)
CAPTION = re.compile(r"\\caption\*?(?:\[[^\]]*\])?\{")


def _prose(raw: str) -> str:
    """The text with tables and figures blanked (same length: lines are kept), their captions left in as sentences."""

    def keep_caption(m: re.Match[str]) -> str:
        body = m.group(0)
        caps = []
        for c in CAPTION.finditer(body):
            depth, i = 1, c.end()
            while i < len(body) and depth:
                depth += {"{": 1, "}": -1}.get(body[i], 0)
                i += 1
            caps.append((c.start(), i))
        out = re.sub(r"[^\n]", " ", body)
        for a, b in caps:
            out = out[:a] + body[a:b] + "." + out[b + 1 :] if b < len(out) else out[:a] + body[a:b]
        return out[: len(body)]

    return FLOATS.sub(keep_caption, raw)


def _hits(kind: str, text: str) -> list[str]:
    out = []
    for rx, label in RULES[kind]:
        out += [_value(kind, m, label) for m in rx.finditer(text)]
    return list(dict.fromkeys(out))


def _nearest(text: str, benchmark: re.Pattern[str]) -> str:
    """The shot count written closest to the benchmark's name."""
    b = benchmark.search(text)
    assert b is not None
    best: tuple[int, str] | None = None
    for rx, label in RULES["shots"]:
        for m in rx.finditer(text):
            d = min(abs(m.start() - b.end()), abs(b.start() - m.end()))
            if best is None or d < best[0]:
                best = (d, _value("shots", m, label))
    assert best is not None
    return best[1]


def read(paper: Paper, benchmark: re.Pattern[str], window: int = 0) -> Settings:
    """The settings stated where the benchmark is named: in its own clause first ("MMLU (5 shot), BBH (3 shot)" gives MMLU
    5-shot), else in its sentence when the sentence states only one value; `window` adds sentences around it."""
    st = Settings(paper.name)
    for file, raw in paper.files:
        prose = _prose(raw)
        sentences = _sentences(prose)
        hits = [i for i, (_, s) in enumerate(sentences) if benchmark.search(s) and len(s) < 1500]
        st.mentions += len(hits)
        near = sorted({j for i in hits for j in range(max(0, i - window), min(len(sentences), i + window + 1))})
        for j in near:
            off, s = sentences[j]
            text = re.sub(r"\s+", " ", plain(s)).strip()
            clauses = [c for c in re.split(r"[;,]|\band\b|\(|\)", text)]
            own = " ".join(c for c in re.split(r"[;,]|\band\b", text) if benchmark.search(c))
            line = raw.count("\n", 0, off) + 1
            for kind in KINDS:
                vals = _hits(kind, own) if own else []
                if kind == "shots" and len(vals) > 1:
                    vals = [_nearest(own, benchmark)]  # "0-shot for all tasks except MMLU (5-shot)": the one next to the name
                if not vals:
                    whole = _hits(kind, text)
                    vals = whole if len(whole) == 1 else []  # several values in the sentence: whose is whose is not known
                for v in vals:
                    st.found.setdefault(kind, []).append(Evidence(v, file, line, text[:200]))
            del clauses
    return st


def differences(all_: list[Settings]) -> list[str]:
    """The settings the papers state differently, or that some state and others do not."""
    out = []
    names = {"shots": "shots", "cot": "chain of thought", "decoding": "decoding", "harness": "harness", "metric": "metric"}
    for kind in KINDS:
        stated = {s.paper: s.values(kind) for s in all_}
        distinct = {tuple(v) for v in stated.values() if v}
        silent = [p for p, v in stated.items() if not v]
        if len(distinct) > 1:
            out.append(f"{names[kind]}: " + "; ".join(f"{p}: {', '.join(v) or 'not stated'}" for p, v in stated.items()))
        elif distinct and silent:
            out.append(f"{names[kind]}: {', '.join(next(iter(distinct)))} in " + ", ".join(p for p, v in stated.items() if v)
                       + f"; not stated in {', '.join(silent)}")  # fmt: skip
    return out
