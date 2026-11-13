<div align="center">

# table-trace

**论文表格里的每一个数字，都从 LaTeX 源码读出来，并标明它在哪个单元格。** 给一个 arXiv 编号，它把每张表的行和单元格整理成数据（文字、结果、± 标准差、是否加粗、所在文件和行号）。给几篇论文和一个模型名，它把各篇对同一模型、同一基准报的数并排列出来。

<a href="https://github.com/zch6a/table-trace/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/zch6a/table-trace/actions/workflows/ci.yml/badge.svg"></a>
<img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue">
<img alt="No dependencies" src="https://img.shields.io/badge/dependencies-none-2ea44f">
<a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-blue"></a>

[English](README.md) · **简体中文**

</div>

---

```console
$ table-trace compare 1512.03385 2012.12877 2201.03545 1905.11946 --row ResNet-50 --col top-1 --col acc
     20.74 (lower is better)  1512.03385 Table 4: ResNet-50 | top-1 err.   [residual_v1_arxiv_release.tex:379]
      76.2  2012.12877 Table 5: ResNet-50 | 25M | ImNet top-1   [experiments.tex:197]
     76.13  2201.03545 Table 10: ResNet-50 (PyTorch) | IN-1K acc.   [main.tex:809]
     78.82 ± 0.07  2201.03545 Table 10: ResNet-50 (enhanced recipe) | IN-1K acc.   [main.tex:811]
        76  1905.11946 Table 2: ResNet-50 | Top-1 Acc.   [arxiv-stripped.tex:307]
  ...
```

上面是输出 14 行中的 5 行（此处省略了标题）。同一个模型，四篇论文：ImageNet top-1 分别是 76.0（EfficientNet）、76.13 和换了新训练方法后的 78.82 ± 0.07（ConvNeXt）、76.2（DeiT），ResNet 论文自己报的是错误率 20.74（即准确率 79.26，单模型，用它自己的测试方式）。每个数字都指向它所在的表和行，差异从哪来（训练方法、测试方式、指标）一眼就能查到。

## 为什么做

不同论文对同一模型、同一基准报的数常常差好几个点：2026 年一项关于地理空间基础模型的研究从 152 篇论文中整理出 10,817 个结果，发现同一模型、同一评测设置下的差距可达 10 到 20 个点（[arXiv:2605.12678](https://arxiv.org/abs/2605.12678)）。从 PDF 里抄数字会丢掉出处，让大模型读表格又可能看错位。table-trace 按规则读作者写的 LaTeX，并保留每个数字所在的单元格。

## 能读什么

- **表格**：`tabular`、`tabular*`、`tabularx`、`tabulary`、`longtable`、`array`、`tblr`；`\multicolumn`（跨列表头会接到下面各列的列名上，例如“ImageNet Top-1”）、`\multirow`（行名会向下填到它跨越的各行）；booktabs 的横线、`\hline`、makecell 的 `\Xhline`、`\noalign`，以及论文自己用宏画的横线。
- **表号**：和论文里一样的 Table 1、2……：每个表格标题算一张表，同一个浮动体里并排的两张表算两张，子表的标题不算新表；同时给出每张表的 `\label` 和标题。
- **单元格**：印出来的文字（展开论文自己的 `\newcommand` 和 `\def` 宏，去掉 `\textbf{}` 等格式，`\pm`、`\dagger`、`\uparrow` 显示为 ±、†、↑，去掉引用）；结果（单元格是结果时取第一个数，`125M`、`50 epochs` 不算结果）、± 标准差、百分号、加粗（作者标的最好）和下划线（常表示次好）、单元格里的所有数字（如 `89.3/82.1`），以及文件和行号。
- **越高越好还是越低越好**：根据表头里的箭头或指标名判断（准确率、BLEU、top-1 越高越好，错误率、FID、延迟越低越好）。所以 `compare` 遇到错误率和准确率放在一起时会提醒。
- **来源**：arXiv 编号或链接（源码下载到临时目录，读完即删，两篇论文之间间隔三秒）、LaTeX 项目文件夹或 .tex 文件；会跟随 `\input` 和 `\include`，忽略注释和 `\iffalse` 里的内容。

在 25 篇知名论文上试过（ResNet、ViT、BERT、T5、LoRA、DeiT、ConvNeXt、Swin、EfficientNet、CLIP、LLaMA、Transformer、GPT-3、Llama 2、Mistral、DPO、DDPM、Stable Diffusion、MAE、SimCLR、RoBERTa、FlashAttention、GAN、YOLO，以及没有表格的 Adam）：约 28,300 个单元格，单元格文字里没有残留的 LaTeX；ResNet 的 14 张表的表号和 label 与论文一致。

## 使用

```bash
uvx --from git+https://github.com/zch6a/table-trace table-trace extract 1512.03385                 # JSON
uvx --from git+https://github.com/zch6a/table-trace table-trace extract 1512.03385 --format md     # Markdown，保留加粗
uvx --from git+https://github.com/zch6a/table-trace table-trace extract paper/ --table 2 --format csv
uvx --from git+https://github.com/zch6a/table-trace table-trace compare 2010.11929 2012.12877 --row "ViT-B/16" --col ImageNet --json
```

`compare` 的 `--row` 和 `--col` 可以写多次（不同写法：`--row ResNet-50 --row R50`），`--caption` 只保留标题里提到某个词的表。名字按其中的单词和数字依次匹配，不管空格、连字符和大小写：“ResNet-50”能找到“ResNet50”和“ResNet 50”，不会找到“ResNet-101”“ResNet-50x2”“SE-ResNet-50”或“R50x1+ViT-B/16”这样的其他模型。没有依赖；需要 Python 3.10+。

## 局限

- 只读 LaTeX：以 PDF 形式提交到 arXiv 的论文没有源码可读。画成图片的表格也不算表格。
- 由少见的宏算出来的数字（计算出的值、`\pgfmathprintnumber`）会按文字处理。
- `compare` 只匹配名字和表头：它不知道“IN-1K acc.”和“Top-1”是同一个指标，也不知道两篇论文的测试方式不同，所以会把表头和标题一起列出来，方便读者判断。

## 同一套工具里的其他项目

[arxiv-diff](https://github.com/zch6a/arxiv-diff) 比较论文各版本的变化（包括表格）· [exp-tables](https://github.com/zch6a/exp-tables) 从实验日志生成结果表 · [repro-score](https://github.com/zch6a/repro-score) 给论文代码的可复现性打分。

## 许可证

MIT。部分代码来自同一作者的 [paper-proof](https://github.com/zch6a/paper-proof)（MIT）。论文源码只在原处读取，不保存。
