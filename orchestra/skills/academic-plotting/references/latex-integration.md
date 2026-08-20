# LaTeX integration

## Include

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/fig_overview.pdf}
  \caption{...}
  \label{fig:overview}
\end{figure}
```

Prefer PDF for plots; PNG for generated schematics if needed.

## Fallback

```latex
\IfFileExists{figures/fig_overview.png}{%
  \includegraphics[width=\linewidth]{figures/fig_overview.png}}{%
  \input{figures/fig_overview_ref.tikz}}
```

## Float hygiene

- `placeins` + `\FloatBarrier` at section ends when floats drift.
- Avoid `[H]` spam; fix sizing at source.
- Do not `\resizebox` to "make it fit" if it destroys typography — regenerate.

## Inventory

Update `.paper/figure_inventory.md`:

| id | file | class | message | source script | status |
|----|------|-------|---------|---------------|--------|
| fig:overview | figures/fig_overview.pdf | concept | ... | prompt.md | verified |

## Text references

Every figure referenced in prose near first appearance (`Fig.~\ref{fig:overview}`).
