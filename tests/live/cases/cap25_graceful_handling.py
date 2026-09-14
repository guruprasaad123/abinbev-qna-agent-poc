"""Capability 25: graceful handling of unsupported or unavailable requests."""
from tests.live.runner import Case, not_crashed_and_answered, intent_is, all_of

TITLE = "Graceful handling of unsupported or unavailable requests"
CAPABILITY_NUMBER = 25

CASES = [
    Case("01", "unsupported entity (real competitor) -> clear message, not a crash",
         ["What was Carlsberg's revenue last year?"], not_crashed_and_answered()),

    Case("02", "unsupported granularity (brand-level financials) -> clear message, not a fabricated number",
         ["What was Corona's exact global revenue figure in 2025?"], not_crashed_and_answered()),

    Case("03", "a nonsensical/garbled question -> handled gracefully, not a crash",
         ["asdkfj revenue zzz???"], not_crashed_and_answered()),

    Case("04", "an empty-ish/minimal question -> handled gracefully",
         ["?"], not_crashed_and_answered()),

    Case("05", "a request for a data granularity that flatly doesn't exist (channel-level)",
         ["What was North America's e-commerce channel revenue specifically?"],
         not_crashed_and_answered()),

    Case("06", "a request mixing a supported and unsupported entity in one turn",
         ["Compare AB InBev's North America revenue to Molson Coors'"], not_crashed_and_answered()),

    Case("07", "out-of-scope request handled gracefully rather than forced into a data answer",
         ["What's the capital of France?"], intent_is("out_of_scope")),

    Case("08", "a request for a period outside the known data range",
         ["What was North America's revenue in Q1 2030?"], not_crashed_and_answered()),
]
