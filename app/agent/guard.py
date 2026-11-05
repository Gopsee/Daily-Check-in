"""Output guard: checks the agent's reflection in code before anyone sees it.

The prompt asks for no phone numbers, helpline names, medication advice or diagnosis.
This hook enforces that after the model replies, so a prompt the model ignores
(or a journal note that tries to steer it) can't put those in front of the user.
It only ever replaces the reflection; it never touches the risk fields.
"""

import logging
import re

from strands.hooks import AfterInvocationEvent, HookProvider, HookRegistry

from app.models import AgentOutput

log = logging.getLogger(__name__)

# Patterns run against lowercased text with curly apostrophes straightened.
CHECKS: dict[str, re.Pattern] = {
    # 3+ digits, optionally separated: 988, 14416, 1-800-891-4416. "7.5 hours" and "24/7" pass.
    "phone_number": re.compile(r"(?:\d[\s().-]?){3,}"),
    # The app shows verified lines itself; the model must not name or invent them.
    "helpline_name": re.compile(r"\blifeline\b|tele[\s-]?manas|crisis text line|samaritans|\baasra\b|\bicall\b"),
    "medication": re.compile(
        r"\b\d+\s?mg\b|\b(?:antidepressants?|ssris?|sertraline|zoloft|fluoxetine|prozac|escitalopram|lexapro"
        r"|citalopram|paroxetine|venlafaxine|bupropion|mirtazapine|alprazolam|xanax|clonazepam|lorazepam"
        r"|diazepam|valium|lithium|quetiapine|olanzapine|melatonin|sleeping pills?|medications?|meds)\b"
    ),
    "diagnosis": re.compile(
        r"\bdiagnos|\bdisorder\b|\bclinical(?:ly)? depress"
        r"|\byou (?:have|might have|may have|could have|seem to have|are suffering from|suffer from)"
        r" (?:clinical |major |severe )?(?:depression|anxiety|bipolar|ptsd|ocd|adhd|insomnia)\b"
        r"|\byou(?:'re| are) depressed\b"
    ),
}


def violations(text: str) -> list[str]:
    """Names of the checks the text fails, e.g. ["phone_number"]. Empty if it's clean."""
    normalised = text.lower().replace("’", "'")
    return [name for name, pattern in CHECKS.items() if pattern.search(normalised)]


class OutputGuard(HookProvider):
    """Replaces a reflection that fails any check with a standard message."""

    def __init__(self, replacement: str) -> None:
        self.replacement = replacement

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(AfterInvocationEvent, self.check)

    def check(self, event: AfterInvocationEvent) -> None:
        output = event.result.structured_output if event.result else None
        if not isinstance(output, AgentOutput):
            return  # the call failed; the service's fail-safe handles that
        found = violations(output.reflection)
        if found:
            # Log the categories only, never the text (journal content stays out of logs).
            log.warning("Output guard replaced the reflection (%s)", ", ".join(found))
            output.reflection = self.replacement
