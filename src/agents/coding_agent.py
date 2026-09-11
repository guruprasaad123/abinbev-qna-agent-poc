"""
Coding Sub-Agent: NL -> Python snippet -> sandboxed execution -> numeric/derived result.

Used when the question needs a calculation beyond a single SQL aggregation
(CAGR, weighted averages across already-known figures, "if X grew by Y% for
Z years", etc.) -- the orchestrator routes here rather than to the
structured agent when the question is arithmetic/derivation-shaped rather
than a direct data lookup.
"""
from __future__ import annotations
from dataclasses import dataclass

from src.tools.code_tool import run_code

SYSTEM_PROMPT = """You write short Python snippets to answer a numeric/analytical question.
Rules:
- Use only: math, statistics, datetime (already available as names) and plain Python.
- No imports, no file/network access -- none are available and will error.
- Assign your final answer to a variable named `result`.
- If given supporting numbers in the prompt, use exactly those numbers.
- Output ONLY the Python code, no markdown fences, no commentary.
"""


@dataclass
class CodingResult:
    ok: bool
    code_used: str = ""
    result: object = None
    stdout: str = ""
    error: str = ""


def answer(llm_client, question: str, supporting_data: str = "") -> CodingResult:
    user_prompt = question if not supporting_data else f"Supporting data:\n{supporting_data}\n\nQuestion: {question}"
    code = llm_client.generate(system=SYSTEM_PROMPT, user=user_prompt, max_tokens=400, caller="coding_agent")
    code = code.strip().strip("`")
    if code.lower().startswith("python"):
        code = code[len("python"):].strip()

    exec_result = run_code(code)
    if exec_result.ok:
        return CodingResult(ok=True, code_used=code, result=exec_result.result, stdout=exec_result.stdout)
    return CodingResult(ok=False, code_used=code, error=exec_result.error)
