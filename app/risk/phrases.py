"""Curated risk phrases (English).

Patterns run against normalised text: lowercase, punctuation removed,
apostrophes dropped ("don't" -> "dont"), whitespace collapsed.
Each entry is (reason shown to the user, regex). Bias toward recall:
a false positive shows a hotline card; a false negative can cost a life.
"""

from app.models import RiskLevel

PHRASES: dict[RiskLevel, list[tuple[str, str]]] = {
    RiskLevel.IMMINENT: [
        ("Mentioned wanting to kill themselves", r"kill(ing)? my ?self"),
        ("Mentioned suicide", r"suicid(e|al)"),
        ("Mentioned ending their life", r"end(ing)? (my|it all|my own) li(fe|ves)|end it all|take my (own )?life"),
        ("Mentioned a plan to die", r"(plan|planning|going) to (die|end it)"),
        ("Mentioned wanting to die", r"(want|wanna|wish|ready) to die|want to be dead"),
    ],
    RiskLevel.HIGH: [
        ("Mentioned hurting themselves", r"(hurt(ing)?|harm(ing)?|cut(ting)?) my ?self|self ?harm"),
        ("Said others would be better off without them", r"better off without me"),
        ("Mentioned not wanting to wake up", r"(not|never|dont) (want to )?wake up"),
        ("Said there is no reason to live", r"no (reason|point) (to|in) (live|living|going on)"),
        ("Said they cannot go on", r"(cant|cannot|can not) go on|(cant|cannot) do this anymore"),
        ("Said they want to disappear", r"want to disappear|wish i (was|were) (gone|dead|never born)"),
    ],
    RiskLevel.ELEVATED: [
        ("Expressed hopelessness", r"hopeless|no hope|nothing (will|ever) (change|get better)"),
        ("Said they feel worthless", r"worthless|(im|i am) a burden|(im|i am) useless"),
        ("Said they feel completely alone", r"(completely|totally|so) alone|no one cares|nobody cares"),
        ("Said they feel trapped", r"trapped|no way out"),
    ],
}
