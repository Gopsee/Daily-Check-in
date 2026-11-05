"""Orchestrates one check-in: save, rule-based risk, agent, merge, respond."""

import logging
from collections.abc import Callable

from app import config
from app.data import coping_by_id, coping_exercises, hotlines_for
from app.models import AgentOutput, Checkin, CheckinResult, RiskFinding, RiskLevel
from app.risk.engine import combine, evaluate
from app.store.base import Store

log = logging.getLogger(__name__)

AgentRunner = Callable[[Store, Checkin], AgentOutput]

FALLBACK_REFLECTIONS = {
    1: "Thanks for checking in on a really hard day. That takes effort, and you don't have to carry this alone.",
    2: "Thanks for checking in. It sounds like today has been heavy. Be gentle with yourself.",
    3: "Thanks for checking in. A middle-of-the-road day still counts. Noticing how you feel matters.",
    4: "Thanks for checking in. Glad today is going fairly well.",
    5: "Thanks for checking in. Great to hear today is a good one. Notice what helped.",
}


# Used when the agent picks no exercise, an unknown one, or can't be reached.
MOOD_COPING = {1: "one_small_step", 2: "one_small_step", 3: "gratitude_three", 4: "gratitude_three", 5: "gratitude_three"}


def fallback_coping(checkin: Checkin) -> dict:
    """One reviewed exercise picked in code: the best match for the person's tags, else one for their mood."""
    tags = {t.lower() for t in checkin.tags}
    best = max(coping_exercises(), key=lambda c: len(tags & set(c["good_for"])))
    return best if tags & set(best["good_for"]) else coping_by_id(MOOD_COPING[checkin.mood])


def submit_checkin(
    store: Store,
    checkin: Checkin,
    run_agent: AgentRunner | None = None,
    region: str = config.HOTLINE_REGION,
) -> CheckinResult:
    if run_agent is None:
        from app.agent.agent import run_checkin_agent

        run_agent = run_checkin_agent

    # Save first, so the check-in is kept even if the agent fails.
    checkin_id = store.save_checkin(checkin)
    checkin = checkin.model_copy(update={"id": checkin_id})

    history = [c for c in store.get_history(checkin.user_id, 7, checkin.day) if c.id != checkin_id]
    findings = evaluate(checkin, history)

    reflection, coping_id, ai_available = FALLBACK_REFLECTIONS[checkin.mood], None, True
    try:
        output = run_agent(store, checkin)
        findings.append(RiskFinding(source="llm", level=RiskLevel.parse(output.risk_level), reason=output.risk_reason))
        reflection, coping_id = output.reflection, output.coping_id
    except Exception as exc:
        log.warning("Check-in agent failed (%s); applying fail-safe", type(exc).__name__)
        ai_available = False
        # Rules already covered mood, scores, trend and explicit phrases. The only gap is
        # indirect wording in the note, so escalate proportionately and only when one exists.
        if checkin.note:
            findings.append(
                RiskFinding(
                    source="failsafe",
                    level=RiskLevel.ELEVATED,
                    reason="Our AI couldn't read your note today, so support lines are shown just in case",
                )
            )

    store.save_risk_findings(checkin_id, findings)
    return CheckinResult(
        checkin_id=checkin_id,
        final_risk=combine(findings),
        findings=findings,
        reflection=reflection,
        coping=coping_by_id(coping_id) or fallback_coping(checkin),
        hotlines=hotlines_for(region),
        ai_available=ai_available,
    )
