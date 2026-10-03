"""
app.py
------
Streamlit front end for the AI PCB Multi-Agent Reviewer.

Pipeline:
    1. User uploads a schematic PDF and (optionally) types extra context.
    2. PDF pages are rendered to images (pdf_utils.py).
    3. A Gemini vision call turns those images into a detailed text
       description of the schematic (llm_utils.py).
    4. A 5-agent CrewAI crew - Component Locator, Design Costing,
       Hardware Availability, Engineering Analyst, Reporting Agent -
       reasons over that description sequentially (agents.py, tasks.py,
       crew.py).
    5. Every Gemini call automatically retries and falls back across a
       user-configurable list of models if one is busy/unavailable.
    6. Results are shown as tabs, with a one-click markdown download.

Deployment: push this whole folder to a GitHub repo and deploy on
Streamlit Community Cloud with app.py as the entry point. Users paste
their own Gemini API key into the sidebar at runtime - no secret needs
to live in the repo.
"""

import streamlit as st

from crew import run_review
from pdf_utils import render_pdf_pages_to_images
from report_utils import REPORT_SECTIONS, split_report_into_sections

# Default fallback chain: if the first model is busy/unavailable, the
# app automatically retries then moves to the next one in this list.
# Users can edit this in the sidebar without touching any code.
# NOTE: the Gemini 2.5 series (Pro/Flash/Flash-Lite) is being retired by
# Google (Oct 20, 2026) and already returns 404 for new API keys - so the
# chain below uses the current Gemini 3.x line instead.
DEFAULT_MODEL_CHAIN = "gemini-3.1-pro, gemini-3.8-flash, gemini-3.5-flash, gemini-3.1-flash-lite"


def configure_page():
    """Set page-level Streamlit config and inject light custom styling."""
    st.set_page_config(page_title="AI PCB Multi-Agent Reviewer", page_icon="🧠", layout="wide")
    st.markdown(
        """
        <style>
        .main-title {
            font-size: 2.3rem;
            font-weight: 800;
            background: linear-gradient(90deg, #7C3AED, #06B6D4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0;
        }
        .subtitle { color: #94A3B8; font-size: 1.05rem; margin-top: 0.2rem; }
        .stButton>button { border-radius: 10px; font-weight: 600; padding: 0.6rem 1.4rem; }
        .agent-pill {
            display: inline-block; padding: 0.15rem 0.7rem; border-radius: 999px;
            background: #1E293B; color: #67E8F9; font-size: 0.8rem; margin-right: 0.3rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> dict:
    """Render sidebar controls and return the chosen settings."""
    with st.sidebar:
        st.header("⚙️ Settings")
        api_key = st.text_input(
            "Google Gemini API Key",
            type="password",
            help="From https://aistudio.google.com/apikey - used only for this session.",
        )
        model_chain_raw = st.text_input(
            "Gemini model fallback chain",
            value=DEFAULT_MODEL_CHAIN,
            help="Comma-separated, tried in order. If a model is busy/unavailable, "
                 "the app automatically retries then falls back to the next one.",
        )
        model_candidates = [m.strip() for m in model_chain_raw.split(",") if m.strip()]

        zoom = st.slider(
            "Rendering quality (zoom)", min_value=1.0, max_value=4.0, value=2.0, step=0.5,
            help="Higher = sharper page images for the vision step, but slower/more tokens.",
        )

        st.markdown("---")
        st.markdown(
            "**Crew of 5 agents:**  \n"
            '<span class="agent-pill">🔎 Component Locator</span>'
            '<span class="agent-pill">💰 Design Costing</span>'
            '<span class="agent-pill">📦 Hardware Availability</span>'
            '<span class="agent-pill">🛠️ Engineering Analyst</span>'
            '<span class="agent-pill">📝 Reporting Agent</span>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Your schematic is sent directly to the Gemini API for analysis "
            "and is not stored by this app."
        )
    return {"api_key": api_key, "model_candidates": model_candidates, "zoom": zoom}


def main():
    """Entry point: wires together the UI, PDF rendering, and the crew."""
    configure_page()

    st.markdown('<p class="main-title">🧠 AI PCB Multi-Agent Reviewer</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Upload a schematic PDF and a crew of 5 AI agents '
        'will inventory parts, estimate cost, check availability, and run a '
        'deep signal-integrity / power-ground / common-mode review - powered '
        'by Google Gemini.</p>',
        unsafe_allow_html=True,
    )
    st.write("")

    settings = render_sidebar()

    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded_pdf = st.file_uploader("📄 Upload schematic (PDF)", type=["pdf"])
    with col2:
        extra_notes = st.text_area(
            "Optional design context",
            placeholder="e.g. 4-layer board, DDR4 on page 3, USB-C on page 5...",
            height=100,
        )

    run_clicked = st.button("🚀 Run Multi-Agent Analysis", type="primary", disabled=uploaded_pdf is None)

    if run_clicked:
        if not settings["api_key"]:
            st.error("Please enter your Gemini API key in the sidebar first.")
            return
        if not settings["model_candidates"]:
            st.error("Please provide at least one Gemini model in the sidebar.")
            return

        with st.spinner("Rendering schematic pages..."):
            images = render_pdf_pages_to_images(uploaded_pdf.read(), zoom=settings["zoom"])

        st.success(f"Rendered {len(images)} page(s).")
        with st.expander("📎 Preview submitted pages", expanded=False):
            preview_cols = st.columns(min(len(images), 4) or 1)
            for i, img in enumerate(images):
                preview_cols[i % len(preview_cols)].image(img, caption=f"Page {i + 1}", width="stretch")

        status_box = st.empty()

        def report_status(msg: str):
            """Stream live progress messages into the UI while the crew runs."""
            status_box.info(msg)

        try:
            with st.spinner("Crew is working: locating parts, then costing, availability, and "
                             "the deep engineering analysis run in parallel..."):
                results = run_review(
                    images=images,
                    api_key=settings["api_key"],
                    model_candidates=settings["model_candidates"],
                    extra_notes=extra_notes,
                    status_callback=report_status,
                )
        except RuntimeError as exc:
            st.error(f"Analysis failed: {exc}")
            return

        status_box.empty()
        st.session_state["results"] = results

    # Display the most recent results, if any exist in this session.
    if "results" in st.session_state:
        results = st.session_state["results"]
        st.markdown("---")
        st.caption(
            f"Vision extraction model: `{results['vision_model_used']}`  •  "
            f"Crew reasoning model: `{results['crew_model_used']}`"
        )
        st.subheader("📊 Engineering Review Report")

        sections = split_report_into_sections(results["final_report"])
        tab_titles = [t for t in REPORT_SECTIONS if t in sections] + \
                     [t for t in sections if t not in REPORT_SECTIONS]
        tabs = st.tabs([f"🔹 {t}" for t in tab_titles])
        for tab, title in zip(tabs, tab_titles):
            with tab:
                st.markdown(sections[title])

        st.download_button(
            "⬇️ Download full report (Markdown)",
            data=results["final_report"],
            file_name="pcb_multi_agent_review.md",
            mime="text/markdown",
        )

        with st.expander("🔍 See each agent's raw output", expanded=False):
            st.markdown("**🔎 Component Locator**")
            st.markdown(results["components"])
            st.markdown("**💰 Design Costing**")
            st.markdown(results["costing"])
            st.markdown("**📦 Hardware Availability**")
            st.markdown(results["availability"])
            st.markdown("**🛠️ Engineering Analyst**")
            st.markdown(results["engineering"])


if __name__ == "__main__":
    main()
