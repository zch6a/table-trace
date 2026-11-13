r"""LaTeX in a table cell as the reader sees it: the paper's own macros expanded (\newcommand, \def, with up to nine
arguments), formatting dropped, symbols as Unicode (± × † ↑ ✓), citations and references left out.
"""

from __future__ import annotations

import re

MACRO_DEF = re.compile(
    r"\\(?:re)?newcommand\*?\s*\{?\s*\\([A-Za-z@]+)\s*\}?\s*(?:\[(\d)\])?\s*(?:\[[^\]]*\])?\s*\{"
    r"|\\(?:DeclareRobustCommand|providecommand)\*?\s*\{?\s*\\([A-Za-z@]+)\s*\}?\s*(?:\[(\d)\])?\s*\{"
    r"|\\(?:g|e|x)?def\s*\\([A-Za-z@]+)\s*((?:#\d)*)\s*\{"
)
MAX_EXPANSION = 20_000  # characters a cell may grow to while macros expand
SYMBOLS = {"pm": "±", "mp": "∓", "times": "×", "dagger": "†", "ddagger": "‡", "dag": "†", "ddag": "‡", "star": "⋆", "ast": "∗",
           "uparrow": "↑", "downarrow": "↓", "Uparrow": "⇑", "Downarrow": "⇓", "rightarrow": "→", "to": "→", "leftarrow": "←",
           "checkmark": "✓", "cmark": "✓", "xmark": "✗", "approx": "≈", "sim": "~", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥",
           "infty": "∞", "cdot": "·", "circ": "∘", "bullet": "•", "S": "§", "P": "¶", "%": "%", "&": "&", "_": "_", "#": "#",
           "$": "$", "{": "{", "}": "}", "textasciitilde": "~", "textbar": "|", "degree": "°", "alpha": "α", "beta": "β",
           "gamma": "γ", "delta": "δ", "Delta": "Δ", "epsilon": "ε", "lambda": "λ", "mu": "μ", "sigma": "σ", "tau": "τ",
           "theta": "θ", "pi": "π", "phi": "φ", "omega": "ω", "ldots": "…", "dots": "…", "cdots": "⋯", "textless": "<",
           "textgreater": ">", "textpm": "±", "texttimes": "×", "textdagger": "†", "minus": "−"}  # fmt: skip
KEEP_ARG = ("textbf|textit|textsl|textsc|texttt|textrm|textsf|textup|textnormal|emph|underline|uline|ul|underbar|mathbf|mathrm|"
            "mathit|mathsf|mathtt|mathcal|mathbb|boldsymbol|bm|pmb|text|mbox|hbox|makecell|shortstack|textmd|mathnormal|"
            "operatorname|ensuremath|tablestyle|bfseries|fbox|framebox|smash|raisebox|resizebox|scalebox|adjustbox|tnote|"
            "tnotex|textsuperscript|textsubscript|mathbin|mathrel|mathop|overline|widehat|hat|tilde|bar|vec")  # fmt: skip
DROP_ARG = "cite[a-z]*|citep|citet|ref|cref|Cref|autoref|eqref|label|footnote|hspace|vspace|phantom|hphantom|vphantom|rule|color|cellcolor|rowcolor|columncolor|includegraphics|url|hyperref|tablefootnote"
NO_ARG = "bf|it|sc|tt|rm|sf|em|small|footnotesize|scriptsize|tiny|normalsize|large|Large|LARGE|huge|centering|raggedright|raggedleft|bfseries|itshape|mdseries|upshape|scshape|normalfont|noindent|quad|qquad|enspace|thinspace|negthinspace|relax|strut|null|newline|linebreak|arraybackslash|hfill|vfill|xspace|unskip|ignorespaces|displaystyle|textstyle|scriptstyle|bigstrut|cr"


def _matching(s: str, start: int) -> int:
    """The index of the brace closing the one just before `start` (-1 when it is not closed)."""
    depth, i = 0, start
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            if depth == 0:
                return i
            depth -= 1
        i += 1
    return -1


def macros(text: str) -> dict[str, tuple[int, str]]:
    r"""The macros a document defines: name -> (number of arguments, body).

    >>> macros(r"\newcommand{\ours}{\textsc{Ours}} \def\R{\mathbb{R}} \newcommand{\best}[1]{\textbf{#1}}")
    {'ours': (0, '\\textsc{Ours}'), 'R': (0, '\\mathbb{R}'), 'best': (1, '\\textbf{#1}')}
    """
    out: dict[str, tuple[int, str]] = {}
    for m in MACRO_DEF.finditer(text):
        name = m.group(1) or m.group(3) or m.group(5)
        n = int(m.group(2) or m.group(4) or 0) if not m.group(5) else len(re.findall(r"#\d", m.group(6) or ""))
        end = _matching(text, m.end())
        if end < 0 or name in ("begin", "end", "input", "include", "def", "newcommand"):
            continue
        out.setdefault(name, (n, text[m.end() : end]))  # the first definition (a \renewcommand later is rare in tables)
    return out


