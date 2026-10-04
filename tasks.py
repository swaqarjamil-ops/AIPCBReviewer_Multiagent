"""
tasks.py
--------
Defines the five tasks the crew runs, structured as THREE STAGES instead
of five fully sequential steps, to cut wall-clock time:

    Stage 1 (sync):    Component Locator
    Stage 2 (PARALLEL): Design Costing | Hardware Availability | Engineering Analyst
    Stage 3 (sync):    Reporting Agent (waits for all of Stage 2)

Costing, Availability, and Engineering Analyst only ever depended on the
Component Locator's output, not on each other - they were being run one
after another for no reason. Marking them `async_execution=True` lets
CrewAI fire all three LLM calls at once and wait for them together,
which is the single biggest lever on total run time for this crew.
(CrewAI requires the crew to end with a synchronous task, which Reporting
already is.)
"""

from crewai import Agent, Task


def build_tasks(agents: dict[str, Agent], schematic_description: str, extra_notes: str) -> list[Task]:
    """Build the five review tasks across three execution stages.

    Args:
        agents: Dict of agents from agents.build_agents().
        schematic_description: The text extracted from the schematic
            images by the Gemini vision step (see llm_utils.py).
        extra_notes: Optional free-text context supplied by the user.

    Returns:
        A list of Task objects, ready for a Process.sequential Crew.
        The list order still matters (it's how CrewAI resolves
        `context=[...]` references), but Costing/Availability/
        Engineering now run concurrently rather than one at a time.
    """
    notes_block = f"\nAdditional context from the user:\n{extra_notes}\n" if extra_notes else ""

    # --- Task 1: Component Locator ----------------------------------------
    task_components = Task(
        description=(
            "Using the schematic extraction notes below, produce a clean, "
            "de-duplicated component inventory table (designator | type | "
            "value | likely package | function on the board).\n"
            f"{notes_block}\n"
            f"SCHEMATIC EXTRACTION NOTES:\n{schematic_description}"
        ),
        expected_output=(
            "A markdown table of components, followed by a short list of "
            "any components whose details were unclear or ambiguous."
        ),
        agent=agents["component_locator"],
    )

    # --- Task 2: Design Costing ---------------------------------------------
    task_costing = Task(
        description=(
            "Using the component inventory produced by the Component "
            "Locator, estimate a rough per-component cost and a total BOM "
            "cost range for a low-to-moderate volume build (e.g. 100-1000 "
            "units). Clearly label these as ESTIMATES. Call out the 3-5 "
            "most expensive components and suggest cheaper alternatives "
            "ONLY where it would not compromise the design."
        ),
        expected_output=(
            "A markdown cost table (component | est. unit cost | notes) "
            "plus a total estimated BOM cost range and a short list of "
            "cost-reduction suggestions."
        ),
        agent=agents["design_costing"],
        context=[task_components],
        async_execution=True,  # runs in parallel with Availability + Engineering
    )

    # --- Task 3: Hardware Availability --------------------------------------
    task_availability = Task(
        description=(
            "Using the component inventory produced by the Component "
            "Locator, assess sourcing risk for each notable component: "
            "is it a common, widely available part, or is it exotic, "
            "single-sourced, or prone to long lead times / obsolescence? "
            "Suggest common, multi-sourced alternatives where relevant."
        ),
        expected_output=(
            "A markdown table (component | availability risk: Low/Medium/"
            "High | notes/alternatives), plus a short summary of the "
            "design's overall supply-chain risk."
        ),
        agent=agents["hardware_availability"],
        context=[task_components],
        async_execution=True,  # runs in parallel with Costing + Engineering
    )

    # --- Task 4: Engineering Analyst (deep SI / power / coupling review) ---
    task_engineering = Task(
        description=(
            "Perform a deep engineering review of the schematic described "
            "below, covering exactly these three areas:\n\n"
            "1. SIGNAL INTEGRITY: high-speed/clock/differential pairs "
            "lacking series or termination resistors, impedance-sensitive "
            "nets without a clear reference plane, missing decoupling near "
            "high-speed ICs, and any fan-out/routing choices visible in "
            "the schematic that risk reflections or crosstalk.\n\n"
            "2. POWER AND GROUND LOOPS: decoupling capacitor placement "
            "and values vs. IC power pins, missing bulk/bypass "
            "capacitance, star vs multi-point grounding conflicts, ground "
            "return path length for high-current/high-speed loops, split/ "
            "isolated ground stitching, and power sequencing risks.\n\n"
            "3. COMMON MODE COUPLING: cable/connector shield grounding, "
            "common-mode choke usage (or absence) on I/O and power lines, "
            "isolation barrier crossings, and proximity of noisy switching "
            "nets to sensitive analog or shield references.\n\n"
            "Reference specific designators/nets wherever possible. If "
            "something can't be confirmed from the notes, say so rather "
            "than guessing.\n"
            f"{notes_block}\n"
            f"SCHEMATIC EXTRACTION NOTES:\n{schematic_description}"
        ),
        expected_output=(
            "A markdown report with three clearly labeled subsections "
            "(Signal Integrity, Power and Ground Loops, Common Mode "
            "Coupling), each listing specific issues found and the "
            "concrete fix for each."
        ),
        agent=agents["engineering_analyst"],
        context=[task_components],
        async_execution=True,  # runs in parallel with Costing + Availability
    )

    # --- Task 5: Reporting Agent (final consolidated report) --------------
    task_reporting = Task(
        description=(
            "Combine the component inventory, costing estimate, hardware "
            "availability assessment, and engineering analysis into ONE "
            "polished markdown report using EXACTLY these '##' headings, "
            "in this order, and nothing else before or after them:\n\n"
            "## Executive Summary\n"
            "## Component Inventory\n"
            "## Signal Integrity Analysis\n"
            "## Power and Ground Loop Analysis\n"
            "## Common Mode Coupling Analysis\n"
            "## Design Costing Estimate\n"
            "## Hardware Availability Assessment\n"
            "## Prioritized Recommendations\n\n"
            "The Executive Summary should be 4-6 sentences summarizing "
            "overall design health and the single biggest risk. The "
            "Prioritized Recommendations should be a numbered list, "
            "highest impact first, pulling the most important action "
            "items from ALL the other sections. Do not simply repeat "
            "other agents' text verbatim everywhere - tighten and "
            "de-duplicate where sections overlap."
        ),
        expected_output=(
            "A single complete markdown document following the exact "
            "heading structure specified above."
        ),
        agent=agents["reporting_agent"],
        context=[task_components, task_costing, task_availability, task_engineering],
    )

    return [task_components, task_costing, task_availability, task_engineering, task_reporting]
