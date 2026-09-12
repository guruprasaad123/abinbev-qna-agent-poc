"""
Main orchestrator agent: the single entry point a caller (CLI, notebook, API)
talks to. It owns conversation memory, understands the user's turn, routes to
the four sub-agents (structured / unstructured / web / coding), validates and
synthesizes their outputs into one answer, and applies every cross-cutting
behavior in the assignment's capability list that isn't specific to one
sub-agent (greeting, scope, clarification, formatting, temporal reasoning,
hierarchy fallback, metadata discovery, follow-up suggestions, transparency).

See docs/ARCHITECTURE.md for the request-flow diagram this function
implements, and docs/CAPABILITY_MAPPING.md for exactly which lines below
satisfy which required capability.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field

from src.llm_client import get_llm_client
from src.memory import ConversationMemory
from src.config import (
    ALL_ZONES, ALL_COUNTRIES, ALL_BRANDS, ALL_KPIS, KPI_CATALOG, ENTITY_ALIASES,
    DOMAIN_DESCRIPTION, COMPANY_NAME, ZONE_HIERARCHY, COUNTRY_TO_ZONE,
    DATA_START, DATA_END, KNOWN_COMPETITORS,
)
from src.agents import structured_agent, unstructured_agent, websearch_agent, coding_agent
from src.formatting import rows_to_markdown_table


@dataclass
class AgentResponse:
    answer: str
    intent: str = ""
    sub_agents_used: list[str] = field(default_factory=list)
    sql_used: str = ""
    citations: list[dict] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    follow_up_suggestions: list[str] = field(default_factory=list)
    retried: bool = False
    raw_nlu: dict = field(default_factory=dict)


NLU_SYSTEM_PROMPT = f"""You are the natural-language-understanding module for an enterprise
Q&A agent over {COMPANY_NAME}'s REAL, publicly disclosed business data. classify the user's
latest message.

Known zones (structured data grain): {', '.join(ALL_ZONES)}, or 'Global' for company-wide
Known countries (map to a zone; NO country-grain structured data exists): {', '.join(ALL_COUNTRIES)}
Known brands (NO structured data exists; qualitative/document mentions only): {', '.join(ALL_BRANDS)}
Known KPIs: {', '.join(ALL_KPIS)}
In-scope domain: {DOMAIN_DESCRIPTION}

The user may write in any language, mix languages, use abbreviations (e.g. "US" for
United States, "EMEA" for Europe/Middle East/Africa), or make typos -- resolve these to the
canonical names above wherever confident.

Respond with ONLY a JSON object (no markdown fences) with this exact shape:
{{
  "language": "<ISO 639-1 code of the user's message language>",
  "intent": one of ["greeting","capability_intro","out_of_scope","metadata_discovery","data_query","comparison","clarification_needed"],
  "needs_clarification": true|false,
  "clarification_question": "<question to ask the user, or null>",
  "entities": {{
     "zones": [canonical zone names mentioned or implied],
     "countries": [canonical country names mentioned or implied],
     "brands": [canonical brand names mentioned or implied],
     "kpis": [canonical KPI keys mentioned or implied],
     "period": "<e.g. '2025', 'Q3 2025', 'last 12 months', or null>",
     "comparison_period": "<a second period being compared against, or null>"
  }},
  "unsupported_entities": [<any brand/country/competitor named by the user that is NOT in the known lists above>],
  "needed_subagents": [subset of "structured","unstructured","web","coding" needed to answer -- use "structured" for
     numeric zone/company KPI questions, "unstructured" for brand-specific, country-specific-color, news/context/why/
     press-release/strategy questions (since brand and country detail is only real in the documents, not in SQL),
     "web" ONLY for things clearly outside {COMPANY_NAME}'s own data (e.g. a named competitor's official financials,
     general industry facts), "coding" for custom derived calculations like CAGR/projections]
}}

Guidelines:
- "hi", "hello", "hey" alone -> intent "greeting".
- "what can you do / help me with" -> intent "capability_intro".
- Anything clearly unrelated to {COMPANY_NAME}'s business (weather, sports scores, general
  trivia, coding help unrelated to this data) -> intent "out_of_scope".
