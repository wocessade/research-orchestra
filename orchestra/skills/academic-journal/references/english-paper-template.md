# English Paper Template

> **~16 KB reference file.** Prefer on-demand partial reads.
> **Sections:** `## 1. LaTeX Template (Primary Path)` · `### Compilation` · `### Double-Column Option (Conference)` · `## 2. Word Template (Fallback Path via python-docx)` · `### Key Differences from Chinese Paper` · `### python-docx Script Skeleton` · `### APA 7th Reference Format` · `## 3. Length Targets Table`
> `## 4. Quick Start Instructions` · `### LaTeX Path (Recommended)` · `### Word Path (Fallback)` · `## 5. Field-Specific Variations` · `### CS / Engineering` · `### Biomedicine` · `### Social Sciences` · `### Economics`

Template for English-language international journal papers. Primary path: LaTeX. Fallback: Word via python-docx.

---

## 1. LaTeX Template (Primary Path)

```latex
\documentclass[12pt,a4paper]{article}

% ── Packages ──
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{times}                          % Times New Roman clone
\usepackage{geometry}
\geometry{margin=2.54cm}                    % 1 inch all sides
\usepackage{graphicx}                       % \includegraphics
\usepackage{booktabs}                       % Professional tables
\usepackage[numbers,super]{natbib}          % Numeric superscript citations
\usepackage{setspace}
\singlespacing
\usepackage{hyperref}                       % Clickable cross-refs
\usepackage{authblk}                        % Author/affiliation blocks
\usepackage{orcidlink}                      % ORCID icons

% ── Metadata ──
\title{Complete Manuscript Title: Specific, Searchable, No Colon Unless Strictly Necessary}
\author[1]{First Author\orcidlink{0000-0000-0000-0000}}
\author[1]{Second Author}
\author[2]{Third Author\orcidlink{0000-0000-0000-0000}}
\affil[1]{Department of X, University of Y, City, Country}
\affil[2]{Institute of Z, Organization W, City, Country}

\date{}

\begin{document}

\maketitle

% ── Abstract ──
\begin{abstract}
\noindent
Here write the abstract in a single paragraph. State the problem, method, primary result (with effect size), and implication.
Typical length: 150--300 words. Do not include citations unless strictly required by the journal.
Structured abstract variants: if the target journal requires ``Background/Methods/Results/Conclusions'' subheadings,
replace this block with a \texttt{\textbackslash section*} structure or use the journal's own class.

\textbf{Keywords:} keyword one; keyword two; keyword three; keyword four; keyword five
\end{abstract}

% ── Introduction ──
\section{Introduction}
Two or three opening sentences establish the broad importance of the topic.
Then the gap: what is missing from the current literature.
State the research question in one sentence.
Briefly describe the approach and the paper's contribution.
Briefly preview the paper's structure in one sentence using concrete content (e.g., ``Section 2 describes the dataset and estimation strategy; Section 3 presents the main results...''). Do NOT use formulaic roadmap language such as ``The remainder of this paper is organized as follows...'' — section headings are the roadmap.
Target length: 500--1,200 words.

Citations appear as superscript numbers: as demonstrated by Smith\textsuperscript{1}.
For author-year styles, use \verb|\citet{key}| and \verb|\citep{key}| from \texttt{natbib}.

% ── Methods ──
\section{Methods}
Provide sufficient detail that a competent researcher could replicate the work.
Include: equipment/models/software with version numbers, sample sizes, inclusion/exclusion criteria,
and the statistical tests used. Use past tense. Active voice preferred for clarity.

\subsection{Participants / Data Sources}
Describe the sample, recruitment, or data provenance.

\subsection{Procedure}
Step-by-step experimental or analytical protocol.

\subsection{Statistical Analysis}
Name the software (with version), specify tests, state the significance threshold.
Target length: 800--2,000 words.

% ── Results ──
\section{Results}
Past tense. Lead with the finding, not the figure pointer.
Every paragraph: one finding + its evidence (statistics, figure/table reference).

\begin{figure}[htbp]
    \centering
    \includegraphics[width=0.8\textwidth]{figures/figure1.pdf}
    \caption{Descriptive caption stating what the figure shows.
             Error bars represent \textpm\ standard deviation.}
    \label{fig:figure1}
\end{figure}

\begin{table}[htbp]
    \centering
    \caption{Descriptive table caption.}
    \label{tab:table1}
    \begin{tabular}{@{}lcccc@{}}
        \toprule
        Group       & N  & Mean & SD  & p-value \\
        \midrule
        Control     & 50 & 23.4 & 5.1 & ---     \\
        Treatment A & 50 & 27.8 & 4.9 & 0.003   \\
        \bottomrule
    \end{tabular}
\end{table}

Do not interpret findings here --- save interpretation for Discussion.
Target length: 800--2,000 words.

% ── Discussion ──
\section{Discussion}
Start with a direct answer to the research question (no throat-clearing).
Compare findings to the literature: agree / disagree / explain discrepancies.
Discuss unexpected results.
Acknowledge limitations naturally (weave them in, do not bury them in a single last paragraph).
State implications and, if appropriate, specify what kind of future research is needed.
Target length: 800--2,000 words.

% ── Conclusion ──
\section{Conclusion}
Take-home message: what is the single most important thing the reader should remember?
One paragraph, no new content beyond what has already been presented.
Target length: 100--300 words.

% ── Acknowledgments ──
\section*{Acknowledgments}
Funding sources, colleagues who commented on the draft, and any institutional support.

% ── Author Contributions ──
\section*{Author Contributions}
Use CRediT taxonomy or a narrative description of each author's role.

% ── Bibliography ──
\bibliographystyle{unsrt}      % Numbered, in order of first citation
% \bibliographystyle{plainnat} % Author-year, alphabetical
\bibliography{references}

\end{document}
```

