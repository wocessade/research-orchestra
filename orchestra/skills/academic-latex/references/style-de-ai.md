# English prose style — human, not model

Goal: prose a tired reviewer reads without friction — not detection evasion.

## Modification threshold

If a passage is already natural, **leave it untouched**. Editing for its own sake degrades text.

## Vocabulary (non-technical filler)

| Avoid | Prefer |
|-------|--------|
| leverage | use, employ |
| delve into | examine, investigate |
| pivotal / paramount | key, central / important |
| underscore | show, emphasize |
| robust (as filler) | reliable, stable — or the specific property |
| seamless / holistic | integrated / comprehensive |
| cutting-edge / groundbreaking | state-of-the-art (sparingly), novel |
| paradigm / realm / landscape | approach / area / field |
| burgeoning / multifaceted / nuanced | growing / complex / subtle |
| unprecedented | new, notable |

Keep domain terms exact. Never synonymize identifiers, paths, metrics, or math.

## Safety zones (character-for-character)

De-AI edits prose only. Do not touch:

- math: `$...$`, `\[...\]`, equation/align bodies
- `verbatim`, `\texttt{}`, code, paths, filenames
- `\label`, `\ref`, `\cref`, `\cite` keys
- siunitx numbers (`\SI`, `\num`)
- LaTeX comments `% ...`

A de-AI rewrite **subtracts**: reworded passage should be no longer than the original. If more words are needed, it is a content change — handle as claim/evidence work.

## Structure

- Prose over lists unless genuinely enumerable.
- Cut throat-clearing ("It is worth noting that", "In order to" -> "to").
- Vary sentence rhythm; limit em dashes to one per paragraph.
- No `\textbf`/`\emph` in body except first-use definitions.
- Put the load-bearing clause last.

## Stance

- Past tense for what was done; present for what the artifact is.
- One claim per sentence near evidence; number + figure/table pointer together.
- Bound every positive claim (dataset, split, years, compute).
- "We" is fine when conventional.

## Section jobs

- Abstract: problem -> approach -> 2–3 headline numbers -> honest verdict. No citations.
- Intro: motivation, gap, RQs, contributions mapped to sections.
- Methods: reproducible; reader with the repo finds every named component.
- Results: organize by question answered, not chronology.
- Discussion: interpret, bound, threats to validity; negatives are first-class.
- Conclusion: no new claims.

Also see academic-journal `references/english-de-ai-guide.md` and `chinese-de-ai-guide.md`.
