# Terminology Ledger

A paper reader must use one name for one thing. The same method, model, dataset, metric, or concept must not drift across shifting names, spellings, or capitalisation.

Build the ledger before translating, and treat it as the single source of truth for the rest of the job.

## 1. Build the ledger on first contact

When you first receive a paper, extract every recurring domain term before translating:
- methods, models, systems, algorithms, modules, frameworks
- datasets, benchmarks
- metrics, units, statistical symbols, mathematical notation
- abbreviations and acronyms, each with its full form
- key concepts the paper defines or repeatedly relies on

For each term, record its canonical form, its first-use expansion (for abbreviations), and any variants already present in the source.

## 2. Present the ledger to the user

Show a compact table:

| Canonical term | First-use definition | Variants seen in source | Decision |
|---|---|---|---|
| ViT | Vision Transformer (ViT) | "ViT", "vision transformer" | use "ViT" after first expansion |

Flag every collision: the same concept under different names, or one name reused for two different concepts. Adopt the form the source uses most often and state that choice.

## 3. Lock and enforce

- Use only canonical forms in every output. Terminology consistency outranks lexical variety.
- Define each abbreviation once, at first use, then use the short form.
- Keep units, symbols, and notation identical across every section.
- If the user renames a term, change every occurrence and update the ledger.

## 4. Do not invent terms

Do not coin new names for the author's methods, modules, or concepts. If a term is missing or inconsistent in ways you cannot resolve from the source, ask the user or flag it. Never fill the gap with a guessed name.
