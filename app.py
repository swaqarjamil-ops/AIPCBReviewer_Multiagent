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
       reasons over that description (Costing/Availability/Engineering
       run in parallel - see tasks.py), then Reporting consolidates
       everything into one final report.
    5. Every Gemini call automatically retries and falls back across a
       fixed list of models if one is busy/unavailable/retired.
    6. Each agent's result is shown in its own clearly labeled section
       on the main page, plus a final consolidated report with a
       one-click markdown download.

No sidebar: there are no user-facing settings. The Gemini API key comes
from Streamlit secrets (GEMINI_API_KEY), and the model fallback chain is
a fixed constant below - see "Deployment" in README.md for how to set
the secret on Streamlit Community Cloud.
"""

import streamlit as st

from crew import run_review
from pdf_utils import render_pdf_pages_to_images
from report_utils import REPORT_SECTIONS, split_report_into_sections

# Fixed fallback chain: if the first model is busy/unavailable/retired,
# the app automatically retries then moves to the next one in this list.
# There is no UI control for this - edit this constant and redeploy if
# Google renames/retires a model.
MODEL_CANDIDATES = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]

# Fixed rendering quality for turning PDF pages into images (no sidebar
# control for this - 2.0x gives a good sharpness/speed balance).
RENDER_ZOOM = 2.0

# Each entry: (results dict key, section title, icon).
AGENT_SECTIONS = [
    ("components", "Component Locator", "🔎"),
    ("costing", "Design Costing", "💰"),
    ("availability", "Hardware Availability", "📦"),
    ("engineering", "Engineering Analyst", "🛠️"),
]


def configure_page():
    """Set page-level Streamlit config (sidebar collapsed/unused) and styling."""
    st.set_page_config(
        page_title="AI PCB Multi-Agent Reviewer",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="collapsed",  # app has no sidebar controls
    )
    st.markdown(
        """
        <style>
        /* Hide the sidebar and its expand arrow entirely - this app has
           no sidebar controls, everything lives on the main page. */
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
            display: none;
        }
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


def get_api_key() -> str:
    """Read the Gemini API key from Streamlit secrets.

    Returns an empty string if the secret hasn't been configured, so the
    caller can show a friendly setup message instead of crashing.
    """
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:  # noqa: BLE001 - secrets.toml may not exist locally
        return ""


def render_agent_badges():
    """Show a small row of pills listing the 5 crew agents, for context."""
    st.markdown(
        '<span class="agent-pill">🔎 Component Locator</span>'
        '<span class="agent-pill">💰 Design Costing</span>'
        '<span class="agent-pill">📦 Hardware Availability</span>'
        '<span class="agent-pill">🛠️ Engineering Analyst</span>'
        '<span class="agent-pill">📝 Reporting Agent</span>',
        unsafe_allow_html=True,
    )


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
    render_agent_badges()
    st.write("")

    api_key = get_api_key()
    if not api_key:
        st.error(
            "No Gemini API key found. Add `GEMINI_API_KEY` to this app's "
            "Streamlit secrets (Settings → Secrets on Streamlit Community "
            "Cloud, or `.streamlit/secrets.toml` locally) and reload."
        )
        return

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
        with st.spinner("Rendering schematic pages..."):
            images = render_pdf_pages_to_images(uploaded_pdf.getvalue(), zoom=RENDER_ZOOM)

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
                    api_key=api_key,
                    model_candidates=MODEL_CANDIDATES,
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

        # --- One clearly separated section per agent, shown directly on
        # the page (not tucked away in a collapsed expander) -------------
        st.header("🧩 Agent-by-Agent Results")
        for result_key, title, icon in AGENT_SECTIONS:
            with st.container(border=True):
                st.subheader(f"{icon} {title}")
                st.markdown(results[result_key])

        # --- Final consolidated report (Reporting Agent's output) -------
        st.markdown("---")
        st.header("📝 Final Consolidated Report")
        sections = split_report_into_sections(results["final_report"])
        tab_titles = [t for t in REPORT_SECTIONS if t in sections] + \
                     [t for t in sections if t not in REPORT_SECTIONS]
        #if no structured headers are present fallback to default settings
        if tab_titles:
            tabs = st.tabs([f"🔹 {t}" for t in tab_titles])
            for tab, title in zip(tabs, tab_titles):
                with tab:
                    st.markdown(sections[title])
        else:
             st.markdown(results.get("final_report", "*No report content was generated.*"))

        st.download_button(
            "⬇️ Download full report (Markdown)",
            data=results["final_report"],
            file_name="pcb_multi_agent_review.md",
            mime="text/markdown",
        )


if __name__ == "__main__":
    main()
