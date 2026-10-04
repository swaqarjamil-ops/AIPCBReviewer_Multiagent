"""
app.py
------
CircuitMind AI - AI PCB Multi-Agent Reviewer
Modern Streamlit UI inspired by the CircuitMind v2 layout.
"""

import os

import streamlit as st

from crew import run_review
from export_utils import report_to_docx, report_to_pdf
from pdf_utils import render_pdf_pages_to_images
from report_utils import REPORT_SECTIONS, split_report_into_sections

MODEL_CANDIDATES = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]
RENDER_ZOOM = 2.0

AGENT_SECTIONS = [
    ("components", "Component Locator", "⌕"),
    ("costing", "Design Costing", "₨"),
    ("availability", "Hardware Availability", "▣"),
    ("engineering", "Engineering Analyst", "⌁"),
]


def configure_page():
    """Configure the CircuitMind-style page and global CSS."""
    st.set_page_config(
        page_title="CircuitMind AI | PCB Engineering Reviewer",
        page_icon="🟩",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

        :root {
            --bg: #050a07;
            --panel: #09120d;
            --panel-2: #0c1711;
            --line: #17301f;
            --line-bright: #24522f;
            --green: #65d46e;
            --green-2: #2fbf71;
            --text: #eef8f0;
            --muted: #8da396;
            --warning: #e8c56a;
        }

        .stApp {
            background:
                radial-gradient(circle at 85% 4%, rgba(47,191,113,.11), transparent 27%),
                radial-gradient(circle at 10% 0%, rgba(101,212,110,.07), transparent 25%),
                var(--bg);
            color: var(--text);
            font-family: Inter, sans-serif;
        }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] {
            background: #07100b;
            border-right: 1px solid var(--line);
        }
        [data-testid="stSidebarContent"] { padding-top: 1rem; }
        .block-container { max-width: 1280px; padding-top: 1.7rem; padding-bottom: 4rem; }
        .circuit-logo { color: var(--green); font-weight: 800; letter-spacing: .03em; font-size: 1.02rem; }
        .mono { font-family: 'JetBrains Mono', monospace; }
        .hero {
            position: relative; overflow: hidden; border: 1px solid var(--line-bright);
            border-radius: 22px; padding: 2.2rem 2.3rem; margin-bottom: 1.2rem;
            background: linear-gradient(135deg, rgba(13,31,19,.95), rgba(6,14,9,.98));
            box-shadow: 0 20px 60px rgba(0,0,0,.28);
        }
        .hero:after {
            content: ''; position: absolute; inset: 0; pointer-events: none; opacity: .13;
            background-image: linear-gradient(rgba(101,212,110,.25) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(101,212,110,.25) 1px, transparent 1px);
            background-size: 28px 28px;
            mask-image: linear-gradient(90deg, transparent, black 50%, transparent);
        }
        .hero-kicker { color: var(--green); font: 600 .78rem 'JetBrains Mono', monospace; text-transform: uppercase; letter-spacing: .14em; }
        .hero h1 { margin: .35rem 0 .5rem; font-size: clamp(2rem, 4vw, 3.35rem); line-height: 1.02; letter-spacing: -.045em; }
        .hero p { max-width: 790px; color: #a9bbb0; font-size: 1.02rem; line-height: 1.65; margin: 0; }
        .trace { margin-top: 1.1rem; color: #52725b; font: .72rem 'JetBrains Mono', monospace; }
        .feature-grid { display:grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 1.2rem 0 1.5rem; }
        .feature-card { border:1px solid var(--line); border-radius:16px; padding:1rem 1.05rem; background:rgba(9,18,13,.78); }
        .feature-icon { color:var(--green); font-size:1.2rem; }
        .feature-title { font-weight:700; margin-top:.3rem; }
        .feature-desc { color:var(--muted); font-size:.82rem; margin-top:.25rem; line-height:1.45; }
        .section-label { color:var(--green); font:600 .73rem 'JetBrains Mono', monospace; text-transform:uppercase; letter-spacing:.13em; margin:1.5rem 0 .45rem; }
        .step { display:flex; gap:.7rem; align-items:center; color:#b9c8bd; font-size:.9rem; }
        .step-num { width:27px; height:27px; display:grid; place-items:center; border:1px solid #315c39; border-radius:50%; color:var(--green); font:600 .75rem 'JetBrains Mono'; }
        .status { display:inline-flex; align-items:center; gap:.4rem; border:1px solid #234b2b; border-radius:999px; padding:.35rem .7rem; color:#a7c3ad; background:#09160d; font-size:.75rem; }
        .status-dot { width:7px; height:7px; border-radius:50%; background:var(--green); box-shadow:0 0 10px rgba(101,212,110,.7); }
        div[data-testid="stFileUploader"] { border:1px dashed #31583a; border-radius:16px; background:#08110c; padding:.2rem; }
        div[data-testid="stFileUploader"] section { background:transparent; }
        .stTextArea textarea, .stTextInput input { background:#07100b !important; border-color:#1b3823 !important; }
        .stButton > button, .stDownloadButton > button { border-radius:10px; font-weight:700; min-height:2.65rem; }
        .primary-action button { background:var(--green) !important; color:#061007 !important; border:0 !important; box-shadow:0 0 0 1px rgba(101,212,110,.15), 0 10px 28px rgba(101,212,110,.12); }
        .agent-card { border:1px solid var(--line); border-radius:14px; background:#08110c; padding:1rem; margin-bottom:.7rem; }
        .agent-head { display:flex; align-items:center; justify-content:space-between; gap:1rem; }
        .agent-name { font-weight:700; }
        .agent-state { color:var(--green); font:600 .7rem 'JetBrains Mono'; }
        .metric { border:1px solid var(--line); border-radius:14px; background:#08110c; padding:1rem; }
        .metric-label { color:var(--muted); font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; }
        .metric-value { font:700 1.15rem 'JetBrains Mono'; margin-top:.25rem; }
        .report-shell { border:1px solid var(--line); border-radius:18px; padding:1rem; background:#07100b; }
        @media(max-width:800px){ .feature-grid{grid-template-columns:1fr;} .hero{padding:1.5rem;} }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_secret(name: str, default: str = "") -> str:
    """Read a Streamlit secret with environment fallback."""
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, default))


def get_api_key() -> str:
    """Read the Gemini API key."""
    return get_secret("GEMINI_API_KEY")


def configure_web_search() -> bool:
    """Expose SERPER_API_KEY for distributor web search."""
    key = get_secret("SERPER_API_KEY")
    if key:
        os.environ["SERPER_API_KEY"] = key
    return bool(key)


def render_sidebar(web_search_enabled: bool):
    """Render CircuitMind-style settings and workflow status in the sidebar."""
    with st.sidebar:
        st.markdown('<div class="circuit-logo">▣ CIRCUITMIND AI</div>', unsafe_allow_html=True)
        st.caption("PCB Engineering Reviewer")
        st.markdown("---")
        st.markdown("**Analysis Engine**")
        st.markdown('<div class="status"><span class="status-dot"></span> Gemini multimodal</div>', unsafe_allow_html=True)
        st.markdown("\n**Engineering scope**")
        for item in ["Signal Integrity", "Power & Ground", "EMI & Coupling", "Component Sourcing", "Design Costing"]:
            st.markdown(f"• {item}")
        st.markdown("---")
        st.markdown("**Data sources**")
        st.markdown(
            '<div class="status"><span class="status-dot"></span> DigiKey + Mouser</div>' if web_search_enabled
            else '<div class="status">○ Distributor search not configured</div>',
            unsafe_allow_html=True,
        )
        fx = get_secret("USD_PKR_RATE") or "Live rate"
        st.caption(f"USD → PKR: {fx}")
        st.markdown("---")
        st.caption("CircuitMind AI • Multi-Agent PCB Review")


def render_feature_cards():
    """Render the three primary CircuitMind analysis capabilities."""
    st.markdown(
        """
        <div class="feature-grid">
          <div class="feature-card"><div class="feature-icon">⚡</div><div class="feature-title">Signal Integrity</div><div class="feature-desc">Identify high-speed routing, termination, impedance and coupling risks.</div></div>
          <div class="feature-card"><div class="feature-icon">🔋</div><div class="feature-title">Power & Ground</div><div class="feature-desc">Review rails, decoupling, return paths, loops and power distribution risks.</div></div>
          <div class="feature-card"><div class="feature-icon">📡</div><div class="feature-title">EMI & Coupling</div><div class="feature-desc">Detect common-mode coupling, noise paths and potential EMI concerns.</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero():
    """Render the main product hero area."""
    st.markdown(
        """
        <div class="hero">
          <div class="hero-kicker">AI PCB ENGINEERING REVIEWER</div>
          <h1>Review your PCB before it becomes hardware.</h1>
          <p>Upload a schematic PDF and let a multi-agent engineering workflow analyze signal integrity, power and ground, EMI/coupling, component sourcing, availability and design cost.</p>
          <div class="trace">VCC ──┬──── MCU ───── HIGH SPEED ───── CONNECTOR ── GND &nbsp;•&nbsp; AI REVIEW PIPELINE READY</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def generate_export_files(report: str):
    """Generate Word and PDF report bytes."""
    return report_to_docx(report), report_to_pdf(report)


def render_results(results):
    """Render agent results, consolidated report and export controls."""
    st.markdown('<div class="section-label">Analysis complete</div>', unsafe_allow_html=True)
    metric_cols = st.columns(4)
    metrics = [
        ("Vision model", results["vision_model_used"]),
        ("Crew model", results["crew_model_used"]),
        ("USD / PKR", f'{results["usd_pkr_rate"]}'),
        ("Web sourcing", "ON" if results["web_search_enabled"] == "True" else "OFF"),
    ]
    for col, (label, value) in zip(metric_cols, metrics):
        with col:
            st.markdown(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label">Agent outputs</div>', unsafe_allow_html=True)
    for result_key, title, icon in AGENT_SECTIONS:
        with st.expander(f"{icon}  {title}", expanded=False):
            st.markdown(results[result_key])

    st.markdown('<div class="section-label">Final engineering report</div>', unsafe_allow_html=True)
    sections = split_report_into_sections(results["final_report"])
    tab_titles = [t for t in REPORT_SECTIONS if t in sections] + [t for t in sections if t not in REPORT_SECTIONS]

    if not tab_titles:
        # The Reporting Agent returned nothing, or returned text with no
        # '##' headings (e.g. an empty/garbled response). st.tabs([])
        # raises ValueError on an empty list, so fall back to showing
        # whatever raw text we do have instead of crashing the page.
        st.warning(
            "The reporting agent didn't return a structured report this "
            "run, so here's its raw output instead."
        )
        st.markdown('<div class="report-shell">', unsafe_allow_html=True)
        st.markdown(results["final_report"].strip() or "_No report content was returned._")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        tabs = st.tabs([f"{t}" for t in tab_titles])
        for tab, title in zip(tabs, tab_titles):
            with tab:
                st.markdown('<div class="report-shell">', unsafe_allow_html=True)
                st.markdown(sections[title])
                st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label">Export</div>', unsafe_allow_html=True)
    if st.button("▣  Generate Final Report — Word + PDF", type="primary", width="stretch"):
        with st.spinner("Preparing formatted engineering reports..."):
            docx_bytes, pdf_bytes = generate_export_files(results["final_report"])
        st.session_state["report_docx"] = docx_bytes
        st.session_state["report_pdf"] = pdf_bytes
        st.success("Final report generated. Choose a format below.")

    if "report_docx" in st.session_state:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("⬇ MS Word", st.session_state["report_docx"], "CircuitMind_AI_PCB_Review.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", width="stretch")
        with c2:
            st.download_button("⬇ PDF", st.session_state["report_pdf"], "CircuitMind_AI_PCB_Review.pdf", "application/pdf", width="stretch")
        with c3:
            st.download_button("⬇ Markdown", results["final_report"], "CircuitMind_AI_PCB_Review.md", "text/markdown", width="stretch")


def main():
    """Run the CircuitMind AI Streamlit application."""
    configure_page()
    web_search_enabled = configure_web_search()
    configured_fx = get_secret("USD_PKR_RATE")
    if configured_fx:
        os.environ["USD_PKR_RATE"] = configured_fx

    render_sidebar(web_search_enabled)
    render_hero()
    render_feature_cards()

    if not get_api_key():
        st.error("Gemini API key is not configured. Add `GEMINI_API_KEY` to Streamlit Secrets.")
        return

    st.markdown('<div class="section-label">01 · Add schematic</div>', unsafe_allow_html=True)
    left, right = st.columns([1.35, .65], gap="large")
    with left:
        uploaded_pdf = st.file_uploader(
            "Drop your schematic PDF here",
            type=["pdf"],
            help="Upload the engineering schematic you want reviewed.",
        )
        if uploaded_pdf:
            st.markdown(f'<div class="status"><span class="status-dot"></span> {uploaded_pdf.name} · {uploaded_pdf.size / 1024:.1f} KB</div>', unsafe_allow_html=True)
    with right:
        extra_notes = st.text_area(
            "Design context (optional)",
            placeholder="Examples: 4-layer board, DDR4 interface, USB-C, 24 V input, sensitive ADC...",
            height=132,
        )

    st.markdown('<div class="section-label">02 · Analyze PCB</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown('<div class="step"><span class="step-num">1</span> Upload schematic</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="step"><span class="step-num">2</span> Run multi-agent engineering review</div>', unsafe_allow_html=True)

    st.markdown('<div class="primary-action">', unsafe_allow_html=True)
    run_clicked = st.button("⚡ Analyze My PCB Schematic", type="primary", disabled=uploaded_pdf is None, width="stretch")
    st.markdown('</div>', unsafe_allow_html=True)

    if not web_search_enabled:
        st.info("Distributor sourcing is offline: add `SERPER_API_KEY` to enable DigiKey/Mouser lookup and live pricing.")

    if run_clicked:
        with st.spinner("Rendering schematic pages..."):
            images = render_pdf_pages_to_images(uploaded_pdf.read(), zoom=RENDER_ZOOM)

        # Stash in session_state (not just a local variable) so the
        # preview survives the script reruns Streamlit triggers on every
        # later widget interaction - including clicking a download
        # button - the same way "results" below already does. Without
        # this, the preview/page-count simply vanished on the next rerun.
        st.session_state["preview_images"] = images

        status_box = st.empty()

        def report_status(msg: str):
            """Show live multi-agent progress."""
            status_box.info(msg)

        try:
            with st.spinner("AI agents are reviewing your design..."):
                results = run_review(
                    images=images,
                    api_key=get_api_key(),
                    model_candidates=MODEL_CANDIDATES,
                    extra_notes=extra_notes,
                    status_callback=report_status,
                    web_search_enabled=web_search_enabled,
                )
        except RuntimeError as exc:
            status_box.empty()
            st.error(f"Analysis failed: {exc}")
            return

        status_box.empty()
        st.session_state["results"] = results
        st.session_state.pop("report_docx", None)
        st.session_state.pop("report_pdf", None)
        st.rerun()

    # Rendered independently of run_clicked (and before the results
    # section) so the schematic preview survives later reruns - e.g.
    # clicking any of the export download buttons - instead of vanishing
    # the moment run_clicked is no longer True.
    if "preview_images" in st.session_state:
        imgs = st.session_state["preview_images"]
        with st.expander(f"Schematic preview · {len(imgs)} page(s)", expanded=False):
            preview_cols = st.columns(min(len(imgs), 4) or 1)
            for i, img in enumerate(imgs):
                preview_cols[i % len(preview_cols)].image(img, caption=f"Page {i + 1}", width="stretch")

    if "results" in st.session_state:
        render_results(st.session_state["results"])


if __name__ == "__main__":
    main()