### Compilation

```bash
pdflatex manuscript.tex
bibtex manuscript
pdflatex manuscript.tex
pdflatex manuscript.tex
```

For continuous word-count tracking:
```bash
texcount manuscript.tex -inc
```

### Double-Column Option (Conference)

For IEEE / ACM conference papers, replace the document class:
```latex
\documentclass[conference]{IEEEtran}
% or
\documentclass[sigconf]{acmart}
```

---

## 2. Word Template (Fallback Path via python-docx)

For users who must submit .docx. Follow the `process_md_to_docx` pattern, adjusted for English journal standards.

### Key Differences from Chinese Paper

| Aspect | Chinese | English Journal |
|--------|-------------|-----------------|
| Page size | A4 (21.0 x 29.7 cm) | US Letter (21.59 x 27.94 cm) or A4 per journal |
| Margins | 2.54 cm t/b, 3.18 cm l/r | 2.54 cm / 1 inch all sides |
| Body font | SimSun 12pt (小四) | Times New Roman 12pt |
| Line spacing | 1.5x | 1.0x (single) |
| Paragraph indent | 0.74 cm first-line | No first-line indent; space between paragraphs (6pt after) |
| Paper title | SimHei 16pt bold, centered | Times New Roman 14pt bold, centered |
| Heading L1 | SimHei 14pt bold | Times New Roman 14pt bold |
| Heading L2 | SimHei 12pt bold | Times New Roman 12pt bold or italic |
| Section numbers | 1, 1.1, 1.1.1 | 1, 1.1, 1.1.1 |
| Reference format | GB/T 7714 | APA 7th or journal-specific |
| Reference font | SimSun 10.5pt (五号) | Times New Roman 12pt |
| Reference spacing | 1.0x, hanging indent 0.74cm | 1.0x or journal-specific |

### python-docx Script Skeleton

