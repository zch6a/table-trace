r"""A paper's tables as data: each table's number, label and caption; its rows and cells; in each cell the text as
printed, the numbers it shows, the result (the first number, when the cell is a result), its ± spread, whether it
is bold or underlined (the authors' best and second best), and the file and line it is on.

Handles tabular, tabular*, tabularx, tabulary, longtable, array and tblr; \multicolumn (the text in its first
column) and \multirow (the name filled down the rows it spans); booktabs rules and \hline; the paper's own macros.

From paper-proof's table reader (the same author's MIT project), extended.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .text import _matching, macros, plain

ENV = re.compile(r"\\begin\{(tabular\*?|tabularx|tabulary|longtable|array|tblr)\}")
FLOAT = re.compile(r"\\begin\{(table\*?|sidewaystable\*?|wraptable|subtable)\}")
RULE = re.compile(
    r"\\(?:toprule|midrule|bottomrule|hline|specialrule|cmidrule|cline|hdashline|Xhline|Xcline|hhline|thickhline|addlinespace|endhead|endfirsthead|endfoot|endlastfoot|"
    r"rowcolor|rowcolors|noalign)\b(?:\s*\([^)]*\))?(?:\s*\{[^}]*\})*(?:\s*\[[^\]]*\])?"
)
FULL_RULE = re.compile(r"\\(?:toprule|midrule|bottomrule|hline|specialrule|hdashline|Xhline|thickhline|hhline)\b")
MAX_SPAN = 64  # \multicolumn{3000000}{c}{x} must not allocate millions of cells
MAX_ROWS = 5000
BOLD = re.compile(r"\\(?:textbf|mathbf|boldsymbol|bm|pmb|bfseries)\b|\{\s*\\bf\b|\\bf\b|\\cellcolor\{best\}|\\best\b|\\first\b")
UNDERLINE = re.compile(r"\\(?:underline|uline|ul|underbar|second|secondbest)\b")
NUMBER = re.compile(r"(?<![\w.])[-−]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)(?![\d])")
# commands between rows whose braces nest (\noalign{\global\savewidth\arrayrulewidth ...}): blanked whole
BRACED = re.compile(
    r"\\(?:noalign|specialrule|Xhline|Xcline|hhline|arrayrulecolor|rowcolors|cmidrule(?:\([^)]*\))?|addlinespace|vspace|hspace)\s*(?:\[[^\]]*\])?\s*\{"
)
LOWER = re.compile(
    r"\b(?:err(?:or)?s?|err\.|loss|perplexity|ppl|fid|kid|wer|cer|ter|mse|mae|rmse|nll|bpd|bpc|eer|latency|time|runtime|"
    r"seconds?|ms|hours?|params?|parameters|flops|macs|memory|mem|cost|chamfer|lpips|distance|regret|abs ?rel|sq ?rel)\b",
    re.I,
)
HIGHER = re.compile(
    r"\b(?:acc(?:uracy)?|acc\.|top-?[15]|bleu|rouge(?:-\w+)?|meteor|chrf|f1|f-?score|auc|auroc|ap|map|ap50|ap75|iou|miou|"
    r"precision|recall|psnr|ssim|ndcg|mrr|hits?@?\d*|pass@?\d*|win ?rate|success|em|exact match|r@\d+|"
    r"spearman|pearson|kendall|correlation|reward|return|bertscore|cider|spice|inception score|throughput|fps)\b",
    re.I,
)


def direction(header: str) -> str:
    r"""'higher', 'lower' or '' for a column header (an arrow, or the metric's name; an error rate is lower).

    >>> direction(r"BLEU ↑"), direction("FID"), direction("top-1 err."), direction("Top-1 Acc."), direction("Model")
    ('higher', 'lower', 'lower', 'higher', '')
    """
    if re.search(r"↑|higher is better|\(\+\)", header, re.I):
        return "higher"
    if re.search(r"↓|lower is better", header, re.I):
        return "lower"
    lo, hi = LOWER.search(header), HIGHER.search(header)
    if lo and (not hi or re.search(r"err", header, re.I)):  # "top-1 err." is an error rate, not an accuracy
        return "lower"
    return "higher" if hi else ""


def _blank_braced(row: str) -> str:
    """Commands between rows blanked with their (nested) braces, so their insides never reach a cell."""
    out, i = [], 0
    for m in BRACED.finditer(row):
        if m.start() < i:
            continue
        j = m.end()
        for _ in range(3):  # \specialrule{w}{a}{b}: up to three groups
            end = _matching(row, j)
            if end < 0:
                break
            j = end + 1
            k = re.match(r"\s*\{", row[j:])
            if not k or not m.group(0).startswith(("\\specialrule", "\\noalign")) or m.group(0).startswith("\\noalign"):
                break
            j += k.end()
        out += [row[i : m.start()], " " * (j - m.start())]
        i = j
    out.append(row[i:])
    return "".join(out)


@dataclass
class Cell:
    raw: str  # the LaTeX of the cell
    text: str  # as printed
    line: int
    value: float | None = None  # the result the cell shows (its first number), None when it is not a result
    decimals: int = 0
    spread: float | None = None  # a ± after the result
    percent: bool = False
    bold: bool = False
    underline: bool = False
    numbers: list[float] = field(default_factory=list)  # every number in the cell ("89.3/82.1": two)
    span: int = 1  # columns a \multicolumn covers (the cells after it are empty)
    filled: bool = False  # the text comes from a \multirow above


@dataclass
class Table:
    file: str
    line: int  # where the tabular begins
    number: int | None  # the table's number in the paper (its floats with a caption, in order); None outside a table
    label: str
    caption: str
    rows: list[list[Cell]] = field(default_factory=list)
    header_rows: int = 0

    @property
    def name(self) -> str:
        return f"Table {self.number}" if self.number else self.label or f"table at {self.file}:{self.line}"

    def row_start(self, i: int) -> int:
        """The first cell after the row's name cells: its first result."""
        r = self.rows[i]
        return next((j for j, c in enumerate(r) if c.value is not None), len(r))

    def columns(self) -> list[str]:
        """A key for each column: its header (a spanning header filled in over the columns it spans), else its
        number."""
        width = max((len(r) for r in self.rows), default=0)
        head = []
        for k, r in enumerate(self.rows[: self.header_rows]):
            texts = [r[j].text if j < len(r) else "" for j in range(width)]
            if k < self.header_rows - 1:  # a spanning header: \multicolumn leaves empty cells after its text
                j = 0
                while j < len(r):
                    for s in range(1, r[j].span):
                        if j + s < width:
                            texts[j + s] = texts[j]
                    j += max(1, r[j].span)
            head.append(texts)
        keys = [" ".join(dict.fromkeys(h[j] for h in head if h[j])).strip() or f"column {j + 1}" for j in range(width)]
        return _dedupe(keys)

    def body(self) -> list[tuple[int, str]]:
        """(row index, key) of the body rows: the key is the row's name cells joined, else its position."""
        out = []
        for i in range(self.header_rows, len(self.rows)):
            r = self.rows[i]
            if not any(c.text for c in r):
                continue
            names = [c.text for c in r[: self.row_start(i)] if c.text]
            out.append((i, " | ".join(names) or f"row {i + 1}"))
        keys = _dedupe([k for _, k in out])
        return [(i, k) for (i, _), k in zip(out, keys, strict=True)]


def _dedupe(keys: list[str]) -> list[str]:
    seen: Counter[str] = Counter()
    out = []
    for k in keys:
        seen[k.lower()] += 1
        out.append(k if seen[k.lower()] == 1 else f"{k} ({seen[k.lower()]})")
    return out


def read_cell(raw: str, line: int, defs: dict[str, tuple[int, str]] | None = None) -> Cell:
    r"""A cell: its text, its numbers, and the result it shows.

    >>> c = read_cell(r"\textbf{75.3}$\pm$0.2", 1); (c.value, c.spread, c.bold, c.decimals)
    (75.3, 0.2, True, 1)
    >>> c = read_cell(r"\underline{92.1}\%", 1); (c.value, c.percent, c.underline)
    (92.1, True, True)
    >>> [read_cell(s, 1).value for s in ["ResNet-50", "--", "125M", "28.4 (+1.2)", "89.3/82.1", ".93", "1,024"]]
    [None, None, None, 28.4, 89.3, 0.93, 1024.0]
    """
    expanded = raw if not defs else _expand_marks(raw, defs)
    text = plain(raw, defs)
    c = Cell(raw.strip(), text, line, bold=bool(BOLD.search(expanded)), underline=bool(UNDERLINE.search(expanded)))
    c.numbers = [float(n.replace("−", "-").replace(",", "")) for n in NUMBER.findall(text)]
    m = re.match(r"\s*[(\[]?\s*([-−]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+))", text)
    if not m:
        return c
    rest = text[m.end() :].strip()
    # only what decorates a result may follow: ± spread, (delta), %, marks, a second result after /
    if rest and not re.match(r"(?:[(\[)\]±%*†‡§¶⋆∗/]|\+/-|\+|−|-\s*\d|[a-z]?\s*$|±)", rest):
        return c  # 125.0M, 50 epochs, 3B: not a result
    if re.match(r"[A-Za-z]{2,}", rest):
        return c
    s = m.group(1).replace("−", "-").replace(",", "")
    c.value = float(s)
    c.decimals = len(s.split(".")[1]) if "." in s else 0
    c.percent = rest.startswith("%")
    sp = re.match(r"%?\s*(?:±|\+/-|\(\s*±)\s*([-−]?(?:\d+(?:\.\d+)?|\.\d+))", rest)
    if sp:
        c.spread = float(sp.group(1).replace("−", "-"))
    return c


def _expand_marks(raw: str, defs: dict[str, tuple[int, str]]) -> str:
    """The cell with the paper's macros expanded, to see bold and underline behind \\best{} or \\sota{}."""
    from .text import expand

    return expand(raw, defs)


def _split(s: str, sep: str) -> list[tuple[str, int]]:
    """Split at `sep` outside braces (and not escaped), with each piece's offset."""
    out, depth, start, i = [], 0, 0, 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            if sep == "\\\\" and depth == 0 and (s.startswith("\\\\", i) or s.startswith("\\tabularnewline", i)):
                out.append((s[start:i], start))
                i += 2 if s.startswith("\\\\", i) else len("\\tabularnewline")
                m = re.match(r"\s*\*?\s*\[[^\]]*\]", s[i:])  # an optional [2pt] after \\
                if m:
                    i += m.end()
                start = i
                continue
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == sep and depth == 0:
            out.append((s[start:i], start))
            start = i + 1
        i += 1
    out.append((s[start:], start))
    return out


MULTICOLUMN = re.compile(r"\s*\\multicolumn\s*\{(\d+)\}\s*\{[^}]*\}\s*\{")
MULTIROW = re.compile(r"\s*\\multirow\s*(?:\[[^\]]*\])?\s*\{(-?\d+)\}\s*(?:\[[^\]]*\])?\s*\{[^}]*\}\s*(?:\[[^\]]*\])?\s*\{")


def _cells(row: str, offset: int, text: str, defs: dict[str, tuple[int, str]]) -> tuple[list[Cell], dict[int, int]]:
    """The row's cells, and the \\multirow spans it starts: {column: rows below to fill}."""
    cells: list[Cell] = []
    spans: dict[int, int] = {}
    for raw, off in _split(row, "&"):
        span, down = 1, 0
        m = MULTICOLUMN.match(raw)
        if m:
            span = max(1, min(int(m.group(1)), MAX_SPAN))
            end = _matching(raw, m.end())
            raw = raw[m.end() : end if end > 0 else len(raw)]
        m = MULTIROW.match(raw)
        if m:
            down = min(abs(int(m.group(1))), MAX_ROWS) - 1
            end = _matching(raw, m.end())
            raw = raw[m.end() : end if end > 0 else len(raw)]
        line = text.count("\n", 0, offset + off + len(raw) - len(raw.lstrip())) + 1
        c = read_cell(raw, line, defs)
        c.span = span
        if down > 0 and c.text:
            spans[len(cells)] = down
        cells.append(c)
        cells.extend(Cell("", "", line) for _ in range(span - 1))
    return cells, spans


@dataclass
class _Float:
    start: int
    end: int
    captions: list[tuple[int, str, str]]  # (position, caption, label) of each table caption in it, in order


def _floats(text: str) -> list[_Float]:
    """The outermost table floats of a file with their captions: a float may hold several tables side by side, each
    with its own caption (minipages); captions inside a subtable are sub-captions of one table, not new tables."""
    out: list[_Float] = []
    for m in FLOAT.finditer(text):
        env = m.group(1)
        if env == "subtable" or any(f.start < m.start() < f.end for f in out):
            continue
        end = text.find(f"\\end{{{env}}}", m.end())
        if end < 0:
            continue
        subs = [(a.start(), text.find("\\end{subtable}", a.end())) for a in re.finditer(r"\\begin\{subtable\}", text[m.start() : end])]
        subs = [(m.start() + a, m.start() + b) for a, b in subs if b > 0]
        caps = []
        for c in re.finditer(r"\\caption(?:of\s*\{table\})?\s*(?:\[[^\]]*\])?\s*\{", text[m.start() : end]):
            pos = m.start() + c.start()
            if any(a < pos < b for a, b in subs):
                continue
            close = _matching(text, m.start() + c.end())
            cap = text[m.start() + c.end() : close] if close > 0 else ""
            caps.append((pos, cap, ""))
        labels = [(m.start() + lm.start(), lm.group(1)) for lm in re.finditer(r"\\label\{([^}]+)\}", text[m.start() : end])]
        labels = [(pos, lab) for pos, lab in labels if not any(a < pos < b for a, b in subs)]
        # each caption's label: the nearest one (a label is written just after its caption, or just before)
        caps = [(pos, cap, min(labels, key=lambda lab: abs(lab[0] - pos))[1] if labels else "") for pos, cap, _ in caps]
        if len(caps) > 1 and len(labels) < len(caps):
            caps = [(pos, cap, lab if k < len(labels) else "") for k, (pos, cap, lab) in enumerate(caps)]
        out.append(_Float(m.start(), end, caps))
    return out


def _caption_of(f: _Float, tabulars: list[int], at: int) -> int | None:
    """Which of the float's captions a tabular has: in order when there are as many tabulars as captions, else the
    nearest."""
    if not f.captions:
        return None
    if len(tabulars) == len(f.captions):
        return tabulars.index(at)
    return min(range(len(f.captions)), key=lambda k: abs(f.captions[k][0] - at))


def find_tables(files: list[tuple[str, str]]) -> list[Table]:
    """Every tabular of a paper, in reading order, with the number of the table it is in."""
    defs: dict[str, tuple[int, str]] = {}
    for _, text in files:
        defs.update({k: v for k, v in macros(text).items() if k not in defs})
    tables: list[Table] = []
    number = 0
    for file, text in files:
        floats = _floats(text)
        first_number: list[int] = []
        for f in floats:
            first_number.append(number + 1)
            number += len(f.captions)
        starts = [m.start() for m in ENV.finditer(text)]
        for m in ENV.finditer(text):
            env = m.group(1)
            i = m.end()
            for _ in range(2 if env in ("tabular*", "tabularx", "tabulary") else 1):  # a width, then the column spec
                mm = re.match(r"\s*(?:\[[^\]]*\])?\s*\{", text[i:])
                if not mm:
                    break
                close_spec = _matching(text, i + mm.end())
                i = close_spec + 1 if close_spec > 0 else i
            close = text.find(f"\\end{{{env}}}", i)
            if close < 0:
                continue
            fi = next((k for k, f in enumerate(floats) if f.start < m.start() < f.end), None)
            num, label, caption = None, "", ""
            if fi is not None:
                f = floats[fi]
                ci = _caption_of(f, [s for s in starts if f.start < s < f.end], m.start())
                if ci is not None:
                    num = first_number[fi] + ci
                    caption, label = plain(f.captions[ci][1], defs), f.captions[ci][2]
            t = Table(file, text.count("\n", 0, m.start()) + 1, num, label, caption)
            _fill(t, text, i, close, defs)
            if any(c.text for r in t.rows for c in r):  # a tabular of images only lays out a figure: not a table
                tables.append(t)
    return tables


def _rule_macros(defs: dict[str, tuple[int, str]]) -> tuple[re.Pattern[str] | None, set[str]]:
    r"""The paper's macros that draw a rule (\thickhline = \noalign{...}\hline...): a pattern for their uses, and
    which of them are full-width rules."""
    names = {n for n, (k, body) in defs.items() if k == 0 and (RULE.search(body) or BRACED.search(body)) and not re.search(r"&|\\\\", body)}
    if not names:
        return None, set()
    full = {n for n in names if FULL_RULE.search(defs[n][1])}
    return re.compile(r"\\(" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r")(?![A-Za-z@])(?:\s*\{\})?"), full


def _fill(t: Table, text: str, start: int, close: int, defs: dict[str, tuple[int, str]]) -> None:
    body = text[start:close]
    first_rule_row = None
    rule_use, full_rules = _rule_macros(defs)
    pending: dict[int, tuple[str, int]] = {}  # column -> (text, rows left) from a \multirow
    for row, off in _split(body, "\\\\")[:MAX_ROWS]:
        uses = list(rule_use.finditer(row)) if rule_use else []
        full = any(FULL_RULE.match(r.group(0)) for r in RULE.finditer(row)) or any(u.group(1) in full_rules for u in uses)
        if full and t.rows and first_rule_row is None:
            first_rule_row = len(t.rows)
        if rule_use:
            row = rule_use.sub(lambda u: " " * len(u.group(0)), row)  # same length: the cells' lines stay right
        clean = RULE.sub(lambda r: " " * len(r.group(0)), _blank_braced(row))
        if not clean.strip():
            continue
        cells, spans = _cells(clean, start + off, text, defs)
        for j, (txt, left) in list(pending.items()):
            if j < len(cells) and not cells[j].text:
                cells[j].text, cells[j].filled = txt, True
            pending[j] = (txt, left - 1)
            if left - 1 <= 0:
                del pending[j]
        for j, down in spans.items():
            pending[j] = (cells[j].text, down)
        t.rows.append(cells)
    if first_rule_row == len(t.rows):
        first_rule_row = None  # the rule under the last row closes the table; it is not the line under a header
    # The header: the rows above the first full rule when it comes early (a header may hold numbers: sizes, shots);
    # otherwise the leading rows without a result.
    leading = next((k for k, r in enumerate(t.rows) if any(c.value is not None for c in r)), len(t.rows))
    if first_rule_row is not None and (first_rule_row <= 3 or first_rule_row <= leading):
        t.header_rows = first_rule_row
    else:
        t.header_rows = leading if leading < len(t.rows) else 0