- A question naming NO zone/country/brand/KPI/period at all when one is clearly required, or
  that is ambiguous between two reasonable readings -> needs_clarification true with a specific
  clarification_question. Do not ask for clarification if reasonable defaults exist or if
  conversation context (given to you separately) already supplies the missing piece.
- "which KPIs / metrics / zones / countries / periods do you have" -> intent "metadata_discovery".
- A question about ONLY a brand (no zone/country) should still route to "unstructured" -- there
  is no structured brand data, so don't route it to "structured" alone.
"""

SYNTHESIS_SYSTEM_PROMPT = f"""You are the answer-synthesis module for an enterprise Q&A agent over
{COMPANY_NAME}'s REAL business data. You are given retrieved evidence from up to four sources
(structured KPI data, internal documents with citations, web search, code execution) and
must write ONE final answer for the user.

Rules:
- Respond in the SAME language the user wrote in.
- Use ONLY the numbers/facts given to you in the evidence below -- never invent a figure.
- If a markdown table is provided, you may reference it but do not fabricate a different one.
- Cite unstructured documents inline like [DOC-014] using the doc_id given.
- If evidence is partial, missing, or an entity was unsupported, say so plainly rather than
  glossing over it (transparency > false confidence).
- Keep the answer focused and well-formatted; use markdown only where it aids readability.
- End with 1-2 short, genuinely relevant follow-up suggestions IF there's a natural next
  question (e.g. a related KPI, an adjacent period, an adjacent brand/market) -- omit this if
  none is natural.