def _args(s: str, i: int, n: int) -> tuple[list[str], int] | None:
    args = []
    for _ in range(n):
        while i < len(s) and s[i] in " \t\n":
            i += 1
        if i < len(s) and s[i] == "{":
            end = _matching(s, i + 1)
            if end < 0:
                return None
            args.append(s[i + 1 : end])
            i = end + 1
        elif i < len(s):
            args.append(s[i])
            i += 1
        else:
            return None
    return args, i


def expand(s: str, defs: dict[str, tuple[int, str]]) -> str:
    r"""The document's macros expanded in `s` (five rounds at most, and no more than MAX_EXPANSION characters).

    >>> expand(r"\ours{} gets \best{75.3}", {"ours": (0, r"\textsc{Ours}"), "best": (1, r"\textbf{#1}")})
    '\\textsc{Ours}{} gets \\textbf{75.3}'
    """
    if not defs or "\\" not in s:
        return s
    pattern = re.compile(r"\\(" + "|".join(sorted(map(re.escape, defs), key=len, reverse=True)) + r")(?![A-Za-z@])")
    for _ in range(5):
        out, i, changed = [], 0, False
        for m in pattern.finditer(s):
            if m.start() < i:
                continue
            n, body = defs[m.group(1)]
            got = _args(s, m.end(), n) if n else ([], m.end())
            if got is None:
                continue
            args, j = got
            for k, a in enumerate(args, 1):
                body = body.replace(f"#{k}", a)
            out += [s[i : m.start()], body]
            i, changed = j, True
        out.append(s[i:])
        s = "".join(out)
        if not changed or len(s) > MAX_EXPANSION:
            break
    return s[:MAX_EXPANSION]


def plain(s: str, defs: dict[str, tuple[int, str]] | None = None) -> str:
    r"""A cell's text as printed.

    >>> plain(r"\textbf{75.3}$_{\pm 0.2}$"), plain(r"ResNet-50~\cite{he2016}"), plain(r"\makecell{Top-1\\Acc. (\%)}")
    ('75.3±0.2', 'ResNet-50', 'Top-1 Acc. (%)')
    >>> plain(r"\ours{}$^\dagger$", {"ours": (0, r"\textsc{Ours}")}), plain(r"{\bf 81.2} \textcolor{red}{(+1.1)}"), plain("$\\uparrow$ BLEU")
    ('Ours†', '81.2 (+1.1)', '↑ BLEU')
    >>> plain(r"BERT\_base \& T5 (\$0.5)")
    'BERT_base & T5 ($0.5)'
    """
    s = expand(s, defs or {})
    # escaped symbols kept apart from the markup steps below (an escaped _ or $ is text, not a subscript or math)
    held = {"\\_": "\x01", "\\$": "\x02", "\\{": "\x03", "\\}": "\x04", "\\#": "\x05", "\\%": "\x06", "\\&": "\x07"}
    for k, v in held.items():
        s = s.replace(k, v)
    s = re.sub(r"\\\\(?:\[[^\]]*\])?", " ", s)  # line breaks inside a cell (\makecell, \shortstack)
    s = re.sub(r"\\textcolor\s*(?:\[[^\]]*\])?\s*\{[^}]*\}", "", s)  # the colour, not the text after it
    for _ in range(4):
        s = re.sub(r"\\(?:" + DROP_ARG + r")\*?\s*(?:\[[^\]]*\])*\s*\{[^{}]*\}", "", s)
        s = re.sub(r"\\(?:" + KEEP_ARG + r")\*?\s*(?:\[[^\]]*\])*\s*(?:\{[^{}]*\}\s*){0,2}?\{([^{}]*)\}", r"\1", s)
    # a symbol; the space after a command word is not printed (\pm 0.2 is ±0.2)
    s = re.sub(
        r"\\([A-Za-z]+)( ?)|\\([%&_#${}])",
        lambda m: SYMBOLS[m.group(1)] if m.group(1) in SYMBOLS else m.group(0) if m.group(1) else SYMBOLS.get(m.group(3), m.group(0)),
        s,
    )
    s = re.sub(r"\\(?:" + NO_ARG + r")(?![A-Za-z])", "", s)
    s = re.sub(r"\\[,;:!> ]", " ", s)
    s = re.sub(r"\\([A-Za-z]+)", r"\1", s)  # a command it does not know: its name, so nothing silently vanishes
    s = s.replace("---", "—").replace("--", "–").replace("~", " ")
    s = re.sub(r"[{}$^_]", "", s)
    for k, v in held.items():
        s = s.replace(v, k[1])
    return re.sub(r"\s+", " ", s).strip()
