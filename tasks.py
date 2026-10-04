"""
tasks.py
--------
Defines the five CrewAI tasks.

Stage 1: Component Locator + distributor listing research.
Stage 2: Design Costing | Hardware Availability | Engineering Analyst (parallel).
Stage 3: Reporting Agent.
"""

from crewai import Agent, Task


def build_tasks(
    agents: dict[str, Agent],
    schematic_description: str,
    extra_notes: str,
    usd_pkr_rate: float,
    fx_source: str,
    web_search_enabled: bool = True,
) -> list[Task]:
    """Build the five review tasks with live sourcing and PKR costing."""
    notes_block = f"\nAdditional context from the user:\n{extra_notes}\n" if extra_notes else ""

    web_source_instruction = (
        "WEB SEARCH IS ENABLED. For component listing research, use the web "
        "search tool with queries restricted to site:digikey.com and/or "
        "site:mouser.com. Prefer exact manufacturer part numbers. Include "
        "the distributor page URL and any visible unit price/quantity break. "
        "Do not invent prices, stock, or URLs."
        if web_search_enabled
        else
        "WEB SEARCH IS NOT ENABLED. Do not claim live distributor verification. "
        "Mark distributor URLs/prices as Not verified and use engineering estimates only."
    )

    task_components = Task(
        description=(
            "Using the schematic extraction notes below, produce a clean, "
            "de-duplicated component inventory table with these columns: "
            "Designator | Type | Value | Manufacturer/MPN | Package | "
            "Function | DigiKey/Mouser Listing | Source Status.\n\n"
            f"{web_source_instruction}\n"
            "For generic passives, group identical values only when the "
            "designators can be listed explicitly. For ICs/connectors and "
            "other procurement-critical parts, identify an exact MPN when "
            "the schematic provides enough information.\n"
            f"{notes_block}\n"
            f"SCHEMATIC EXTRACTION NOTES:\n{schematic_description}"
        ),
        expected_output=(
            "A markdown inventory table followed by a short list of "
            "ambiguous/unverified parts. Any live distributor URL must point "
            "to DigiKey or Mouser."
        ),
        agent=agents["component_locator"],
    )

    task_costing = Task(
        description=(
            "Using the component inventory produced by the Component Locator, "
            "prepare a BOM cost estimate for approximately 100-1000 units. "
            "ALL component prices in the final table must be shown in PKR. "
            f"Use USD-to-PKR conversion rate {usd_pkr_rate:.4f} "
            f"({fx_source}) for USD listings. "
            "Use DigiKey and Mouser as preferred web sources when exact MPNs "
            "are available. Search those domains with site: restrictions. "
            "For each part show: Designator | MPN | Source | Source Currency "
            "| Source Unit Price | PKR Unit Price | Price Basis | Notes. "
            "If a current listing cannot be verified, provide a clearly "
            "labeled estimated PKR range rather than inventing a live price. "
            "Distinguish live/listing prices from estimates. Include the "
            "estimated total BOM cost in PKR and identify the 3-5 largest "
            "cost contributors. Do not present a distributor price as a "
            "guaranteed quotation."
        ),
        expected_output=(
            "A markdown costing table with PKR prices, total BOM cost range "
            "in PKR, source URLs where verified, price-basis labels, and "
            "cost-reduction observations."
        ),
        agent=agents["design_costing"],
        context=[task_components],
        async_execution=True,
    )

    task_availability = Task(
        description=(
            "Using the component inventory produced by the Component "
            "Locator, assess sourcing risk for each notable component: "
            "common/widely available, multi-sourced, single-sourced, "
            "obsolete, or prone to long lead times. Use any verified "
            "DigiKey/Mouser listing evidence already provided by the "
            "Component Locator, but do not invent stock status. Suggest "
            "common alternatives where relevant."
        ),
        expected_output=(
            "A markdown table (component | availability risk | evidence | "
            "notes/alternatives), plus an overall supply-chain summary."
        ),
        agent=agents["hardware_availability"],
        context=[task_components],
        async_execution=True,
    )

    task_engineering = Task(
        description=(
            "Perform a deep engineering review of the schematic described "
            "below, covering exactly these three areas:\n\n"
            "1. SIGNAL INTEGRITY: high-speed/clock/differential pairs "
            "lacking series or termination resistors, impedance-sensitive "
            "nets without a clear reference plane, missing decoupling near "
            "high-speed ICs, and fan-out/routing choices visible in the "
            "schematic that risk reflections or crosstalk.\n\n"
            "2. POWER AND GROUND LOOPS: decoupling capacitor placement "
            "and values vs. IC power pins, missing bulk/bypass capacitance, "
            "star vs multi-point grounding conflicts, ground return path "
            "length for high-current/high-speed loops, split/isolated ground "
            "stitching, and power sequencing risks.\n\n"
            "3. COMMON MODE COUPLING: cable/connector shield grounding, "
            "common-mode choke usage (or absence) on I/O and power lines, "
            "isolation barrier crossings, and proximity of noisy switching "
            "nets to sensitive analog or shield references.\n\n"
            "Reference specific designators/nets wherever possible. If "
            "something can't be confirmed from the notes, say so rather "
            "than guessing.\n"
            f"{notes_block}\nSCHEMATIC EXTRACTION NOTES:\n{schematic_description}"
        ),
        expected_output=(
            "A markdown report with Signal Integrity, Power and Ground "
            "Loops, and Common Mode Coupling subsections, each listing "
            "specific issues and concrete fixes."
        ),
        agent=agents["engineering_analyst"],
        context=[task_components],
        async_execution=True,
    )

    task_reporting = Task(
        description=(
            "Combine the component inventory, PKR costing estimate, "
            "hardware availability assessment, and engineering analysis "
            "into ONE polished markdown report using EXACTLY these headings, "
            "in this order, and nothing else before or after them:\n\n"
            "## Executive Summary\n"
            "## Component Inventory\n"
            "## Signal Integrity Analysis\n"
            "## Power and Ground Loop Analysis\n"
            "## Common Mode Coupling Analysis\n"
            "## Design Costing Estimate\n"
            "## Hardware Availability Assessment\n"
            "## Prioritized Recommendations\n\n"
            "Preserve verified DigiKey/Mouser source URLs in the component "
            "and costing sections. All prices must remain in PKR. Clearly "
            "label live/listing values versus estimates. The Executive "
            "Summary should be 4-6 sentences. Prioritized Recommendations "
            "should be a numbered list, highest impact first, based on all "
            "other sections."
        ),
        expected_output=(
            "A complete markdown document following the exact heading "
            "structure specified above, including PKR costing and "
            "DigiKey/Mouser source links where verified."
        ),
        agent=agents["reporting_agent"],
        context=[task_components, task_costing, task_availability, task_engineering],
    )

    return [
        task_components,
        task_costing,
        task_availability,
        task_engineering,
        task_reporting,
    ]
