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
