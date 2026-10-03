"""
llm_utils.py
------------
Everything related to talking to Google Gemini models lives here:

1. A generic "try model A, if it's busy/unavailable fall back to model B,
   C, ..." retry helper (`with_model_fallback`), used for BOTH the raw
   vision extraction call and the CrewAI crew run.
2. `extract_schematic_description()` - a single multimodal Gemini call
   that looks at the rendered schematic page images and writes a
   detailed textual description (components, values, nets, topology).
   This text is then what the CrewAI agents reason over, since CrewAI
   agents work with text, not raw images.
3. `get_gemini_llm()` - builds a CrewAI-compatible LLM object (CrewAI
   uses LiteLLM under the hood) pointed at a specific Gemini model.

Default fallback chain (edit in app.py sidebar, no code change needed):
    gemini-3-pro -> gemini-3.5-flash -> gemini-2.5-pro -> gemini-2.5-flash

Note: this uses the `google-genai` SDK (`from google import genai`), the
current unified Gen AI client. The older `google-generativeai` package
(`import google.generativeai as genai`) was deprecated by Google (legacy
support ended Nov 30, 2025) and should not be used in new code.
"""

import time

from crewai import LLM
from google import genai
from PIL import Image

# How many times to retry the SAME model before moving to the next one
# in the fallback list, and how long to wait between retries (seconds).
MAX_RETRIES_PER_MODEL = 2
RETRY_BACKOFF_SECONDS = 3


def with_model_fallback(model_candidates: list[str], call_fn, status_callback=None):
    """Try `call_fn(model_name)` across a list of models until one works.

    This is the core "if the model is busy/unavailable, retry then fall
    back to the next model" logic, reused for both the vision-extraction
    step and the CrewAI crew run.

    Args:
        model_candidates: Ordered list of Gemini model names to try,
            e.g. ["gemini-3-pro", "gemini-3.5-flash", "gemini-2.5-pro"].
        call_fn: A function that takes a single model name and returns
            a result, raising an exception on failure (rate limit,
            model overloaded, timeout, etc).
        status_callback: Optional function(str) used to report progress
            to the Streamlit UI (e.g. st.write).

    Returns:
        A tuple (result, model_name_that_succeeded).

    Raises:
        RuntimeError: If every model in the list fails every retry.
    """
    last_error = None
    for model_name in model_candidates:
        for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
            try:
                if status_callback:
                    status_callback(f"🔄 Trying `{model_name}` (attempt {attempt}/{MAX_RETRIES_PER_MODEL})...")
                result = call_fn(model_name)
                if status_callback:
                    status_callback(f"✅ `{model_name}` succeeded.")
                return result, model_name
            except Exception as exc:  # noqa: BLE001 - we want to catch & fall back on ANY provider error
                last_error = exc
                # A 404 ("model not found" / retired model) will NEVER
                # succeed on retry - skip straight to the next model
                # instead of burning time retrying something unfixable.
                is_permanent_error = "404" in str(exc)
                if status_callback:
                    reason = "model unavailable" if is_permanent_error else "retrying/falling back"
                    status_callback(f"⚠️ `{model_name}` failed ({exc}). {reason}...")
                if is_permanent_error:
                    break
                time.sleep(RETRY_BACKOFF_SECONDS)
    raise RuntimeError(
        f"All Gemini models in the fallback list failed. Last error: {last_error}"
    )


def extract_schematic_description(images: list[Image.Image], api_key: str, model_name: str) -> str:
    """Use a Gemini vision call to turn schematic page images into text.

    This is the ONE place the raw images are actually looked at. The
    resulting rich text description is then fed to every CrewAI agent,
    so the agents stay simple, fast, and purely text-based.

    Args:
        images: Rendered schematic page images (see pdf_utils.py).
        api_key: Google AI Studio / Gemini API key.
        model_name: Which Gemini model to use for this call.

    Returns:
        A detailed plain-text description of the schematic's components,
        reference designators, values, nets, and visible topology.
    """
    client = genai.Client(api_key=api_key)

    prompt = (
        "You are looking at page images of an electronic schematic (possibly "
        "multiple pages of the same design). Write a thorough, structured, "
        "plain-text extraction covering:\n"
        "1. Every component you can identify: reference designator, type "
        "(resistor, capacitor, IC, connector, etc.), value, and package if "
        "visible.\n"
        "2. Key nets and how components connect (power rails, ground, "
        "high-speed/clock/differential signals, analog vs digital sections).\n"
        "3. Any connectors, test points, or off-board interfaces.\n"
        "4. The overall topology/architecture you can infer (e.g. "
        "'microcontroller with SPI flash, USB interface, and a buck "
        "regulator feeding a 3.3V rail').\n"
        "Be exhaustive and specific - this text will be the ONLY thing other "
        "engineers use to analyze the design, so do not skip details. If "
        "something is unreadable, say so rather than guessing."
    )

    # The google-genai SDK accepts a list mixing PIL images and text
    # directly in `contents` - PIL.Image objects are auto-converted.
    contents = list(images) + [prompt]
    response = client.models.generate_content(model=model_name, contents=contents)
    return response.text


def get_gemini_llm(model_name: str, api_key: str, temperature: float = 0.2) -> LLM:
    """Build a CrewAI LLM object pointed at a specific Gemini model.

    CrewAI uses LiteLLM internally, which expects Gemini models in the
    form "gemini/<model-name>".

    Args:
        model_name: e.g. "gemini-3-pro".
        api_key: Google AI Studio / Gemini API key.
        temperature: Sampling temperature (low = more consistent/factual).

    Returns:
        A configured crewai.LLM instance ready to hand to Agents.
    """
    return LLM(model=f"gemini/{model_name}", api_key=api_key, temperature=temperature)
