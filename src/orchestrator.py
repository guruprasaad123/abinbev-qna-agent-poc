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
    ALL_BRANDS, ALL_COUNTRIES, ALL_CHANNELS, ALL_KPIS, KPI_CATALOG, ENTITY_ALIASES,
    DOMAIN_DESCRIPTION, COMPANY_NAME, GEO_HIERARCHY, CITY_TO_COUNTRY, COUNTRY_TO_REGION,
    DATA_START, DATA_END, CATEGORY_HIERARCHY, BRANDS, KNOWN_COMPETITORS,
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
Q&A agent over {COMPANY_NAME}'s FMCG business data. classify the user's latest message.

Known brands: {', '.join(ALL_BRANDS)}
Known countries: {', '.join(ALL_COUNTRIES)}
Known channels: {', '.join(ALL_CHANNELS)}
Known KPIs: {', '.join(ALL_KPIS)}
In-scope domain: {DOMAIN_DESCRIPTION}

The user may write in any language, mix languages, use abbreviations (e.g. "GP" for
Northstar Lager, "US" for United States), or make typos -- resolve these to the canonical
names above wherever confident.

Respond with ONLY a JSON object (no markdown fences) with this exact shape:
{{
  "language": "<ISO 639-1 code of the user's message language>",
  "intent": one of ["greeting","capability_intro","out_of_scope","metadata_discovery","data_query","comparison","clarification_needed"],
  "needs_clarification": true|false,
  "clarification_question": "<question to ask the user, or null>",
  "entities": {{
     "brands": [canonical brand names mentioned or implied],
     "countries": [canonical country names mentioned or implied],
     "channels": [canonical channel names mentioned or implied],
     "kpis": [canonical KPI keys mentioned or implied],
     "period": "<e.g. '2025', 'Q3 2025', 'last 12 months', or null>",
     "comparison_period": "<a second period being compared against, or null>"
  }},
  "unsupported_entities": [<any brand/country/city/competitor named by the user that is NOT in the known lists above>],
  "needed_subagents": [subset of "structured","unstructured","web","coding" needed to answer -- use "structured" for
     numeric KPI questions, "unstructured" for news/context/why/press-release/strategy questions, "web" ONLY for
     things clearly outside {COMPANY_NAME}'s own data (e.g. a public competitor's official financials, general
     industry facts), "coding" for custom derived calculations like CAGR/projections]
}}

Guidelines:
- "hi", "hello", "hey" alone -> intent "greeting".
- "what can you do / help me with" -> intent "capability_intro".
- Anything clearly unrelated to {COMPANY_NAME}'s business (weather, sports scores, general
  trivia, coding help unrelated to this data) -> intent "out_of_scope".
- A question naming NO brand/country/KPI/period at all when one is clearly required, or that
  is ambiguous between two reasonable readings -> needs_clarification true with a specific
  clarification_question. Do not ask for clarification if reasonable defaults exist or if
  conversation context (given to you separately) already supplies the missing piece.
