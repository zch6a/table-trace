"""The same model on the same benchmark across papers: every cell whose row names the model and whose column header
names the benchmark or the metric (in tables whose caption names what --caption gives, when it is given), with where
it is, and how far apart the papers' numbers are.

Names match by their words and numbers in order, whatever the spacing, hyphens or case: "ResNet-50" matches
"ResNet50", "ResNet 50" and "ResNet-50~\\cite{he}", not "ResNet-101", "ResNet-50x2" or "SE-ResNet-50". Aliases add other spellings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .source import Paper
from .tables import Table, direction, find_tables


def pattern(name: str, strict: bool = True) -> re.Pattern[str]:
    r"""A name as a pattern of its words and numbers, in order; `strict` (for models) also refuses a name joined by
    a hyphen to a longer one, which columns allow ("ImageNet" is in "ImageNet-1K").

    >>> p = pattern("ResNet-50")
    >>> [bool(p.search(s.lower())) for s in ["ResNet50", "ResNet 50 (ours)", "resnet-50", "ResNet-101", "ResNet-50x2", "SE-ResNet-50", "ResNet-50-D"]]
    [True, True, True, False, False, False, False]
    >>> bool(pattern("ViT-B/16").search("r50x1+vit-b/16")), bool(pattern("ViT-B/16").search("vit-b/16 (ours)"))
    (False, True)
    >>> bool(pattern("ImageNet", strict=False).search("imagenet-1k top-1")), bool(pattern("ImageNet").search("imagenet-1k"))
    (True, False)
    """
    tokens = re.findall(r"[a-z]+|\d+(?:\.\d+)?", name.lower())
    if not tokens:
        raise ValueError(f"{name!r}: no words or numbers to look for")
    # not joined by a hyphen or a plus to a longer name either: SE-ResNet-50, ResNet-50-D and R50x1+ViT-B/16 are other models
    body = r"[\W_]*".join(re.escape(t) for t in tokens)
    if strict:
        return re.compile(r"(?<![a-z0-9])(?<![a-z0-9][-+])" + body + r"(?![-+]?[a-z0-9])")
    return re.compile(r"(?<![a-z0-9])" + body + r"(?![a-z0-9])")


@dataclass
class Found:
    paper: str
    url: str
    table: str  # "Table 3", or a label, or where it is
    caption: str
    row: str
    column: str
    text: str  # the cell as printed
    value: float
    spread: float | None
    bold: bool
    file: str
    line: int
    better: str = ""  # "higher" or "lower", from the column's header


def find(paper: Paper, rows: list[re.Pattern[str]], cols: list[re.Pattern[str]], captions: list[re.Pattern[str]] | None = None,
         tables: list[Table] | None = None) -> list[Found]:  # fmt: skip
    """The results in `paper` whose row matches one of `rows` and whose column header matches one of `cols`, in
    tables whose caption (or label) matches one of `captions` when they are given."""
    out = []
    for t in tables if tables is not None else find_tables(paper.files):
        if captions and not any(p.search(f"{t.caption} {t.label}".lower()) for p in captions):
            continue
        keys = t.columns()
        col_hit = [any(p.search(k.lower()) for p in cols) for k in keys]
        if not any(col_hit):
            continue
        for i, rkey in t.body():
            if not any(p.search(rkey.lower()) for p in rows):
                continue
            r = t.rows[i]
            for j, c in enumerate(r):
                if c.value is None or j < t.row_start(i) or j >= len(keys):
                    continue
                if not col_hit[j]:
                    continue
                out.append(Found(paper.name, paper.url, t.name, t.caption, rkey, keys[j], c.text, c.value, c.spread, c.bold, t.file, c.line,
                                 direction(keys[j])))  # fmt: skip
    return out


def spread_of(found: list[Found]) -> tuple[float, float] | None:
    """The lowest and highest value found, across papers."""
    if not found:
        return None
    vals = [f.value for f in found]
    return min(vals), max(vals)