```python
from docx import Document
from docx.shared import Pt, Cm, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

doc = Document()

# ── Page Setup ──
section = doc.sections[0]
section.page_width = Cm(21.0)       # A4; use Cm(21.59) for US Letter
section.page_height = Cm(29.7)      # A4; use Cm(27.94) for US Letter
section.top_margin = Cm(2.54)
section.bottom_margin = Cm(2.54)
section.left_margin = Cm(2.54)
section.right_margin = Cm(2.54)

# ── Font Helpers ──
def set_run_font(run, font_en='Times New Roman', size=Pt(12), bold=False, italic=False):
    """Set fonts on a run. English-only, no East-Asian font needed."""
    run.font.size = size
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:ascii'), font_en)
    rFonts.set(qn('w:hAnsi'), font_en)

def add_body_para(doc, text, font_en='Times New Roman', size=Pt(12)):
    """Add a body paragraph: block style, no indent, 1.0 spacing, 6pt after."""
    para = doc.add_paragraph()
    pf = para.paragraph_format
    pf.line_spacing = 1.0
    pf.space_before = Pt(0)
    pf.space_after = Pt(6)
    # No first-line indent (block paragraph style)
    run = para.add_run(text)
    set_run_font(run, font_en=font_en, size=size)
    return para

def add_heading_styled(doc, text, level=1):
    """Add a heading: Times New Roman, bold, left-aligned or centered."""
    para = doc.add_paragraph()
    heading_styles = {0: "Heading 1", 1: "Heading 2", 2: "Heading 3"}
    style_id = heading_styles.get(level)
    if style_id:
        try:
            para.style = doc.styles[style_id]
        except KeyError:
            pass
    pf = para.paragraph_format
    pf.line_spacing = 1.0
    pf.space_before = Pt(12)
    pf.space_after = Pt(6)

    if level == 0:  # Paper title
        run = para.add_run(text)
        set_run_font(run, size=Pt(14), bold=True)
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif level == 1:  # Section heading (Introduction, Methods, etc.)
        run = para.add_run(text)
        set_run_font(run, size=Pt(14), bold=True)
    elif level == 2:  # Subsection heading
        run = para.add_run(text)
        set_run_font(run, size=Pt(12), bold=True)
    return para

def add_author_block(doc, text):
    """Author list, centered, normal weight."""
    para = doc.add_paragraph()
    pf = para.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.line_spacing = 1.0
    pf.space_after = Pt(2)
    run = para.add_run(text)
    set_run_font(run, size=Pt(12), bold=False)
    return para

def add_affiliation_block(doc, text):
    """Affiliation, centered."""
    para = doc.add_paragraph()
    pf = para.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.line_spacing = 1.0
    pf.space_after = Pt(12)
    run = para.add_run(text)
    set_run_font(run, size=Pt(10), bold=False)
    return para

def add_reference(doc, text, font_en='Times New Roman', size=Pt(12)):
    """Add a reference entry: 1.0 spacing, hanging indent 1.27 cm (0.5 inch)."""
    para = doc.add_paragraph()
    pf = para.paragraph_format
    pf.line_spacing = 1.0
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.first_line_indent = Cm(-1.27)
    pf.left_indent = Cm(1.27)
    run = para.add_run(text)
    set_run_font(run, font_en=font_en, size=size)
    return para

def process_md_to_docx(doc, filepath, body_fn, quote_fn=None, ref_fn=None, heading_fn=None):
    """
    Process a markdown file into docx paragraphs.
    Same logic as process_md_to_docx: consecutive lines merged into one paragraph.
    """
    import re as _re
    if not os.path.exists(filepath):
        return
    quote_fn = quote_fn or body_fn
    ref_fn = ref_fn or body_fn

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    def clean_md_line(line):
        line = _re.sub(r'\*\*(.+?)\*\*', r'\1', line)
        line = _re.sub(r'\*(.+?)\*', r'\1', line)
        return line

    body_buf = []

    def flush_body():
        nonlocal body_buf
        if not body_buf:
            return
        text = clean_md_line(''.join(body_buf))
        if ref_fn and _re.match(r'^\[\d+\]', text):
            ref_fn(doc, text)
        else:
            body_fn(doc, text)
        body_buf = []

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line or line.isspace():
            flush_body()
            i += 1
            continue
        if line.startswith('```'):
            flush_body()
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                i += 1
            i += 1
            continue
        if line.startswith('# ') and not line.startswith('## '):
            flush_body()
            if heading_fn:
                heading_fn(doc, clean_md_line(line[2:]), level=0)
            i += 1
            continue
        if line.startswith('## '):
            flush_body()
            if heading_fn:
                heading_fn(doc, clean_md_line(line[3:]), level=1)
            i += 1
            continue
        if line.startswith('### '):
            flush_body()
            if heading_fn:
                heading_fn(doc, clean_md_line(line[4:]), level=2)
            i += 1
            continue
        if line.startswith('> '):
            flush_body()
            quote_lines = [line[2:]]
            i += 1
            while i < len(lines) and lines[i].startswith('> '):
                quote_lines.append(lines[i][2:].rstrip())
                i += 1
            quote_fn(doc, clean_md_line(''.join(quote_lines)))
            continue
        if _re.match(r'^\[\d+\]', line):
            flush_body()
            ref_fn(doc, clean_md_line(line))
            i += 1
            continue
        body_buf.append(line)
        i += 1

    flush_body()

