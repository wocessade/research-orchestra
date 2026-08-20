# Stop and Ask Protocol

**This pipeline is a collaborator, not a black-box factory.** At any stage where the right path depends on information you don't have, or where proceeding blindly would compromise the paper's quality — **STOP and ask the user.**

Yes, even with permissions bypassed, you can and must use `AskUserQuestion` to pause at critical junctures. Bypassing permissions means you can execute tools; it does NOT mean you should guess when a question would produce a better outcome.

**Trigger conditions — stop and ask when:**

| Situation | What to Ask |
|-----------|-------------|
| Ambiguous data structure | "Column X has 40% missing values. Is this expected, or should I treat these rows differently?" |
| Two equally strong candidate claims in D2 | Present both with tradeoffs: "Claim A is larger effect but less novel; Claim B is more novel but harder to prove. Which direction?" |
| Need a decision only the domain expert can make | "I found three candidate mechanisms. Which is most plausible given your domain knowledge?" |
| Citation requires verification | "I can't resolve DOI X. Is this the paper you meant: [details]?" |
| Journal choice affects what you write | "This paper could target [Journal A] (shorter, methods-focused) or [Journal B] (longer, theory-focused). Which venue?" |
| Data quality issue might be a feature not a bug | "The 'outliers' in column Y might actually be the most interesting cases. Should I treat them as special or exclude them?" |
| Unrecognizable data (images, proprietary formats) | "Column [X] contains [images/binary/proprietary format] I can't interpret directly. Tell me: (1) What does this represent? (e.g., TEM/SEM microscopy, XPS spectra, gel images) (2) What instrument/software generated it? (3) Do you have an exported CSV/text version? If not, I need you to provide the data in [specific format] — for spectra: two-column (x, y) text; for images: describe what each image shows + what you measured from it." |
| Existing figure needs modification agent can't perform | "Your [Figure X / data plot] should be [specific change: overlaid with blank, normalized, cropped to region, re-exported with scale bar visible, etc.] because [reason: this comparison is essential for the claim / the current version misleads / reviewer will ask for it]. I can't do this — it requires [Origin / ImageJ / ChemDraw / instrument software / etc.]. Please: [step-by-step what to do], then send me the updated file." |
| Data needs replotting from raw instrument files | "The [XRD/FTIR/XPS/etc.] data you provided is already processed (baseline-subtracted, smoothed, peak-labeled). For the paper, I need the raw data to: (1) apply consistent processing across all samples, (2) overlay multiple conditions in one figure, (3) extract peak positions/areas uniformly. Can you export the raw [xy/spectrum/intensity] data from [instrument software] without any processing applied?" |
| Ethics or IRB concern | "This analysis approach might raise [specific concern]. Has this been cleared?" |
| Advisor feedback received (T1/T3/T4) | Stop and parse feedback before applying any changes. Categorize by severity, present the structured tracking table, and confirm the fix plan before editing. Never apply advisor feedback silently — the user may have clarifying context about what the advisor meant. |
| Advisor review loop stagnates (3+ rounds, same issues) | "Advisor review has not converged after {N} rounds. The remaining unresolved issues are: {list}. Let's discuss how to resolve these before another round." |
| You hit something no installed skill handles | "I need to do [X] but no current skill covers this. Can you provide a tool/script for this, or should I use a simpler alternative?" |

| S8→S9 clean context | S9 审稿 agent 发现稿件中的错误与 S4 写作阶段一致 | STOP-AND-ASK: "审稿发现的问题可能与写作阶段 bias 重叠。需要重新审稿吗？" |

**Anti-pattern: forging ahead.** If you think "I'm not sure but I'll just do X," that's exactly when you should ask. A 30-second question saves hours of rewriting.

### Mid-Pipeline Direction Change

**Trigger:** User indicates a need to change research question, data source, or target venue type mid-pipeline.

**Structured rerouting:**
1. **Record progress:** Note which stages are complete and which outputs are salvageable
2. **Identify affected stages:** List stages that depend on the element being changed
3. **Suggest rollback point:** Recommend the earliest stage that needs re-execution
4. **Preserve salvageable outputs:** List outputs that remain valid despite the change

**Example:** User at S4 changes language from en→zh. Rollback to S3 (outline) — the claim structure may still work, but the prose direction and argumentation logic need re-planning for the new language.
