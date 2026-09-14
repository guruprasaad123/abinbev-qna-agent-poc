"""Capability 4: clarification for ambiguous or incomplete user requests."""
from tests.live.runner import Case, clarification_asked, intent_is, all_of, not_crashed_and_answered

TITLE = "Clarification for ambiguous or incomplete user requests"
CAPABILITY_NUMBER = 4

CASES = [
    Case("01", "no entity, no KPI, no period at all -- classic ambiguous case",
         ["Tell me about performance."], clarification_asked()),
    Case("02", "vague pronoun with nothing prior to resolve it against",
         ["How is it doing?"], clarification_asked()),
    Case("03", "asks for 'the numbers' without saying which",
         ["Can you give me the numbers?"], clarification_asked()),
    Case("04", "names a KPI but no zone/period at all",
         ["What's the margin?"], clarification_asked()),
    Case("05", "reasonable default exists (company-wide, latest period implied) -- should NOT force clarification",
         ["What was AB InBev's total revenue last year?"],
         not_crashed_and_answered()),
    Case("06", "a fully-specified question should NOT trigger clarification",
         ["What was North America's revenue in Q1 2024?"], intent_is("data_query")),
    Case("07", "clarification question itself should be specific, not generic filler",
         ["How's it going for us?"], clarification_asked()),
    Case("08", "multi-turn: clarification, then the user supplies the missing piece",
         ["Tell me about performance.", "North America revenue, Q1 2024"],
         not_crashed_and_answered()),
]
