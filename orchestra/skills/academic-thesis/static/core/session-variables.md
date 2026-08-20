# Session Variables — External API Keys

These keys are session-only, never persisted to disk, never written to any file.
If the user has not provided a needed key, STOP-AND-ASK before the first stage that needs it.

## Pipeline-Level Variables

Pipeline-level variables (`pipeline_root`, `output_dir`) are defined in `manifest.yaml` `session_variables` and set at session start:

| Variable | Description | Auto-detection |
|----------|-------------|----------------|
| `pipeline_root` | Root directory of the pipeline skill. Used by CLI commands in stage files (literature/literature_search.py, evaluate/scripts/scoring.py, etc.). | Auto-detected at session start as the directory containing `manifest.yaml`. |
| `output_dir` | Per-paper output directory. After Paper Directory Resolution (SKILL.md Step 1), resolves to `{output_dir_base}/{YYYYMMDD_HHMMSS}_{slug}/`. Default base: `./paper_output_{entry_point}`. Can be overridden by user. |
| `paper_slug` | Per-paper unique directory name: `{YYYYMMDD_HHMMSS}_{english_slug}`. Generated at pipeline start. English slug derived from paper topic (Chinese→English translation, lowercase, 50-char limit). Use `"untitled"` if topic unknown at generation time. | Generated at pipeline start (SKILL.md Step 1, Paper Directory Resolution). |
| `paper_dir` | Full path to the paper's output directory. Same as resolved `output_dir`. | Set during Paper Directory Resolution. |

## API Key Registration Table

| Service | Key Name | Needed By | How to Register |
|---------|----------|-----------|----------------|
| Tavily | `tavily_api_key` | S2, S5, C2E, T2D | User provides at session start or first use |
| OpenRouter | `openrouter_api_key` | S5 (generate-image.md fallback) | User provides at session start |
| Zotero | `zotero_api_key`, `zotero_library_id` | S2, S6 | User provides at session start |

## Key Resolution Protocol

When any stage needs a key:

1. **Check** if the key name is already registered in this session (from prior stage or session start).
2. **If yes** → use it directly in all API calls within that stage.
3. **If no** → STOP-AND-ASK: "Stage {N} needs {service_name} API access. Please provide your {key_name}."
4. **Once provided** → retain in memory for the session. Do not write to pipeline_state.json or any other file.
5. **Validate Tavily key (NEW — pre-flight check):** After the user provides a Tavily API key, validate it with a cheap test query before any stage uses it:

   ```python
   import httpx
   try:
       response = httpx.post(
           "https://api.tavily.com/search",
           headers={"Content-Type": "application/json"},
           json={"query": "test", "max_results": 1, "api_key": tavily_api_key},
           timeout=15,
       )
       if response.status_code == 200:
           pass  # Key is valid — proceed
       elif response.status_code in (401, 403):
           raise RuntimeError(f"Tavily API returned {response.status_code}")
       else:
           print(f"Tavily key check returned unexpected status {response.status_code}. Proceeding but monitor for errors.")
   except Exception as e:
       # STOP-AND-ASK for a corrected key
       print(f"Tavily API key validation failed: {e}")
       print("Your Tavily API key appears to be invalid or expired.")
       print("Please verify your key at https://app.tavily.com and provide a corrected key.")
       # DO NOT proceed to any Tavily-using stage until a valid key is confirmed
   ```

   **Result handling:**
   - HTTP 200 → key is valid, mark `tavily_api_key_validated: true` in the session_variables dict
   - HTTP 401/403 → **STOP-AND-ASK** the user for a corrected key, then re-validate
   - Network error / timeout → warn the user but do not block; the error will surface naturally at first API use

   This is a single validation step at key registration time, not a recurring health check. It catches expired or mistyped keys before any stage fails mid-execution.

## Key State Tracking

The orchestrator maintains a simple in-memory dictionary:

```
session_variables = {
    "tavily_api_key": "tvly-...",       # provided, validated
    "tavily_api_key_validated": True,   # pre-flight check passed
    "openrouter_api_key": None,         # not yet provided
    "zotero_api_key": None,             # not yet provided
    "zotero_library_id": None,          # not yet provided
}
```

This is NOT persisted in pipeline_state.json or any file. It exists only in the current conversation.

## Stage Declaration

Each stage that needs keys must declare its needs at the top of the stage file:

```
> **API Keys Required:** tavily_api_key
```

This signals to the orchestrator: if this key is not yet registered, STOP-AND-ASK before executing the stage.