"""


class Orchestrator:
    def __init__(self, llm_classify=None, llm_generate=None, llm_synthesize=None):
        # Three-tier model routing (see docs/COST_LATENCY_TRADEOFFS.md §2):
        # classify  -- cheap tier, NLU/intent only (high call volume, narrow task)
        # generate  -- cheap tier, narrow sub-agent generation (NL->SQL, code, memory summary)
        # synthesize -- workhorse tier, final answer composition + validation-retry
        self.llm_classify = llm_classify or get_llm_client("classify")
        self.llm_generate = llm_generate or get_llm_client("generate")
        self.llm_synthesize = llm_synthesize or get_llm_client("synthesize")
        self.memory = ConversationMemory()

    # ------------------------------------------------------------------ NLU
    def _run_nlu(self, user_message: str) -> dict:
        context = self.memory.context_block()
        prompt = (f"{context}\n\nLatest user message: {user_message}" if context else
                  f"Latest user message: {user_message}")
        raw = self.llm_classify.generate(system=NLU_SYSTEM_PROMPT, user=prompt, json_mode=True,
                                          max_tokens=600, caller="orchestrator_nlu")
        try:
            parsed = json.loads(_strip_fences(raw))
            # Some models occasionally wrap the object in a single-element array
            # even when asked for a bare object -- unwrap it rather than treating
            # it as a parse failure.
            if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
                parsed = parsed[0]
            if not isinstance(parsed, dict):
                raise ValueError("NLU response was not a JSON object")
            data = parsed
        except (json.JSONDecodeError, ValueError):
            # Graceful degradation: fall back to a permissive default rather than crashing.
            data = {"language": "en", "intent": "data_query", "needs_clarification": False,
                     "clarification_question": None, "entities": {}, "unsupported_entities": [],
                     "needed_subagents": ["structured"]}
        data.setdefault("entities", {})
        data.setdefault("unsupported_entities", [])
        data.setdefault("needed_subagents", ["structured"])
        return data

    # ------------------------------------------------------- hierarchy fallback
    def _hierarchy_fallback_notes(self, nlu: dict) -> list[str]:
        """Resolve a country to its zone (roll-up -- AB InBev doesn't disclose
        country-grain structured data, only zone-grain) or flag a genuinely
        unsupported entity (e.g. a named competitor) with a plain-language
        note, rather than silently returning nothing or an error."""
        notes = []
        resolved_zones = []
        for country in nlu.get("entities", {}).get("countries", []):
            zone = COUNTRY_TO_ZONE.get(country)
            if zone:
                resolved_zones.append(zone)
                notes.append(f"AB InBev doesn't publicly disclose structured financials by country; "
                              f"showing the **{zone}** zone (which includes {country}) instead, plus any "
                              f"{country}-specific commentary found in the documents.")
        for unsupported in nlu.get("unsupported_entities", []):
            key = unsupported.strip()
            notes.append(f"'{key}' isn't part of {COMPANY_NAME}'s tracked entities (brand/zone/country), "
                          f"or is a different company entirely (e.g. a competitor), so no internal "
                          f"structured data exists for it. Any answer about it, if given, is "
                          f"qualitative/public information only, not internal reporting.")
        if resolved_zones:
            nlu["entities"].setdefault("zones", [])
            nlu["entities"]["zones"] = list(set(nlu["entities"]["zones"] + resolved_zones))
        return notes

    # ------------------------------------------------------------- routing
    def _context_block_for_subagents(self) -> str:
        return self.memory.context_block()

    def _call_structured(self, user_message: str, entities: dict) -> tuple[str, list[str]]:
        filt_desc = _entities_to_context_line(entities)
        ctx = (self._context_block_for_subagents() + "\n" + filt_desc).strip()
        result = structured_agent.answer(self.llm_generate, user_message, context_block=ctx)
        evidence = []
        assumptions = list(result.notes)
        if result.ok:
            table = rows_to_markdown_table(result.columns, result.rows)
            evidence.append(f"STRUCTURED DATA (SQL: {result.sql_used}):\n{table}")
        else:
            assumptions.append(f"Structured data lookup failed: {result.error}")
            evidence.append("STRUCTURED DATA: unavailable for this request.")
        return "\n".join(evidence), assumptions

    def _call_unstructured(self, user_message: str) -> tuple[str, list[dict]]:
        ctx = self._context_block_for_subagents()
        result = unstructured_agent.answer(self.llm_generate, user_message, context_block=ctx)
        citations = []
        if result.ok and result.documents:
            lines = ["RETRIEVED DOCUMENTS:"]
            for d in result.documents:
                lines.append(f"[{d.doc_id}] {d.title} ({d.date}, {d.source_type}): {d.excerpt}")
                citations.append({"doc_id": d.doc_id, "title": d.title, "date": d.date, "source_type": d.source_type})
            return "\n".join(lines), citations
        return "RETRIEVED DOCUMENTS: none relevant found.", citations

    def _call_web(self, user_message: str) -> tuple[str, list[str]]:
        result = websearch_agent.answer(user_message)
        if result.ok:
            lines = ["WEB SEARCH RESULTS:"]
            for r in result.results:
                lines.append(f"- {r['title']} ({r['url']}): {r['snippet']}")
            return "\n".join(lines), []
        return "WEB SEARCH: unavailable.", [f"Web search was unavailable ({result.unavailable_reason})."]

    def _call_coding(self, user_message: str, prior_evidence: str) -> tuple[str, list[str]]:
        result = coding_agent.answer(self.llm_generate, user_message, supporting_data=prior_evidence)
        if result.ok:
            return f"CODE EXECUTION RESULT: {result.result} (code: {result.code_used})", []
        return "CODE EXECUTION: failed.", [f"Custom calculation failed: {result.error}"]

    # -------------------------------------------------------- validation
    def _needs_retry(self, answer_text: str, evidence_numbers: set[str]) -> bool:
        """Cheap, deterministic hallucination check: pull every standalone
        number out of the drafted answer and confirm at least a reasonable
        fraction of them appear in the evidence we actually retrieved. This
        catches the common failure mode (model invents a plausible-looking
        figure) without a second full LLM call unless something looks off."""
        answer_numbers = set(re.findall(r"\d[\d,]*\.?\d*", answer_text))
        answer_numbers = {n for n in answer_numbers if len(n.replace(",", "").replace(".", "")) >= 3}
        if not answer_numbers:
            return False
        overlap = answer_numbers & evidence_numbers
        return len(overlap) < 0.5 * len(answer_numbers)

    # ------------------------------------------------------------- main
    def handle_turn(self, user_message: str, on_step=None) -> AgentResponse:
        """`on_step`, if given, is called as `on_step(phase: str, detail: dict)` at each
        major milestone (nlu, routing, subagent, synthesis) -- purely observational,
        never affects behavior. Built for a UI (see ui/app.py) to show a live trace of
        the orchestrator/sub-agent workflow; every other caller (CLI, notebook, tests)
        omits it and behaves exactly as before."""
        emit = on_step or (lambda phase, detail: None)
        self.memory.add_turn("user", user_message)
        nlu = self._run_nlu(user_message)
        intent = nlu.get("intent", "data_query")
        emit("nlu", {
            "intent": intent, "language": nlu.get("language", "en"),
            "entities": nlu.get("entities", {}),
            "needs_clarification": bool(nlu.get("needs_clarification")),
            "corrections": _detect_corrections(user_message, nlu.get("entities", {})),
        })

        if intent == "greeting":
            text = (f"Hello! I'm the {COMPANY_NAME} Q&A assistant. {DOMAIN_DESCRIPTION} "
                     f"Ask me about revenue, volume, EBITDA, margin, organic growth or net profit "
                     f"by zone/period, or about brand and country context from our documents. "
                     f"What would you like to know?")
            return self._finish(text, intent, nlu)

        if intent == "capability_intro":
            text = self._capability_intro_text()
            return self._finish(text, intent, nlu)

        if intent == "out_of_scope":
            text = (f"That's outside what I can help with -- I'm scoped to {COMPANY_NAME}'s business "
                     f"data and related market/company context. {DOMAIN_DESCRIPTION}")
            return self._finish(text, intent, nlu)

        if intent == "metadata_discovery":
            text = self._metadata_discovery_text()
            self.memory.update_filters(_flatten_entities(nlu.get("entities", {})))
            return self._finish(text, intent, nlu)

        if nlu.get("needs_clarification") and intent == "clarification_needed":
            question = nlu.get("clarification_question") or "Could you clarify which brand, market, or period you mean?"
            return self._finish(question, intent, nlu)

        # --- data_query / comparison: route to sub-agents ---
        if intent == "comparison":
            # A comparison follow-up ("how does that compare to X?") reliably
            # names the NEW entity but the model doesn't always re-state the
            # one already in focus -- inject it explicitly from the prior
            # active filter rather than trusting the model to resolve "that"
            # correctly from prose context alone (this was observed to fail:
            # the comparison silently dropped the entity under discussion).
            entities = nlu.setdefault("entities", {})
            for dim, key in (("zone", "zones"), ("country", "countries"), ("brand", "brands")):
                prior_val = self.memory.active_filters.get(dim, "")
                for v in prior_val.split(", "):
                    if v and entities.get(key) and v not in entities[key]:
                        entities[key].append(v)
        self.memory.update_filters(_flatten_entities(nlu.get("entities", {})))
        assumptions = self._hierarchy_fallback_notes(nlu)

        needed = nlu.get("needed_subagents") or ["structured"]
        evidence_blocks = []
        citations = []
        used = []
        emit("routing", {"needed_subagents": needed})

        if "structured" in needed:
            block, notes = self._call_structured(user_message, nlu.get("entities", {}))
            evidence_blocks.append(block)
            assumptions.extend(notes)
            used.append("structured")
            emit("subagent", {"name": "structured", "evidence": block, "notes": notes})
        if "unstructured" in needed:
            block, cites = self._call_unstructured(user_message)
            evidence_blocks.append(block)
            citations.extend(cites)
            used.append("unstructured")
            emit("subagent", {"name": "unstructured", "evidence": block, "citations": cites})
        if "web" in needed:
            block, notes = self._call_web(user_message)
            evidence_blocks.append(block)
            assumptions.extend(notes)
            used.append("web")
            emit("subagent", {"name": "web", "evidence": block, "notes": notes})
        if "coding" in needed:
            block, notes = self._call_coding(user_message, "\n".join(evidence_blocks))
            evidence_blocks.append(block)
            assumptions.extend(notes)
            used.append("coding")
            emit("subagent", {"name": "coding", "evidence": block, "notes": notes})

        evidence_text = "\n\n".join(evidence_blocks) if evidence_blocks else "No evidence retrieved."
        evidence_numbers = set(re.findall(r"\d[\d,]*\.?\d*", evidence_text))

        synth_prompt = (f"{self.memory.context_block()}\n\nUser question: {user_message}\n\n"
                         f"Evidence:\n{evidence_text}\n\n"
                         + (f"Known data limitations to mention: {'; '.join(assumptions)}\n" if assumptions else ""))
        emit("synthesis", {"status": "start"})
        # max_tokens is generous (not just the length of the expected prose answer)
        # because some models spend a chunk of the budget on internal reasoning
        # before writing the final answer -- too tight a cap risks the response
        # getting cut off mid-reasoning, before the actual answer is ever written.
        answer_text = self.llm_synthesize.generate(system=SYNTHESIS_SYSTEM_PROMPT, user=synth_prompt,
                                                    max_tokens=1600, caller="orchestrator_synthesis")

        retried = False
        if self._needs_retry(answer_text, evidence_numbers):
            retried = True
            emit("synthesis", {"status": "retry", "reason": "drafted answer used numbers not found in evidence"})
            correction_prompt = (synth_prompt + "\n\nYour previous draft:\n" + answer_text +
                                  "\n\nThat draft used figures not found in the evidence above. "
                                  "Rewrite the answer using ONLY numbers present in the evidence.")
            answer_text = self.llm_synthesize.generate(system=SYNTHESIS_SYSTEM_PROMPT, user=correction_prompt,
                                                        max_tokens=1600, caller="orchestrator_synthesis_retry")
        emit("synthesis", {"status": "done", "retried": retried})

        follow_ups = self._follow_up_suggestions(nlu)
        resp = self._finish(answer_text, intent, nlu, sub_agents_used=used, citations=citations,
                             assumptions=assumptions, follow_up_suggestions=follow_ups, retried=retried)
        return resp

    # -------------------------------------------------------- helpers
    def _finish(self, text, intent, nlu, sub_agents_used=None, citations=None, assumptions=None,
                follow_up_suggestions=None, retried=False) -> AgentResponse:
        self.memory.add_turn("assistant", text)
        self.memory.summarize_overflow(lambda s, u: self.llm_generate.generate(system=s, user=u, max_tokens=300, caller="memory_summarizer"))
        return AgentResponse(
            answer=text, intent=intent, sub_agents_used=sub_agents_used or [],
            citations=citations or [], assumptions=assumptions or [],
            follow_up_suggestions=follow_up_suggestions or [], retried=retried, raw_nlu=nlu,
        )

    def _capability_intro_text(self) -> str:
        kpi_list = ", ".join(v["label"] for v in KPI_CATALOG.values())
        return (f"I'm the {COMPANY_NAME} Q&A assistant, built over AB InBev's real, publicly "
                f"disclosed results. I can:\n"
                f"- Answer questions about {kpi_list}, by reporting zone and quarter/year\n"
                f"- Compare KPIs across zones or time periods (QoQ, YoY)\n"
                f"- Roll a country up to its zone automatically when structured data doesn't go that granular\n"
                f"- Retrieve real press releases, filing excerpts and brand/country commentary with citations\n"
                f"- Pull in public/web context for named competitors or anything outside our own data\n"
                f"- Do custom calculations (growth rates, projections) on the numbers\n\n"
                f"Known zones: {', '.join(ALL_ZONES)}\nKnown countries: {', '.join(ALL_COUNTRIES)}\n"
                f"Known brands (document-level only): {', '.join(ALL_BRANDS)}\n"
                f"Structured data covers Q1 2024-Q4 2025 (quarterly, by zone) and "
                f"FY{DATA_START.year}-FY{DATA_END.year} (annual, company-wide).")

    def _metadata_discovery_text(self) -> str:
        lines = [f"**Available data**:", ""]
        lines.append("KPIs: " + ", ".join(f"{v['label']} ({v['unit']})" for v in KPI_CATALOG.values()))
        lines.append("")
        lines.append("Structured (SQL) grain: zone x quarter, Q1 2024-Q4 2025; zone x year and "
                      f"company-wide (Global) x year, FY{DATA_START.year}-FY{DATA_END.year}. "
                      "No brand-level or country-level structured rows -- AB InBev doesn't disclose "
                      "that granularity publicly.")
        lines.append("")
        lines.append("Zones: " + ", ".join(ALL_ZONES))
        lines.append("Countries (roll up to their zone): " + ", ".join(f"{c} ({z})" for z, cs in ZONE_HIERARCHY.items() for c in cs))
        lines.append("Brands (document/qualitative mentions only, not structured rows): " + ", ".join(ALL_BRANDS))
        lines.append("")
        lines.append("Document types: real press releases and filing excerpts, summarized with citations "
                      "to the original AB InBev source and URL.")
        return "\n".join(lines)

    def _follow_up_suggestions(self, nlu: dict) -> list[str]:
        entities = nlu.get("entities", {})
        suggestions = []
        if entities.get("kpis") and len(entities["kpis"]) == 1:
            other = [k for k in ALL_KPIS if k not in entities["kpis"]][:1]
            if other:
                suggestions.append(f"Compare against {KPI_CATALOG[other[0]]['label']}?")
        if entities.get("period") and not entities.get("comparison_period"):
            suggestions.append("Compare this to the same period last year?")
        if entities.get("zones") and len(entities["zones"]) == 1:
            suggestions.append("Compare this across all zones?")
        return suggestions[:2]


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _detect_corrections(user_message: str, entities: dict) -> list[dict]:
    """Best-effort, purely observational check for the UI's dev-mode trace: a
    canonical entity the NLU extracted that doesn't appear verbatim (case-
    insensitively) in the raw user message was likely resolved from an
    abbreviation, alias, or typo (e.g. "NA" / "Norht America" -> "North
    America"). We don't know the exact raw token that was corrected -- only
    that *something* in the message was normalized to this canonical value --
    so this is reported as "normalized", not a precise before/after diff."""
    corrections = []
    msg_lower = user_message.lower()
    for dim, key in (("zone", "zones"), ("country", "countries"), ("brand", "brands")):
        for canonical in entities.get(key) or []:
            if canonical and canonical.lower() not in msg_lower:
                corrections.append({"dimension": dim, "resolved_to": canonical})
    for kpi_key in entities.get("kpis") or []:
        label = KPI_CATALOG.get(kpi_key, {}).get("label", kpi_key)
        if label.lower() not in msg_lower and kpi_key.lower() not in msg_lower:
            corrections.append({"dimension": "kpi", "resolved_to": label})
    return corrections


def _flatten_entities(entities: dict) -> dict:
    flat = {}
    if entities.get("zones"):
        flat["zone"] = entities["zones"][0] if len(entities["zones"]) == 1 else ", ".join(entities["zones"])
    if entities.get("countries"):
        flat["country"] = entities["countries"][0] if len(entities["countries"]) == 1 else ", ".join(entities["countries"])
    if entities.get("brands"):
        flat["brand"] = entities["brands"][0] if len(entities["brands"]) == 1 else ", ".join(entities["brands"])
    if entities.get("kpis"):
        flat["kpi"] = ", ".join(entities["kpis"])
    if entities.get("period"):
        flat["period"] = entities["period"]
    return flat


def _entities_to_context_line(entities: dict) -> str:
    parts = []
    for key in ("zones", "countries", "brands", "kpis"):
        if entities.get(key):
            parts.append(f"{key}: {', '.join(entities[key])}")
    if entities.get("period"):
        parts.append(f"period: {entities['period']}")
    if entities.get("comparison_period"):
        parts.append(f"comparison_period: {entities['comparison_period']}")
    return ("Extracted entities for this question -- " + "; ".join(parts)) if parts else ""
