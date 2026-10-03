"""
crew.py
-------
Assembles the CrewAI Crew (agents + tasks) for one Gemini model, and
provides the top-level `run_review()` function that app.py calls. All
the "try this Gemini model, fall back to the next one if it's busy" logic
lives in llm_utils.with_model_fallback and is reused for both the vision
extraction step and the crew run itself.

Per tasks.py, the crew now runs in three stages instead of five fully
sequential steps - Component Locator, then Costing/Availability/
Engineering IN PARALLEL, then Reporting - which is the main speedup over
the previous fully-sequential version.
"""

from crewai import Crew, Process
from PIL import Image

from agents import build_agents
from llm_utils import extract_schematic_description, get_gemini_llm, with_model_fallback
from tasks import build_tasks


def build_crew(model_name: str, api_key: str, schematic_description: str, extra_notes: str) -> Crew:
    """Build a fresh Crew (new agents + tasks) for a given Gemini model.

    A new Crew is built per attempt (rather than mutating an existing
    one) so that falling back to a different model is simple and safe.

    Args:
        model_name: Gemini model to power every agent in this crew.
        api_key: Google AI Studio / Gemini API key.
        schematic_description: Text extracted from the schematic images.
        extra_notes: Optional free-text context from the user.

    Returns:
        A ready-to-run crewai.Crew using a sequential process.
    """
    llm = get_gemini_llm(model_name, api_key)
    agents = build_agents(llm)
    tasks = build_tasks(agents, schematic_description, extra_notes)
    return Crew(agents=list(agents.values()), tasks=tasks, process=Process.sequential, verbose=False)


def run_review(
    images: list[Image.Image],
    api_key: str,
    model_candidates: list[str],
    extra_notes: str,
    status_callback=None,
) -> dict[str, str]:
    """Run the full two-stage review: vision extraction, then the crew.

    Args:
        images: Rendered schematic page images.
        api_key: Google AI Studio / Gemini API key.
        model_candidates: Ordered list of Gemini models to try/fall back
            across, e.g. ["gemini-3-pro", "gemini-3.5-flash", ...].
        extra_notes: Optional free-text context from the user.
        status_callback: Optional function(str) for live progress updates
            in the Streamlit UI.

    Returns:
        A dict with each agent's raw output plus the final report:
        {
            "components": "...",
            "costing": "...",
            "availability": "...",
            "engineering": "...",
            "final_report": "...",
            "model_used": "gemini-3-pro",
        }
    """
    # Stage 1: look at the images once, write a detailed text description.
    description, vision_model_used = with_model_fallback(
        model_candidates,
        lambda model_name: extract_schematic_description(images, api_key, model_name),
        status_callback=status_callback,
    )

    # Stage 2: run the 5-agent crew over that text description.
    def _run_crew(model_name: str):
        crew = build_crew(model_name, api_key, description, extra_notes)
        result = crew.kickoff()
        # Pull each task's individual output so the UI can show them
        # separately, in addition to the final consolidated report.
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
    }
