# Polish log

### 2026-11-14 — development

**Why this, not a leaderboard.** Hugging Face revived Papers with Code (paperswithcode.co, 2026-05): state-of-the-art
leaderboards enriched by AI, with no API, data dump or data licence announced and no link from a result to its
table. The gap is the other way round: papers report the same model on the same benchmark several points apart
(arXiv:2605.12678: 10,817 results from 152 papers, gaps of 10–20 points), and nothing maintained reads result tables
from LaTeX source keeping each cell. So: every number in a paper's tables, traced to its cell; and a comparison of
what papers report for one model.

**Built from earlier work** (the same author's MIT code): from paper-proof, the arXiv id check, the safe unpacking
(only .tex-like files, only inside the folder, a 500 MB limit on what a bomb unpacks to), the project reading
(`\input` inside the project only, comments and `\iffalse` left out) and its table reader; from arxiv-diff, the row
and column keys. Extended: cells as printed (the paper's `\newcommand`/`\def` macros with arguments expanded, a long
list of formatting dropped, symbols as Unicode, the space after a command word dropped as LaTeX does: `\pm 0.2` is
±0.2), the ± spread, %, underline, every number in a cell, `\multirow` names filled down, spanning headers joined to
their columns, which way a column is better, the table numbers.

**Tried on real papers, fixed what broke**:
- the caption naming the benchmark made every column count (throughput, image size, box AP as "ImageNet"): `--col`
  now matches column headers, and `--caption` filters tables;
- `\noalign{\global\savewidth...}` (nested braces) and rules drawn by the paper's own macros (`\thickhline`) leaked
  into row names (ConvNeXt): commands between rows are blanked with their braces, and rule macros before reading;
  makecell's `\Xhline`, `\Xcline`, `\hhline` added;
- an error rate beside accuracies (the ResNet paper reports top-1 error): each result says which way its column is
  better, and `compare` warns when both kinds are side by side;
- names too loose: "ResNet-50" matched SE-ResNet-50, ResNet-50-D and the hybrid R50x1+ViT-B/16; a name joined to a
  longer one by a hyphen or a plus is now another model (for model names; "ImageNet" still matches "ImageNet-1K");
- numbering: two tables side by side in one float (ResNet's Tables 4 and 5, two minipages) got one number, so every
  table after was one off; each table caption now counts, a subtable's does not, and each tabular takes its own
  caption and label. ResNet's 14 tables now match the paper.
Then eleven papers (ResNet, ViT, BERT, T5, LoRA, DeiT, ConvNeXt, Swin, EfficientNet, CLIP, LLaMA): about 13,500
cells, no LaTeX command left in a cell's text.

**What it shows**: ResNet-50's ImageNet top-1 is 76.0 (EfficientNet), 76.13 and 78.82 ± 0.07 with a newer recipe
(ConvNeXt), 76.2 (DeiT), and 20.74 error (79.26 accuracy) in the ResNet paper; ViT-B/16's is 84.15 in the ViT paper
(pre-trained on JFT) and 77.9 in DeiT (ImageNet only).

Tests: 18 (doctests included), made-up LaTeX, no network (an arXiv fetch is replaced by a made-up source in the test
of the command). ruff, ruff format, mypy clean.

Next: polishing round 1 (more papers and table styles; the CLI's edges; a social card).

### 2026-11-14 — polishing round 1

**Fourteen more papers in other styles** (Transformer, GPT-3, Llama 2, Mistral, DPO, DDPM, Stable Diffusion, MAE,
SimCLR, RoBERTa, FlashAttention, Adam, GAN, YOLO): about 13,000 more cells, read with the same check for LaTeX left in a
cell's text (all that remained were English words in tables of sample text: “it”, “small”, “centering”). Fixed:
- `\texttt{{\color{gray}...} \textbf{...}}` (GPT-3's prompt tables) kept the command's name: a plain brace group
  inside an argument was never unwrapped. Now it is (a doctest).
- Tabulars that only lay out images inside figures (GPT-3's scale plots, Stable Diffusion's samples) came out as tables
  with no text and every row a header: a tabular with no text in any cell is now not a table (75 tables in GPT-3,
  not 86).
- A text-only table whose last row is followed by `\bottomrule` was all header: the rule closing the table is no
  longer read as the line under a header.

**The command's edges**, one by one: a folder with no main file (a folder of table snippets) was refused; now every
.tex file in it is read in name order. A path that does not exist was “not an arXiv id”; now “no such file or
folder”. `compare` with no match said only “no match in: paper”; now it says what was looked for and suggests other
spellings. Already fine: no arguments, a missing `--col`, a paper without tables (exit 1), a binary .tex file, an
arXiv id that does not exist (HTTP 404, said), an id that is not one, several papers at once.

**The social card** (`docs/social-preview.png`, from `scripts/social-card.html`): the README's ResNet-50 comparison, each
number with its table and line.

Tests: 20 (doctests included), made-up LaTeX, no network. ruff, ruff format, mypy clean.

Next: polishing round 2 (an independent review of the code; the README's claims against real runs).

### 2026-11-14 — polishing round 2

**An independent review** (unpacking and `\input` paths found safe; 9 bugs and 7 smaller issues, all reproduced with
made-up LaTeX; 15 fixed, each with a test):
- **Numbering.** A subtable's end was looked for from the wrong offset, so in a long file a table's own caption, written
  after its subtables, was taken as inside one and dropped (the table unnumbered, every later number one off). Tables
  in an `\input` file were numbered after the whole parent file; they are now numbered where the file is included
  (the project reader records where each file inputs another). A table captioned with `\captionof{table}` outside a
  table float (in a figure's minipage) had no number, so the next table was “Table 1” where LaTeX prints Table 2.
- **A tabular nested in a cell** ended the outer table at the inner one's `\end`: the rows after it were lost and the
  inner one came out as a second table. Ends are now matched by depth, the splitter keeps a nested tabular's `&` and
  `\\` in its cell, and its text is the cell's.
- **Rules took the next cell as an argument**: `\hline {\bf Ours} & 2.0`, `\cline{1-2} {\em Ours}`, `\addlinespace {\it
  Ours}`, `\rowcolor{gray!20}{\bf Ours}` gave an empty name (so `compare` never found the row), and `\rowcolor[HTML]{EEEEEE}`
  left “EEEEEE” in it. Each rule now takes its own arguments only.
- **`\multicolumn` with braces in its column spec** (`{@{}c@{}}`, `{>{\centering}p{2cm}}`) was not recognised: the header
  read “multicolumn2@c@ImageNet” and the columns after it shifted. A spanning header in the only header row now covers
  its columns too.
- **Names**: “GPT-3” matched GPT-3.5 and “ViT-B/16” matched ViT-B/16/384: a name followed by `.5` or `/384` is another
  model now; “C++” keeps its pluses.
- **Macros with an optional first argument** (`\newcommand{\res}[2][0.0]{#2 (#1)}`) ignored the default and took the next
  token; arguments are now put in at once (an argument holding `#2` is not filled again); and the expansion limit is
  counted as it grows, so a macro that doubles itself stops at 20,000 characters instead of allocating gigabytes (and
  running out of memory would now be a message).
- **`\iff` inside an `\iffalse` block** (the maths symbol) counted as an `\if`, so the block never closed and every table
  after it was blanked: only TeX's conditionals and those `\newif` declares count now.
- **Smaller**: `\multirow{-2}` (text in the last row of its span) filled downwards, now upwards; a column of years (BERT
  & 2019 & 80.1) was the first result, now not; “2018-2019” and “125m” were results, now not (a letter after a number
  counts only as a superscript mark: 75.3$^a$); `\textminus` is a minus; CSV fields that start like a formula (=, +, @,
  - before a non-number) are quoted for spreadsheets; one paper that cannot be read no longer stops the others (exit 2
  at the end).
- Not changed: “75.3 (0.2)” has no spread (a bracketed number after a result is as often a delta); parsing is otherwise
  conservative (a miss, not a wrong number).

**On the real papers** after the fixes: ConvNeXt, Swin and Llama 2 nest tabulars, so their tables had been cut short —
ConvNeXt now reads 1,055 cells in 12 tables (633 in 27 before), Swin 893 (624), Llama 2 3,558 (2,686); CLIP's and
DDPM's tables numbered in full (19 and 4); no LaTeX in any cell's text. 25 papers, about 28,300 cells.

**The README against real runs**: every command, as written, from GitHub in an empty folder: `extract` (JSON 18 tables,
Markdown 18, CSV of the local fixture), `compare` (the ResNet-50 example line for line, the ViT-B/16 one). The example
is now said to be five of its fourteen lines; the count of papers and cells is up to date.

Tests: 23 (doctests included), made-up LaTeX, no network. ruff, ruff format, mypy clean.

Next: polishing round 3 (speed on long sources; the README read again; the agent skill tried).

The round's commit (9f90722) went out with three lint errors (ruff: a lambda not binding its loop variable, a percent-formatted string in a test), so CI failed; fixed in 13bbaa7 (a typed helper for the macro arguments). The gates now run before any commit in one step that stops on a failure.

### 2026-11-14 — polishing round 3

**Speed.** Real long sources read in a fraction of a second — GPT-3 (95 files, 75 tables) 0.13 s, Llama 2 (53 tables)
0.17 s, Stable Diffusion (71 tables) 0.24 s — while fetching their sources takes 5 to 17 s. Made-up stress cases found
three steps that grew with the square of the input: a float was checked against every float before it, a tabular looked
through every float and every tabular start, and every cell's line was counted from the top of its file. Now floats and
tabulars are found by binary search (they come in order and do not overlap) and lines from an index of the line breaks:
10,000 floats 2.89 s → 0.04 s; 2,000 small tables 1.28 s → 0.34 s; a table of 5,000 rows 1.65 s → 0.53 s. A
200,000-character cell, 3,000 macros, and unclosed braces in every row all stay under 0.1 s.

**The agent skill, followed as written**: its three commands run, and the JSON carries what it tells an agent to quote
(table, row, column, value, bold, `better`, file and line). Doing so showed a gap: ViT's Table 2 has the models as
columns and the datasets as rows, so `compare --row ViT-L/16 --col ImageNet` found nothing there. `compare` now also
reads a table the other way round (a column named like the model, a row named like the benchmark), reports it as model
and metric all the same, and marks it (`transposed`, “models as columns”): ViT-L/16 on ImageNet, 87.76 ± 0.03 (JFT) and
85.3 ± 0.02 (ImageNet-21k). The skill now says so, and when to use `--caption`.

**The README read again**: it now says how long reading takes, that tables with the models as columns are read the
other way round, and what round 2 added (a tabular nested in a cell, `\captionof{table}`, numbering across `\input`,
folders of table snippets); the CHANGELOG too.

Tests: 24 (doctests included), made-up LaTeX, no network. ruff, ruff format, mypy clean.

Next: polishing round 4 (engineering: a clean install from the wheel, the workflows, a dependency check, a fuzz of the
readers).

### 2026-11-14 — polishing round 4

**Broken inputs** (`scripts/fuzz.py`, new): mutations of a corpus of tables that use what the readers handle
(`\multicolumn` with braced specs, `\multirow{-n}`, rule macros and `\noalign`, nested tabulars, subtables,
`\captionof{table}`, optional-argument macros, `\iffalse` with `\iff`, models as columns) — pieces repeated, removed or
cut short, LaTeX fragments spliced in (an unclosed `\multicolumn{`, `\def\a{\a\a}\a`, a stray `\end{tabular}`, NUL) —
through `find_tables`, the row and column keys and `compare`; and mutated .tar.gz sources (with `../` and absolute
names, bytes flipped, cut short) through the unpacking and the project reading, checking that nothing lands outside
its folder. 500 rounds (seed 0) and 5,000 each with seeds 1, 2 and 3: 15,500 rounds, about 3,100 archives, no failure,
the slowest case 0.01 s. (The fuzz script's own check for escaped files first looked through every earlier folder,
which made 5,000 rounds take two minutes; it now looks only beside the folder and removes each one: 16 s.) CI runs
300 rounds on every push.

**A clean install** (the sdist, the wheel built from it, a new Python 3.10 environment): `--version`, no requirements
at all, `compare` on the fixture. The sdist holds the sources, tests, fixture, scripts and documents, not `docs/`.

**Workflows and dependencies**: actions pinned to commits, read-only tokens but for the release job that writes the
release (and runs nothing of the project), `persist-credentials: false`, a timeout on every job, `--locked`;
`pip-audit` on the 15 locked development packages: no known vulnerabilities. At run time there is nothing to audit.

Tests: 24 (doctests included), made-up LaTeX, no network. ruff, ruff format, mypy clean.

Next: polishing round 5 (the documents read through; the CHANGELOG as release notes), then v0.1.0.
