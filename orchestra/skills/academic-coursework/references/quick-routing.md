# Quick Routing by Course Type

| Entry | Mode | Pipeline |
|---|---|---|
| **Course assignment** | semi-auto | C1(topic)→C2(lit)→C3(write)→C4(review)→C5(deliver) |
| **Course assignment + padding** | semi-auto | C1→C2→C3→C4→C5→C5.5(padding) |
| **Existing manuscript** | semi-auto | C4(review)→C5(deliver) |
| **Existing manuscript + padding** | semi-auto | C4→C5→C5.5(padding) |
| **Auto mode (any entry)** | auto | orchestrator runs C1→C5 sequence automatically |

See `static/core/gate-chain.md` for detailed Gate definitions and `static/core/dispatch-points.md` for agent dispatch rules.
