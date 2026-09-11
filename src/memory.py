"""
Conversation memory: multi-turn history + extracted "active filters" (the
entities/dimensions/period currently in focus) + rolling summarization.

Design rationale (docs/DESIGN_DECISIONS.md has the full writeup):
  - Two complementary representations are kept, not one:
      1. `active_filters` -- a small structured dict (brand, country, channel,
         kpi, period, ...) updated after every turn. This is what actually
         answers "Support contextual follow-up questions" and "Support
         conversation context preservation" cheaply and reliably: a
         follow-up like "what about last year?" is resolved by reusing
         active_filters rather than re-parsing the whole transcript.
      2. `raw_turns` -- the literal recent exchange, kept verbatim for a
         bounded window (RECENT_TURNS_KEPT) so the model sees exact wording.
  - "Support conversation memory optimization for long-running sessions" is
    implemented as rolling summarization: once history exceeds a threshold,
    older turns are compressed into `rolling_summary` (one LLM call) and
    dropped from raw_turns. This bounds prompt-token growth (and therefore
    cost/latency) in long sessions instead of re-sending the entire
    transcript every turn -- a concrete, measurable trade-off discussed in
    docs/COST_LATENCY_TRADEOFFS.md.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

RECENT_TURNS_KEPT = 6          # raw (verbatim) turns always kept
SUMMARIZE_TRIGGER_TURNS = 14   # once total turns exceed this, summarize the overflow


@dataclass
class ConversationMemory:
    raw_turns: list[dict] = field(default_factory=list)   # [{role, content}]
    rolling_summary: str = ""
    active_filters: dict = field(default_factory=dict)     # e.g. {"brand": "Glacier Peak", "country": "United States", "kpi": "net_revenue_usd", "period": "2025"}
    turn_count: int = 0

    def add_turn(self, role: str, content: str):
        self.raw_turns.append({"role": role, "content": content})
        self.turn_count += 1

    def update_filters(self, extracted: dict):
        """Merge newly-extracted entities into active filters. Only non-empty
        values overwrite -- an omitted dimension in a follow-up question means
        'keep using what we already had', which is the whole point of this
        mechanism (e.g. user asks brand+country, then just 'and last year?')."""
        for k, v in (extracted or {}).items():
            if v:
                self.active_filters[k] = v

    def clear_filters(self):
        self.active_filters = {}

    def needs_summarization(self) -> bool:
        return len(self.raw_turns) > SUMMARIZE_TRIGGER_TURNS

    def summarize_overflow(self, llm_generate_fn):
        """Compress everything except the most recent RECENT_TURNS_KEPT turns
        into rolling_summary via one LLM call, then drop them from raw_turns.
        `llm_generate_fn(system, user) -> str` is injected so this module has
        no direct dependency on the LLM client (keeps it unit-testable)."""
        if not self.needs_summarization():
            return
        overflow = self.raw_turns[:-RECENT_TURNS_KEPT]
        self.raw_turns = self.raw_turns[-RECENT_TURNS_KEPT:]
        transcript = "\n".join(f"{t['role']}: {t['content']}" for t in overflow)
        system = ("Summarize this conversation excerpt in 3-5 bullet points, preserving any "
                  "concrete entities, numbers, decisions, or open questions a later turn might "
                  "need. Be terse.")
        prior = f"Existing summary so far:\n{self.rolling_summary}\n\n" if self.rolling_summary else ""
        new_summary = llm_generate_fn(system, f"{prior}New excerpt to fold in:\n{transcript}")
        self.rolling_summary = new_summary.strip()

    def context_block(self) -> str:
        """Compact text block to prepend to the system/user prompt."""
        parts = []
        if self.rolling_summary:
            parts.append(f"Conversation summary so far:\n{self.rolling_summary}")
        if self.active_filters:
            filt = ", ".join(f"{k}={v}" for k, v in self.active_filters.items())
            parts.append(f"Active context (reuse these for follow-ups unless the user overrides them): {filt}")
        return "\n\n".join(parts)

    def recent_history_as_messages(self) -> list[dict]:
        return list(self.raw_turns)
