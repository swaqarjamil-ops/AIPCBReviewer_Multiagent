# 🧠 AI PCB Multi-Agent Reviewer

A Streamlit app that reviews schematic PDFs using a **5-agent CrewAI
crew** powered by **Google Gemini**. No sidebar/settings - everything
is on the main page, and the API key comes from Streamlit secrets.

| Agent | Job |
|---|---|
| 🔎 Component Locator | Builds a clean component inventory from the schematic |
| 💰 Design Costing | Estimates per-component and total BOM cost |
| 📦 Hardware Availability | Flags hard-to-source / single-sourced parts |
| 🛠️ Engineering Analyst | Deep Signal Integrity, Power/Ground Loop, and Common-Mode Coupling review |
| 📝 Reporting Agent | Merges everything into one polished markdown report |

Each agent's result is shown in **its own section on the front page**
(Component Locator, Design Costing, Hardware Availability, Engineering
Analyst), followed by the Reporting Agent's final consolidated report.

## Architecture

```
PDF upload
   └─> pdf_utils.py      render pages to images
   └─> llm_utils.py       Gemini VISION call → detailed text description
   └─> agents.py          defines the 5 CrewAI agents
   └─> tasks.py           defines the 5 tasks, in 3 execution stages
   └─> crew.py            assembles + runs the crew, with model fallback
   └─> report_utils.py    splits the final report into UI tabs
   └─> app.py             Streamlit UI (entry point, no sidebar)
```

The schematic images are only looked at **once**, in a single Gemini
vision call that writes a detailed text description. Every CrewAI agent
then reasons over that text - this keeps the multi-agent logic simple,
fast, and token-efficient.

### Execution stages (for speed)

```
Stage 1 (sync)      Component Locator
Stage 2 (PARALLEL)  Design Costing | Hardware Availability | Engineering Analyst
Stage 3 (sync)      Reporting Agent (waits for all of Stage 2)
```

Costing, Availability, and Engineering only ever depend on the
Component Locator's output, not on each other, so they run
concurrently (`async_execution=True` in `tasks.py`) instead of one
after another.

## Automatic model retry / fallback

Every Gemini call (the vision step AND the crew run) goes through
`llm_utils.with_model_fallback()`: it retries the current model a
couple of times, and if it's still busy/unavailable/rate-limited, moves
on to the next model in the fallback chain. A permanent error (like a
404 for a retired model) skips retries and falls back immediately.

Fixed fallback chain (`MODEL_CANDIDATES` in `app.py`):
```
gemini-3.8-flash, gemini-3.7-flash, gemini-3.6-flash, gemini-3.5-flash
```
There's no sidebar control for this - edit the `MODEL_CANDIDATES` list
in `app.py` and redeploy if Google renames/retires a model. Double-check
current model names at https://ai.google.dev/gemini-api/docs/models,
since Google periodically renames/retires model versions - for example,
the entire Gemini 2.5 series (Pro/Flash/Flash-Lite) is being retired on
October 20, 2026 and already returns a 404 for new API keys.

## Libraries used

- **`google-genai`** (`from google import genai`) - Google's current,
  actively-maintained Gen AI SDK. The older `google-generativeai`
  package (`import google.generativeai as genai`) is deprecated
  (legacy support ended Nov 30, 2025) and is intentionally **not**
  used here.
- **`crewai`** - pinned to `>=1.15.0`, the current major release line.
- Streamlit calls use the current `width="stretch"` parameter instead
  of the deprecated `use_container_width`.

## Run locally

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then edit .streamlit/secrets.toml and paste in your real Gemini API key
streamlit run app.py
```

Get a key at https://aistudio.google.com/apikey. Upload a schematic
PDF and click **Run Multi-Agent Analysis** - there's nothing else to
configure.

## Deploy via GitHub + Streamlit Community Cloud

1. Create a new GitHub repo and push ALL of these files to its **root**
   (no subfolders): `app.py`, `agents.py`, `tasks.py`, `crew.py`,
   `llm_utils.py`, `pdf_utils.py`, `report_utils.py`, `requirements.txt`,
   `README.md`, `.gitignore`. (`.streamlit/secrets.toml.example` is
   optional/informational - never push a real `secrets.toml`.)
2. Go to https://share.streamlit.io/ and click **New app**.
3. Select your repo/branch, set the main file path to `app.py`.
4. Before (or right after) deploying, open the app's **Settings →
   Secrets** and add:
   ```toml
   GEMINI_API_KEY = "your-real-key-here"
   ```
5. Deploy. Every visitor to the app shares this one key - there's no
   per-user API key input in the UI.

## Notes

- This app gives cost/availability **estimates** based on the model's
  general knowledge, not live distributor pricing or stock data - treat
  those sections as a starting point, not a quote.
- Larger/more complex schematics will use more tokens and take longer.
