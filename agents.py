"""
agents.py
---------
Defines the five CrewAI agents that make up the review crew. Each agent
has a narrow, well-defined role so its output stays focused. All five
share the same underlying Gemini LLM (passed in from llm_utils.py), so
swapping/falling back to a different Gemini model only requires building
a new LLM object, not touching this file.
"""

from crewai import Agent, LLM


def build_agents(llm: LLM) -> dict[str, Agent]:
    """Create the five review agents, all backed by the given LLM.

    Args:
        llm: A crewai.LLM instance (see llm_utils.get_gemini_llm).

    Returns:
        A dict mapping a short key to the corresponding Agent, so
        tasks.py can reference them by name.
    """

    component_locator = Agent(
        role="Component Locator",
        goal=(
            "Produce a clean, organized inventory of every component on "
            "the schematic with its designator, type, value, and function."
        ),
        backstory=(
            "You are a meticulous PCB librarian. You read raw schematic "
            "extraction notes and turn them into an unambiguous, well "
            "organized Bill-of-Materials-style component list that other "
            "engineers can rely on without re-checking the schematic."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    design_costing = Agent(
        role="Design Costing Analyst",
        goal=(
            "Estimate the approximate per-component and total BOM cost "
            "for the design at low-to-moderate production volume."
        ),
        backstory=(
            "You are a hardware procurement analyst with broad knowledge "
            "of typical electronic component pricing. You give realistic, "
            "clearly-labeled ESTIMATES (not live quotes), flag the most "
            "expensive components, and suggest lower-cost alternatives "
            "where it is safe to do so."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    hardware_availability = Agent(
        role="Hardware Availability Analyst",
        goal=(
            "Assess how easy or hard each key component will be to source, "
            "and flag supply-chain risk."
        ),
        backstory=(
            "You are a supply-chain specialist who has watched countless "
            "projects stall because of a single hard-to-find part. You "
            "flag components that are obsolete, single-sourced, exotic, "
            "or prone to long lead times, and suggest common, multi-sourced "
            "alternatives where possible."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    engineering_analyst = Agent(
        role="Senior Signal & Power Integrity Engineer",
        goal=(
            "Perform a deep technical review of the design's Signal "
            "Integrity, Power/Ground loop behavior, and Common-Mode "
            "coupling risk."
        ),
        backstory=(
            "You have 20+ years of hardware design and EMC/SI review "
            "experience. You are direct, technical, and always reference "
            "specific designators or nets. You explain WHY something is a "
            "risk and WHAT to change, never just that 'it could be better'."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    reporting_agent = Agent(
        role="Reporting Agent",
        goal=(
            "Combine every other agent's findings into one polished, "
            "well-structured markdown engineering review report."
        ),
        backstory=(
            "You are a technical editor who turns multiple specialists' "
            "notes into a single coherent, non-repetitive, easy-to-navigate "
            "report for a hardware engineering audience."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    return {
        "component_locator": component_locator,
        "design_costing": design_costing,
        "hardware_availability": hardware_availability,
        "engineering_analyst": engineering_analyst,
        "reporting_agent": reporting_agent,
    }
