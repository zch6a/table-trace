"""A paper's LaTeX: from arXiv by its id (the source fetched into a temporary folder, deleted afterwards), or from a
folder or a .tex file. The files are read in the paper's order, following \\input and \\include, without comments
or what \\iffalse hides.

From paper-proof (the same author's MIT project): the id check, the safe unpacking (only .tex-like files, only inside
the folder, a size limit on what a bomb unpacks to) and the project reading.
"""

from __future__ import annotations

import gzip
import io
import os
import re
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass, field
from pathlib import Path, PurePath

from . import __version__

USER_AGENT = f"table-trace/{__version__} (+https://github.com/zch6a/table-trace)"
ID = re.compile(
    r"^(?:arxiv:|https?://arxiv\.org/(?:abs|pdf|e-print)/)?(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)(?:\.pdf)?/?$", re.I
)
KEEP = (".tex", ".sty", ".cls")
MAX_BYTES = 200 * 1024 * 1024  # arXiv's own limit on a source is 50 MB compressed
MAX_UNPACKED = 500 * 1024 * 1024  # all source files together, once decompressed: a bomb stops here
INTERVAL = 3.0  # seconds between requests to arXiv, as its API terms ask
INPUT = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}|\\(?:sub)?import\s*\{([^}]*)\}\s*\{([^}]+)\}")


class SourceError(Exception):
    pass


def arxiv_id(s: str) -> str | None:
    """The arXiv id in an id or an arXiv link, with its version if given; None for anything else.

    >>> arxiv_id("2106.09685"), arxiv_id("arXiv:1512.03385v1"), arxiv_id("https://arxiv.org/abs/2010.11929"), arxiv_id("paper/")
    ('2106.09685', '1512.03385v1', '2010.11929', None)
    """
    m = ID.match(s.strip())
    return m.group(1) if m else None


_last_request = [0.0]


