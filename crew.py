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

    # Soft length guard: very long extractions inflate every downstream
    # agent prompt. Keep a hard cap so token usage stays predictable.
    _MAX_DESC_CHARS = 12000
    if len(description) > _MAX_DESC_CHARS:
        if status_callback:
            status_callback(
                f"✂️ Schematic extraction was {len(description):,} chars; "
                f"truncating to {_MAX_DESC_CHARS:,} for token efficiency."
            )
        description = description[:_MAX_DESC_CHARS] + "\n... [truncated for token efficiency]"

    # Human-readable labels, in the same order tasks.build_tasks() returns
    # them, used only to produce a clear error message below.

    _TASK_LABELS = [
        "Component Locator", "Design Costing", "Hardware Availability",
        "Engineering Analyst", "Reporting Agent",
    ]

    def _task_output_text(task, label: str) -> str:
        """Safely pull the text out of one finished CrewAI task.

        An async task (Costing/Availability/Engineering all run with
        async_execution=True) can occasionally finish with `task.output`
        still None - e.g. an internal tool error inside that task. Doing
        `task.output.raw` in that case used to raise a bare
        AttributeError, which with_model_fallback's broad `except
        Exception` would catch and treat exactly like "the model is
        busy", silently burning through every model in the fallback
        chain before finally surfacing a confusing "All Gemini models
        failed" message with no clue what actually went wrong. Raising a
        specific, task-named error here means that if this run truly
        can't recover, the final error the user sees names the real
        cause instead.
        """
        if task.output is None:
            raise RuntimeError(
                f"The '{label}' task finished without producing output - "
                "this usually means a tool call or sub-task failed "
                "internally, not that the Gemini model was unavailable."
            )
        return str(task.output.raw)

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
        task_outputs = [
            _task_output_text(task, label)
            for task, label in zip(crew.tasks, _TASK_LABELS)
        ]
        # The crew-level result normally mirrors the last (Reporting)
        # task's output; fall back to that task's own output directly if
        # `result` itself is missing/empty for any reason.
        if result is not None and getattr(result, "raw", None):
            final_report = str(result.raw)
        else:
            final_report = task_outputs[-1]
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