def clean_md_line_standalone(line):
    import re as _re
    line = _re.sub(r'\*\*(.+?)\*\*', r'\1', line)
    line = _re.sub(r'\*(.+?)\*', r'\1', line)
    return line
```

### APA 7th Reference Format

For English journal papers, references follow APA 7th or the target journal's style:

```
[1] Author, A. A., & Author, B. B. (Year). Title of article. Title of Periodical, Volume(Issue), Pages. https://doi.org/xxxx
[2] Author, A. A. (Year). Title of book. Publisher.
[3] Author, A. A. (Year, Month). Title of conference paper. In Editor (Ed.), Proceedings Title (pp. xx-xx). Publisher.
```

---

## 3. Length Targets Table

Per-section word count ranges for typical international journal articles:

| Section | Word Count Range | Notes |
|---------|-----------------|-------|
| Title | 10--20 words | Specific, searchable, no "A Study of..." |
| Abstract | 150--300 words | Structured or unstructured per journal |
| Introduction | 500--1,200 words | Funnel: broad → gap → question → approach |
| Methods | 800--2,000 words | Replicable detail; may be shorter for computational papers |
| Results | 800--2,000 words | Data-driven, interpretation-free |
| Discussion | 800--2,000 words | Interpretation, comparison, limitations |
| Conclusion | 100--300 words | Take-home message, no new content |
| Acknowledgments | 50--150 words | Funding + contributors |
| References | 30--60 entries | Depends on field and journal tier |
| **Total body** | **~4,000--8,000 words** | Typical research article (excluding references) |

---

## 4. Quick Start Instructions

### LaTeX Path (Recommended)

1. Copy the LaTeX skeleton from Section 1 into `manuscript.tex`.
2. Replace placeholder text with actual content from S4 output.
3. Create `references.bib` with BibTeX entries from S2 bibliography.
4. Place figures in `figures/` directory.
5. Compile:
   ```bash
   pdflatex manuscript.tex
   bibtex manuscript
   pdflatex manuscript.tex
   pdflatex manuscript.tex
   ```
6. Track word count: `texcount manuscript.tex -inc`

### Word Path (Fallback)

1. Write the paper content as Markdown following the IMRAD structure.
2. Use the python-docx script skeleton from Section 2, substituting actual content.
3. Run the script to generate the .docx.
4. Verify formatting: Times New Roman 12pt, single spacing, no first-line indent, 1-inch margins.
5. Save as the final output filename required by the journal.

---

## 5. Field-Specific Variations

### CS / Engineering
- IEEE double-column format: use `\documentclass[conference]{IEEEtran}`
- Algorithm environments: `\usepackage{algorithm}`, `\usepackage{algpseudocode}`
- Results and Discussion are often combined in shorter conference papers
- Figures carry most of the evidentiary weight; minimal prose decoration

### Biomedicine
- Structured abstract: Background / Methods / Results / Conclusions subheadings
- CONSORT (RCT), PRISMA (systematic review), STROBE (observational) checklists
- Ethics statement (IRB approval number, informed consent) is mandatory in Methods
- Conflicts of interest and funding disclosures typically required on the title page

### Social Sciences
- APA 7th format: author-date citations, running head on title page
- Longer introductions with extensive literature review (often 25--35% of total text)
- Qualitative studies: thematic analysis, participant quotes as evidence
- Appendices for interview protocols, survey instruments, coding schemes

### Economics
- AER (American Economic Review) style
- Regression tables with standard errors in parentheses, significance stars
- Footnotes for technical details and robustness checks
- Mathematical models in numbered equations with clear notation definitions