def fetch(aid: str, into: Path, timeout: float = 60.0) -> None:
    """The source of an arXiv paper unpacked into `into`. A paper submitted as a PDF only has no LaTeX: an error."""
    wait = _last_request[0] + INTERVAL - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request[0] = time.monotonic()
    req = urllib.request.Request(f"https://arxiv.org/e-print/{aid}", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(MAX_BYTES + 1)
            kind = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raise SourceError(f"arXiv {aid}: HTTP {e.code}" + (" (no such paper?)" if e.code == 404 else "")) from e
    except (urllib.error.URLError, OSError) as e:
        raise SourceError(f"arXiv {aid}: could not download ({getattr(e, 'reason', None) or e})") from e
    if len(data) > MAX_BYTES:
        raise SourceError(f"arXiv {aid}: the source is larger than {MAX_BYTES // 2**20} MB")
    if "pdf" in kind or data[:5] == b"%PDF-":
        raise SourceError(f"arXiv {aid} was submitted as a PDF only: there is no LaTeX source to read tables from")
    extract(data, into)


def _copy(src: io.BufferedIOBase | gzip.GzipFile, target: Path, budget: list[int]) -> None:
    with open(target, "wb") as out:
        while chunk := src.read(1 << 20):
            budget[0] -= len(chunk)
            if budget[0] < 0:
                raise SourceError(f"the source unpacks to more than {MAX_UNPACKED // 2**20} MB: not extracted")
            out.write(chunk)


def extract(data: bytes, into: Path) -> list[Path]:
    """The .tex files of an arXiv e-print (a gzipped tar, or a single gzipped .tex) written under `into`."""
    into.mkdir(parents=True, exist_ok=True)
    root = into.resolve()
    written: list[Path] = []
    budget = [MAX_UNPACKED]
    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            for m in tf:
                name = Path(m.name)
                if not m.isfile() or name.is_absolute() or name.anchor or ".." in name.parts or name.suffix.lower() not in KEEP:
                    continue
                target = (into / name).resolve()
                if root not in target.parents:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                f = tf.extractfile(m)
                if f is not None:
                    _copy(f, target, budget)  # type: ignore[arg-type]
                    written.append(target)
        return written
    except tarfile.ReadError:
        pass  # not a tar: a single (gzipped) file
    except (tarfile.TarError, EOFError, OSError, zlib.error) as e:
        raise SourceError(f"the source archive is damaged ({e.__class__.__name__}): not extracted") from e
    target = into / "main.tex"
    try:
        src = gzip.GzipFile(fileobj=io.BytesIO(data)) if data[:2] == b"\x1f\x8b" else io.BytesIO(data)
        _copy(src, target, budget)
    except (EOFError, OSError, zlib.error) as e:
        raise SourceError(f"the source archive is damaged ({e.__class__.__name__}): not extracted") from e
    return [target]


def read_text(path: Path) -> str:
    """UTF-8 (with or without a BOM), else the Windows and Latin-1 encodings older sources use."""
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def strip_comments(text: str) -> str:
    r"""Comments removed, line breaks kept (so line numbers stay right).

    >>> strip_comments("a % b\nc \\% d % e\n")
    'a \nc \\% d \n'
    """
    return re.sub(r"(?<!\\)((?:\\\\)*)%[^\n]*", r"\1", text)


def strip_dead(text: str) -> str:
    r"""What never reaches the PDF blanked out, line breaks kept: \iffalse ... \fi and comment environments.

    >>> strip_dead("a \\iffalse b \\ifx c\\fi d \\fi e") == "a" + " " * 28 + "e"
    True
    """
    blank = lambda s: re.sub(r"[^\n]", " ", s)  # noqa: E731
    text = re.sub(r"\\begin\{comment\}.*?\\end\{comment\}", lambda m: blank(m.group(0)), text, flags=re.S)
    out, i = [], 0
    for m in re.finditer(r"\\iffalse\b", text):
        if m.start() < i:
            continue
        depth, j = 1, len(text)
        for t in re.finditer(r"\\(if[a-zA-Z@]*|fi)\b", text[m.end() :]):
            if t.group(1) == "fi":
                depth -= 1
            elif t.group(1) not in ("ifthenelse", "iftoggle"):
                depth += 1
            if depth == 0:
                j = m.end() + t.end()
                break
        out += [text[i : m.start()], blank(text[m.start() : j])]
        i = j
    out.append(text[i:])
    return "".join(out)


def find_main(directory: Path) -> Path | None:
    """The file with \\documentclass and \\begin{document}; main.tex, paper.tex or ms.tex when there are several."""
    candidates = []
    for p in sorted(directory.rglob("*.tex")):
        try:
            t = strip_comments(read_text(p))
        except OSError:
            continue
        if "\\documentclass" in t and "\\begin{document}" in t:
            candidates.append((p, len(t)))
    for name in ("main.tex", "paper.tex", "ms.tex", "manuscript.tex"):
        for p, _ in candidates:
            if p.name.lower() == name:
                return p
    if not candidates:
        return None
    return min(candidates, key=lambda c: (len(c[0].relative_to(directory).parts), -c[1]))[0]


def _resolve(root: Path, base: Path, name: str) -> Path | None:
    """A file named in the project, relative to the main file's folder; never outside the project, never a drive or
    network path."""
    name = name.strip()
    pure = PurePath(name.replace("\\", "/"))
    if not name or pure.anchor or os.path.isabs(name) or name.startswith(("/", "\\", "~")) or re.match(r"^[A-Za-z]:", name):
        return None
    for folder in (base, root):
        lexical = os.path.normpath(os.path.join(str(folder), str(pure)))
        try:
            if os.path.commonpath([lexical, str(root)]) != str(root):
                continue
        except ValueError:
            continue
        p = Path(lexical).resolve()
        for q in (p, p.with_name(p.name + ".tex")):
            if (q == root or root in q.parents) and q.is_file():
                return q
    return None


@dataclass
class Paper:
    """A paper's LaTeX files in reading order: (file relative to the main file's folder, text without comments)."""

    name: str  # the arXiv id, or the folder or file given
    files: list[tuple[str, str]] = field(default_factory=list)
    url: str = ""  # the paper on arXiv


def read_project(main: Path, name: str = "") -> Paper:
    main = main.resolve()
    root = main.parent
    paper = Paper(name=name or main.parent.name)
    seen: set[Path] = set()

    def visit(path: Path, depth: int) -> None:
        if path in seen or depth > 20 or len(seen) > 2000:
            return
        seen.add(path)
        text = strip_dead(strip_comments(read_text(path)))
        paper.files.append((path.relative_to(root).as_posix(), text))
        for m in INPUT.finditer(text):
            p = _resolve(root, path.parent, m.group(1) or (m.group(2) or "") + "/" + m.group(3))
            if p is not None:
                visit(p, depth + 1)

    visit(main, 0)
    return paper


def load(source: str) -> Paper:
    """A paper from an arXiv id or link, a folder holding a LaTeX project, or a .tex file."""
    path = Path(source)
    if path.is_file():
        return read_project(path, path.name)
    if path.is_dir():
        main = find_main(path)
        if main is None:
            raise SourceError(f"{source}: no .tex file with \\documentclass and \\begin{{document}}")
        return read_project(main, path.name)
    aid = arxiv_id(source)
    if aid is None:
        raise SourceError(f"{source}: not an arXiv id, a folder or a .tex file")
    with tempfile.TemporaryDirectory(prefix="table-trace-") as tmp:
        fetch(aid, Path(tmp))
        main = find_main(Path(tmp))
        if main is None:
            raise SourceError(f"arXiv {aid}: the source has no main .tex file")
        paper = read_project(main, aid)
    paper.url = f"https://arxiv.org/abs/{aid}"
    return paper
