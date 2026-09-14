"""Capability 2: greeting, capability introduction, and out-of-scope handling."""
from tests.live.runner import Case, intent_is, no_subagent_used, answer_contains_any, all_of

TITLE = "Greeting, capability introduction, and out-of-scope request handling"
CAPABILITY_NUMBER = 2

CASES = [
    Case("01", "plain greeting", ["hi"], all_of(intent_is("greeting"), no_subagent_used())),
    Case("02", "greeting with punctuation", ["Hello!"], intent_is("greeting")),
    Case("03", "casual greeting", ["hey there"], intent_is("greeting")),
    Case("04", "capability introduction, direct phrasing",
         ["What can you help me with?"], intent_is("capability_intro")),
    Case("05", "capability introduction, alternate phrasing",
         ["What kind of questions can I ask you?"], intent_is("capability_intro")),
    Case("06", "out-of-scope: weather", ["What's the weather like today?"],
         all_of(intent_is("out_of_scope"), no_subagent_used())),
    Case("07", "out-of-scope: general trivia", ["Tell me a joke"], intent_is("out_of_scope")),
    Case("08", "out-of-scope: unrelated stock", ["What's the stock price of Apple?"],
         intent_is("out_of_scope")),
    Case("09", "out-of-scope: general coding help unrelated to this data",
         ["Can you help me write a sorting algorithm in Rust?"], intent_is("out_of_scope")),
    Case("10", "borderline: a real business question should NOT be out-of-scope",
         ["What was AB InBev's revenue in North America last year?"],
         answer_contains_any("revenue", "million")),
]
