"""
crew.py
-------
Assembles and runs the CrewAI PCB review crew.
"""

import os

from crewai import Crew, Process
from PIL import Image

from agents import build_agents
from llm_utils import extract_schematic_description, get_gemini_llm, with_model_fallback
from market_data import get_usd_pkr_rate
from tasks import build_tasks


def build_crew(
    model_name: str,
    api_key: str,
    schematic_description: str,
    extra_notes: str,
    usd_pkr_rate: float,
    fx_source: str,
    web_search_enabled: bool = True,
) -> Crew:
    """Build a fresh Crew for one Gemini model."""
    llm = get_gemini_llm(model_name, api_key)
    agents = build_agents(llm, web_search_enabled=web_search_enabled)
    tasks = build_tasks(
        agents,
        schematic_description,
        extra_notes,
        usd_pkr_rate=usd_pkr_rate,
        fx_source=fx_source,
        web_search_enabled=web_search_enabled,
    )
    return Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=False,
    )


def run_review(
    images: list[Image.Image],
    api_key: str,
    model_candidates: list[str],
    extra_notes: str,
    status_callback=None,
    web_search_enabled: bool = True,
) -> dict[str, str]:
    """Run vision extraction followed by the five-agent review crew."""
    usd_pkr_rate, fx_source = get_usd_pkr_rate()

    if status_callback:
        status_callback(
            f"💱 Costing conversion: 1 USD ≈ PKR {usd_pkr_rate:,.2f} "
            f"({fx_source})."
        )

    description, vision_model_used = with_model_fallback(
        model_candidates,
        lambda model_name: extract_schematic_description(images, api_key, model_name),
        status_callback=status_callback,
    )

    def _run_crew(model_name: str):
        crew = build_crew(
            model_name,
            api_key,
            description,
            extra_notes,
            usd_pkr_rate=usd_pkr_rate,
            fx_source=fx_source,
            web_search_enabled=web_search_enabled,
        )
        result = crew.kickoff()
        task_outputs = [str(t.output.raw) for t in crew.tasks]
        final_report = str(result.raw) if hasattr(result, "raw") else str(result)
        return task_outputs, final_report

    (task_outputs, final_report), crew_model_used = with_model_fallback(
        model_candidates, _run_crew, status_callback=status_callback
    )

    return {
        "components": task_outputs[0],
        "costing": task_outputs[1],
        "availability": task_outputs[2],
        "engineering": task_outputs[3],
        "final_report": final_report,
        "vision_model_used": vision_model_used,
        "crew_model_used": crew_model_used,
        "usd_pkr_rate": f"{usd_pkr_rate:.4f}",
        "fx_source": fx_source,
        "web_search_enabled": str(web_search_enabled),
    }
