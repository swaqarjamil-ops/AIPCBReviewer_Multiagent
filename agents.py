"""
agents.py
---------
Defines the five CrewAI agents used by the PCB reviewer.

The Component Locator and Design Costing agents use Serper web search
when SERPER_API_KEY is configured. Their prompts explicitly restrict
component sourcing searches to DigiKey and Mouser.
"""

from crewai import Agent, LLM

try:
    from crewai_tools import SerperDevTool
except ImportError:  # pragma: no cover - handled gracefully in app
    SerperDevTool = None


def _distributor_search_tool():
    """Create the web-search tool used for DigiKey/Mouser component lookup."""
    if SerperDevTool is None:
        return None
    # Fewer results = fewer tokens fed back into the agent after each search.
    return SerperDevTool(n_results=4)



def build_agents(llm: LLM, web_search_enabled: bool = True) -> dict[str, Agent]:
    """Create the five review agents, all backed by the supplied LLM."""
    distributor_search = _distributor_search_tool() if web_search_enabled else None
    sourcing_tools = [distributor_search] if distributor_search else []

    component_locator = Agent(
        role="Component Locator & Distributor Research Agent",
        goal=(
            "Produce a clean inventory of every component and, where a "
            "manufacturer part number can be identified, research the "
            "component on DigiKey and Mouser. Record manufacturer, MPN, "
            "package, and distributor source URLs without inventing data."
        ),
        backstory=(
            "You are a meticulous PCB BOM and component sourcing specialist. "
            "You read schematic extraction notes, identify likely manufacturer "
            "part numbers, and use web search to verify listings. For online "
            "component research, search ONLY DigiKey (digikey.com) and Mouser "
            "(mouser.com). If an exact part cannot be verified, say "
            "'Not verified' rather than guessing."
        ),
        tools=sourcing_tools,
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    design_costing = Agent(
        role="Design Costing & Procurement Analyst",
        goal=(
            "Produce a realistic BOM cost estimate using current distributor "
            "listing information where available, with every component price "
            "shown in PKR. Use DigiKey and Mouser listings as the preferred "
            "price sources and clearly distinguish live/listing prices from "
            "engineering estimates."
        ),
        backstory=(
            "You are a hardware procurement analyst. You use web search to "
            "look up exact or closest verified part listings on DigiKey and "
            "Mouser, capture the available unit price/quantity break when "
            "visible, then convert USD prices to PKR using the exchange rate "
            "provided in the task. Never fabricate a distributor price. "
            "When no live price is found, label the PKR value as an estimate."
        ),
        tools=sourcing_tools,
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    hardware_availability = Agent(
        role="Hardware Availability Analyst",
        goal=(
            "Assess how easy or hard each key component will be to source "
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
