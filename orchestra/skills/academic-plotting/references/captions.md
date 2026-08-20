# Caption contract

Captions are miniature arguments, not furniture labels.

## Pattern

```text
Figure X: [What is shown]. [How to read / encoding]. [Takeaway]. [Caveat if needed].
```

## Quantitative must-haves

- Metric name and direction (higher is better?).
- Aggregation: mean/median; error = SD/SE/CI; n; seeds.
- Single-run vs multi-run stated explicitly.

## Consistency

- Takeaway == figure contract `message` == claim ledger entry.
- Panel letters in caption match figure.
- Terminology matches body text / glossary.

## Placement

Caption text lives in LaTeX (`\caption{}`), not burned into the image file (except panel letters).