- "which KPIs / metrics / brands / countries / periods do you have" -> intent "metadata_discovery".
"""

SYNTHESIS_SYSTEM_PROMPT = f"""You are the answer-synthesis module for an enterprise Q&A agent over
{COMPANY_NAME}'s FMCG data. You are given retrieved evidence from up to four sources
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
    def __init__(self, llm_router=None, llm_worker=None):
        self.llm_router = llm_router or get_llm_client("router")
        self.llm_worker = llm_worker or get_llm_client("worker")
        self.memory = ConversationMemory()

    def _resolve_entity_aliases(self, text: str) -> dict[str, list[str]]:
        """
        Deterministic first-pass scan for entity aliases, abbreviations, and typos
        defined in ENTITY_ALIASES (e.g. 'coron' -> Corona, 'mexco' -> Mexico, 'revenu' -> net_revenue_usd).
        """
        cleaned = re.sub(r"[^\w\s\.-]", " ", f" {text.lower()} ")
        brands, countries, channels, kpis, unsupported = [], [], [], [], []

        for alias, canonical in sorted(ENTITY_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
            pattern = r"(?:\b|_)" + re.escape(alias) + r"(?:\b|_)"
            if re.search(pattern, cleaned):
                if canonical in ALL_BRANDS and canonical not in brands:
                    brands.append(canonical)
                elif canonical in ALL_COUNTRIES and canonical not in countries:
                    countries.append(canonical)
                elif canonical in ALL_CHANNELS and canonical not in channels:
                    channels.append(canonical)
                elif canonical in ALL_KPIS and canonical not in kpis:
                    kpis.append(canonical)
                elif canonical in CITY_TO_COUNTRY and canonical not in unsupported:
                    unsupported.append(canonical)
                elif canonical in KNOWN_COMPETITORS and canonical not in unsupported:
                    unsupported.append(canonical)

        return {
            "brands": brands,
            "countries": countries,
            "channels": channels,
            "kpis": kpis,
            "unsupported_entities": unsupported,
        }

    # ------------------------------------------------------------------ NLU
    def _run_nlu(self, user_message: str) -> dict:
        context = self.memory.context_block()
        prompt = (f"{context}\n\nLatest user message: {user_message}" if context else
                  f"Latest user message: {user_message}")
        raw = self.llm_router.generate(system=NLU_SYSTEM_PROMPT, user=prompt, json_mode=True,
                                        max_tokens=600, caller="orchestrator_nlu")
        try:
            data = json.loads(_strip_fences(raw))
        except json.JSONDecodeError:
            # Graceful degradation: fall back to a permissive default rather than crashing.
            data = {"language": "en", "intent": "data_query", "needs_clarification": False,
                     "clarification_question": None, "entities": {}, "unsupported_entities": [],
                     "needed_subagents": ["structured"]}
        data.setdefault("entities", {})
        data.setdefault("unsupported_entities", [])
        data.setdefault("needed_subagents", ["structured"])

        # Augment/correct entities using deterministic entity alias resolution
        norm = self._resolve_entity_aliases(user_message)
        for cat in ("brands", "countries", "channels", "kpis"):
            target = data["entities"].setdefault(cat, [])
            for item in norm.get(cat, []):
                if item not in target:
                    target.append(item)
        for item in norm.get("unsupported_entities", []):
            if item not in data["unsupported_entities"]:
                data["unsupported_entities"].append(item)

        return data

    # ------------------------------------------------------- hierarchy fallback
    def _hierarchy_fallback_notes(self, nlu: dict) -> list[str]:
        """Resolve a city to its country (roll-up) or flag a genuinely
        unsupported entity (e.g. a competitor) with a plain-language note,
        rather than silently returning nothing or an error."""
        notes = []
        resolved_countries = []
        for unsupported in nlu.get("unsupported_entities", []):
            key = unsupported.strip()
            if key in CITY_TO_COUNTRY:
                country = CITY_TO_COUNTRY[key]
                resolved_countries.append(country)
                notes.append(f"Structured data isn't broken out by city; showing **{country}** "
                              f"(the country containing {key}) instead.")
            else:
                notes.append(f"'{key}' isn't part of {COMPANY_NAME}'s tracked entities (brand/country/competitor), "
                              f"so no internal data exists for it. Any answer about it, if given, is "
                              f"qualitative/public information only, not internal reporting.")
        if resolved_countries:
            nlu["entities"].setdefault("countries", [])
            nlu["entities"]["countries"] = list(set(nlu["entities"]["countries"] + resolved_countries))
        return notes

    # ------------------------------------------------------------- routing
    def _context_block_for_subagents(self) -> str:
        return self.memory.context_block()

    def _call_structured(self, user_message: str, entities: dict) -> tuple[str, list[str]]:
        filt_desc = _entities_to_context_line(entities)
        ctx = (self._context_block_for_subagents() + "\n" + filt_desc).strip()
        result = structured_agent.answer(self.llm_worker, user_message, context_block=ctx)
        evidence = []
        assumptions = list(result.notes)
        if result.ok:
            # Volume is always reported in hL (hectoliters) -- see src/config.py.
            vol_units = ["hL"] * len(result.rows) if "volume" in result.columns else None
            table = rows_to_markdown_table(result.columns, result.rows, volume_unit_by_row=vol_units)
            evidence.append(f"STRUCTURED DATA (SQL: {result.sql_used}):\n{table}")
        else:
            assumptions.append(f"Structured data lookup failed: {result.error}")
            evidence.append("STRUCTURED DATA: unavailable for this request.")
        return "\n".join(evidence), assumptions

    def _call_unstructured(self, user_message: str) -> tuple[str, list[dict]]:
        ctx = self._context_block_for_subagents()
        result = unstructured_agent.answer(self.llm_worker, user_message, context_block=ctx)
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
        result = coding_agent.answer(self.llm_worker, user_message, supporting_data=prior_evidence)
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
    def handle_turn(self, user_message: str) -> AgentResponse:
        self.memory.add_turn("user", user_message)
        nlu = self._run_nlu(user_message)
        intent = nlu.get("intent", "data_query")

        if intent == "greeting":
            text = (f"Hello! I'm the {COMPANY_NAME} Q&A assistant. {DOMAIN_DESCRIPTION} "
                     f"Ask me about revenue, volume, share, pricing, distribution, marketing/promo "
                     f"spend or margin by brand/market/channel/period, or about related company news "
                     f"and market context. What would you like to know?")
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
        self.memory.update_filters(_flatten_entities(nlu.get("entities", {})))
        assumptions = self._hierarchy_fallback_notes(nlu)

        needed = nlu.get("needed_subagents") or ["structured"]
        evidence_blocks = []
        citations = []
        used = []

        if "structured" in needed:
            block, notes = self._call_structured(user_message, nlu.get("entities", {}))
            evidence_blocks.append(block)
            assumptions.extend(notes)
            used.append("structured")
        if "unstructured" in needed:
            block, cites = self._call_unstructured(user_message)
            evidence_blocks.append(block)
            citations.extend(cites)
            used.append("unstructured")
        if "web" in needed:
            block, notes = self._call_web(user_message)
            evidence_blocks.append(block)
            assumptions.extend(notes)
            used.append("web")
        if "coding" in needed:
            block, notes = self._call_coding(user_message, "\n".join(evidence_blocks))
            evidence_blocks.append(block)
            assumptions.extend(notes)
            used.append("coding")

        evidence_text = "\n\n".join(evidence_blocks) if evidence_blocks else "No evidence retrieved."
        evidence_numbers = set(re.findall(r"\d[\d,]*\.?\d*", evidence_text))

        synth_prompt = (f"{self.memory.context_block()}\n\nUser question: {user_message}\n\n"
                         f"Evidence:\n{evidence_text}\n\n"
                         + (f"Known data limitations to mention: {'; '.join(assumptions)}\n" if assumptions else ""))
        answer_text = self.llm_router.generate(system=SYNTHESIS_SYSTEM_PROMPT, user=synth_prompt,
                                                max_tokens=900, caller="orchestrator_synthesis")

        retried = False
        if self._needs_retry(answer_text, evidence_numbers):
            retried = True
            correction_prompt = (synth_prompt + "\n\nYour previous draft:\n" + answer_text +
                                  "\n\nThat draft used figures not found in the evidence above. "
                                  "Rewrite the answer using ONLY numbers present in the evidence.")
            answer_text = self.llm_router.generate(system=SYNTHESIS_SYSTEM_PROMPT, user=correction_prompt,
                                                    max_tokens=900, caller="orchestrator_synthesis_retry")

        follow_ups = self._follow_up_suggestions(nlu)
        resp = self._finish(answer_text, intent, nlu, sub_agents_used=used, citations=citations,
                             assumptions=assumptions, follow_up_suggestions=follow_ups, retried=retried)
        return resp

    # -------------------------------------------------------- helpers
    def _finish(self, text, intent, nlu, sub_agents_used=None, citations=None, assumptions=None,
                follow_up_suggestions=None, retried=False) -> AgentResponse:
        self.memory.add_turn("assistant", text)
        self.memory.summarize_overflow(lambda s, u: self.llm_worker.generate(system=s, user=u, max_tokens=300, caller="memory_summarizer"))
        return AgentResponse(
            answer=text, intent=intent, sub_agents_used=sub_agents_used or [],
            citations=citations or [], assumptions=assumptions or [],
            follow_up_suggestions=follow_up_suggestions or [], retried=retried, raw_nlu=nlu,
        )

    def _capability_intro_text(self) -> str:
        kpi_list = ", ".join(v["label"] for v in KPI_CATALOG.values())
        return (f"I'm the {COMPANY_NAME} Q&A assistant. I can:\n"
                f"- Answer questions about {kpi_list}, by brand, country, channel and month/quarter/year\n"
                f"- Compare KPIs across brands, markets, channels or time periods\n"
                f"- Retrieve company news, market research, sustainability and strategy documents with citations\n"
                f"- Pull in public/web context for things outside our internal data\n"
                f"- Do custom calculations (growth rates, projections) on the numbers\n\n"
                f"Known brands: {', '.join(ALL_BRANDS)}\nKnown markets: {', '.join(ALL_COUNTRIES)}\n"
                f"Data covers {DATA_START.strftime('%b %Y')} to {DATA_END.strftime('%b %Y')} (year-to-date).")

    def _metadata_discovery_text(self) -> str:
        lines = [f"**Available data** ({DATA_START.strftime('%b %Y')}–{DATA_END.strftime('%b %Y')}):", ""]
        lines.append("KPIs: " + ", ".join(f"{v['label']} ({v['unit']})" for v in KPI_CATALOG.values()))
        lines.append("")
        lines.append("Brands & categories:")
        for cat, subs in CATEGORY_HIERARCHY.items():
            brands_in_cat = [b for b, m in BRANDS.items() if m["category"] == cat]
            lines.append(f"- {cat} ({', '.join(subs)}): {', '.join(brands_in_cat)}")
        lines.append("")
        lines.append("Markets: " + ", ".join(f"{c} ({r})" for r, cs in GEO_HIERARCHY.items() for c in cs))
        lines.append("Channels: " + ", ".join(ALL_CHANNELS))
        lines.append("")
        lines.append("Document types: press releases, earnings commentary, market research notes, "
                      "sustainability updates, competitor intelligence, strategy memos.")
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
        if entities.get("brands") and not entities.get("channels"):
            suggestions.append("Break this down by channel?")
        return suggestions[:2]


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _flatten_entities(entities: dict) -> dict:
    flat = {}
    if entities.get("brands"):
        flat["brand"] = entities["brands"][0] if len(entities["brands"]) == 1 else ", ".join(entities["brands"])
    if entities.get("countries"):
        flat["country"] = entities["countries"][0] if len(entities["countries"]) == 1 else ", ".join(entities["countries"])
    if entities.get("channels"):
        flat["channel"] = ", ".join(entities["channels"])
    if entities.get("kpis"):
        flat["kpi"] = ", ".join(entities["kpis"])
    if entities.get("period"):
        flat["period"] = entities["period"]
    return flat


def _entities_to_context_line(entities: dict) -> str:
    parts = []
    for key in ("brands", "countries", "channels", "kpis"):
        if entities.get(key):
            parts.append(f"{key}: {', '.join(entities[key])}")
    if entities.get("period"):
        parts.append(f"period: {entities['period']}")
    if entities.get("comparison_period"):
        parts.append(f"comparison_period: {entities['comparison_period']}")
    return ("Extracted entities for this question -- " + "; ".join(parts)) if parts else ""
