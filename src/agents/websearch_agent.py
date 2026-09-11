"""Web Search Sub-Agent: thin wrapper around tools/web_search_tool so the
orchestrator has a uniform `answer(...)` interface across all four sub-agents."""
from __future__ import annotations
from dataclasses import dataclass, field

from src.tools.web_search_tool import web_search


@dataclass
class WebAgentResult:
    ok: bool
    results: list[dict] = field(default_factory=list)
    unavailable_reason: str = ""


def answer(question: str, max_results: int = 5) -> WebAgentResult:
    result = web_search(question, max_results=max_results)
    if result.ok:
        return WebAgentResult(ok=True, results=result.results)
    return WebAgentResult(ok=False, unavailable_reason=result.unavailable_reason)
