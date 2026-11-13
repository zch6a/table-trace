# Security

## What it does

- **What reaches the network, and when.** Only for an arXiv id or link: one request to `arxiv.org/e-print/<id>`, with
  a generic User-Agent, three seconds after the previous one, read up to 200 MB. Nothing else is fetched; a folder or
  a .tex file is read where it is.
- **Unpacking.** The source is unpacked into a temporary folder, deleted once read: only `.tex`, `.sty` and `.cls`
  files, only inside that folder (no absolute paths, no `..`, no links), and no more than 500 MB unpacked in all (a
  compression bomb stops there). A damaged archive is an error, not a crash.
- **Reading.** `\input` and `\include` are followed only inside the project's folder: never an absolute path, a
  drive, a network path or a name leading out of it. The LaTeX is read as text with regular expressions; nothing in it
  is run. Macro expansion and table sizes are bounded (a cell grows to 20,000 characters at most; `\multicolumn` spans
  64 columns at most; 5,000 rows a table).
- **What is kept.** Nothing: the output is the tables' text and numbers with where they are. In CSV, a field that
  starts like a spreadsheet formula (`=`, `+`, `@`, or `-` before a non-number) is prefixed with `'`, so that a
  spreadsheet shows it rather than runs it.
- **Dependencies.** None at run time.

## Reporting a vulnerability

Please open a private security advisory on GitHub (Security → Report a vulnerability) rather than a public issue.
