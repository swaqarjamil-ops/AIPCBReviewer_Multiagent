"""
report_utils.py
----------------
Small helper for turning the Reporting Agent's final markdown into a
dict of sections, so app.py can show them as neat Streamlit tabs.
"""

import re

# Must match the '##' headings requested in tasks.py's reporting task.
REPORT_SECTIONS = [
    "Executive Summary",
    "Component Inventory",
    "Signal Integrity Analysis",
    "Power and Ground Loop Analysis",
    "Common Mode Coupling Analysis",
    "Design Costing Estimate",
    "Hardware Availability Assessment",
    "Prioritized Recommendations",
]


def split_report_into_sections(report_text: str) -> dict[str, str]:
    """Split a markdown report into a dict keyed by its '##' headings.

    Any heading the model produced that isn't in REPORT_SECTIONS is
    bundled under 'Other Notes' so no content is ever silently dropped.
    """
    sections: dict[str, str] = {}
    parts = re.split(r"\n(?=##\s+)", report_text.strip())
    for part in parts:
        match = re.match(r"##\s+(.*?)\n(.*)", part.strip(), re.DOTALL)
        if match:
            title, body = match.group(1).strip(), match.group(2).strip()
            sections[title] = body
        elif part.strip():
            sections.setdefault("Other Notes", "")
            sections["Other Notes"] += part.strip() + "\n"
    return sections
