"""Capability 3: intent validation before data retrieval.

The orchestrator always runs NLU (_run_nlu) FIRST, before any sub-agent is
touched -- greeting/out_of_scope/metadata/clarification paths never reach a
sub-agent at all. These cases confirm the routing decision matches intent,
i.e. sub-agents are gated on a validated intent, not fired unconditionally.
"""
from tests.live.runner import Case, intent_is, no_subagent_used, used_subagent, all_of

TITLE = "Intent validation before data retrieval"
CAPABILITY_NUMBER = 3

CASES = [
    Case("01", "greeting never reaches a sub-agent",
         ["hi"], all_of(intent_is("greeting"), no_subagent_used())),
    Case("02", "out-of-scope never reaches a sub-agent",
         ["What's the weather?"], all_of(intent_is("out_of_scope"), no_subagent_used())),
    Case("03", "metadata_discovery never reaches a sub-agent",
         ["What KPIs do you track?"], all_of(intent_is("metadata_discovery"), no_subagent_used())),
    Case("04", "a genuine data question DOES reach the structured sub-agent",
         ["What was North America's revenue in Q1 2024?"],
         all_of(intent_is("data_query"), used_subagent("structured"))),
    Case("05", "a comparison question is classified as comparison intent",
         ["Compare EMEA and North America revenue for 2025"], intent_is("comparison")),
    Case("06", "a brand-only question routes to unstructured, not structured",
         ["Tell me about Corona's positioning outside Mexico"],
         used_subagent("unstructured")),
    Case("07", "ambiguous request is flagged for clarification, not guessed at",
         ["Tell me about performance."], intent_is("clarification_needed")),
    Case("08", "capability-intro request classified correctly, not as data_query",
         ["What can you do?"], intent_is("capability_intro")),
]
