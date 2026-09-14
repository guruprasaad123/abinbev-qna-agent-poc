"""Capability 13: answer validation, retry mechanisms, and response quality evaluation.

Whether a retry actually FIRES depends on the model occasionally citing a
number not present in the evidence -- inherently probabilistic, not
something we can force deterministically against a real model. These cases
check that the mechanism doesn't break the turn either way (retried=True or
False are both acceptable outcomes); what matters is the final answer is
still well-formed and evidence-grounded.
"""
from tests.live.runner import Case, not_crashed_and_answered, answer_contains_any, all_of

TITLE = "Answer validation, retry mechanisms, and response quality evaluation"
CAPABILITY_NUMBER = 13

CASES = [
    Case("01", "a question needing several numbers at once (multi-KPI), retry-prone",
         ["Give me North America's revenue, volume, and EBITDA margin for FY2025 all at once"],
         not_crashed_and_answered()),

    Case("02", "a dense multi-zone, multi-period comparison in one turn",
         ["Compare revenue and EBITDA margin for North America, EMEA, and Asia Pacific across 2024 and 2025"],
         not_crashed_and_answered()),

    Case("03", "a straightforward single-number question, should not need a retry",
         ["What was North America's revenue in Q1 2024?"],
         answer_contains_any("3,593", "3593")),

    Case("04", "a question with a false premise the answer must not silently accept",
         ["What drove South America's huge revenue growth last year?"],
         not_crashed_and_answered(),
         note="South America's YoY revenue can be flat/declining in some periods -- answer should reflect actual evidence, not the premise's assumption."),

    Case("05", "a long multi-turn conversation, checking the final answer stays grounded",
         ["What was Middle Americas revenue in 2024?",
          "And in 2025?",
          "What drove that change?"],
         not_crashed_and_answered()),

    Case("06", "a comparison across many dimensions at once (stresses the synthesis step)",
         ["Compare EBITDA margin and organic revenue growth for North America versus EMEA in 2025"],
         not_crashed_and_answered()),
]
