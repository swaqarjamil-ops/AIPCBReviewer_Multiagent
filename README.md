# 🧠 AI PCB Multi-Agent Reviewer

A Streamlit app that reviews schematic PDFs using a **5-agent CrewAI
crew** powered by **Google Gemini**:

| Agent | Job |
|---|---|
| 🔎 Component Locator | Builds a clean component inventory from the schematic |
| 💰 Design Costing | Estimates per-component and total BOM cost |
| 📦 Hardware Availability | Flags hard-to-source / single-sourced parts |
| 🛠️ Engineering Analyst | Deep Signal Integrity, Power/Ground Loop, and Common-Mode Coupling review |
| 📝 Reporting Agent | Merges everything into one polished markdown report |

## Architecture

```
PDF upload
   └─> pdf_utils.py      render pages to images
   └─> llm_utils.py       Gemini VISION call → detailed text description
   └─> agents.py          defines the 5 CrewAI agents
   └─> tasks.py           defines the 5 sequential tasks (text-only)
   └─> crew.py            assembles + runs the crew, with model fallback
   └─> report_utils.py    splits the final report into UI tabs
   └─> app.py             Streamlit UI (entry point)
```

The schematic images are only looked at **once**, in a single Gemini
vision call that writes a detailed text description. Every CrewAI agent
then reasons over that text - this keeps the multi-agent logic simple,
fast, and token-efficient.

## Automatic model retry / fallback

Every Gemini call (the vision step AND the crew run) goes through
`llm_utils.with_model_fallback()`: it retries the current model a couple
of times, and if it's still busy/unavailable/rate-limited, moves on to
the next model in the fallback chain you configure in the sidebar.

Default chain:
```
gemini-3-pro, gemini-3.5-flash, gemini-2.5-pro, gemini-2.5-flash
```
Edit this list in the sidebar (no code changes needed) to match whatever
models your API key has access to. Double-check current model names at
https://ai.google.dev/gemini-api/docs/models before deploying, since
Google periodically renames/retires model versions.

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
streamlit run app.py
```

Paste your **Gemini API key** (from https://aistudio.google.com/apikey)
into the sidebar, upload a schematic PDF, and click **Run Multi-Agent
Analysis**.

## Deploy via GitHub + Streamlit Community Cloud

1. Create a new GitHub repo and push ALL of these files to its **root**
   (no subfolders): `app.py`, `agents.py`, `tasks.py`, `crew.py`,
   `llm_utils.py`, `pdf_utils.py`, `report_utils.py`, `requirements.txt`,
   `README.md`.
2. Go to https://share.streamlit.io/ and click **New app**.
3. Select your repo/branch, set the main file path to `app.py`, and
   deploy.
4. Each user enters their own Gemini API key in the sidebar at runtime -
   no key needs to be stored in the repo or in Streamlit secrets.

   *(Optional)* To bake in a shared key instead, add
   `GEMINI_API_KEY = "..."` under **App settings → Secrets** and update
   `render_sidebar()` in `app.py` to default to
   `st.secrets.get("GEMINI_API_KEY", "")`.

## Notes

- This app gives cost/availability **estimates** based on the model's
  general knowledge, not live distributor pricing or stock data - treat
  those sections as a starting point, not a quote.
- Larger/more complex schematics will use more tokens and take longer;
  the "Rendering quality" slider trades image sharpness for speed/cost.
