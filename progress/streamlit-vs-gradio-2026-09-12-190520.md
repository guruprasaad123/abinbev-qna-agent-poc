# Streamlit vs Gradio — decision record

Decision needed for: a developer-mode UI that visualizes the orchestrator's workflow
(NLU/routing → sub-agents → tool usage → synthesis) alongside a normal chat interface.
Requested a quantitative basis rather than a purely qualitative call.

## Data pulled (live web search, 2026-09-12)

| Metric | Streamlit | Gradio | Notes |
|---|---|---|---|
| GitHub stars | ~44-45K | ~43-45K | Roughly tied |
| PyPI downloads/month | ~26.5-32M | ~14.7M | Streamlit ~2x Gradio |
| Native trace/step component | `st.status(type="step")` — general timeline widget (2026 addition) | `gr.Chatbot`'s per-message `metadata`/`title` field — collapsible accordion **purpose-built** for showing tool calls/reasoning next to a chat bubble | Gradio's is more purpose-fit for a pure tool-call log |
| Fit for our data shape | Better — `st.dataframe`/`st.json`/`st.code`/`st.metric` map cleanly onto our varied `AgentResponse` fields (SQL used, citations table, raw NLU JSON, retry flag, follow-ups) | Weaker for this — one accordion per message is more linear-log-shaped, harder to hold multiple distinct structured blocks | Deciding factor |
| General layout flexibility (sidebar toggle, columns, multi-page) | Stronger | Weaker (chat-demo-first design) | Matters for the dev-mode toggle + side panel |

## Correction to an earlier (less rigorous) take

An initial qualitative pass leaned Streamlit without fully crediting Gradio's `Chatbot`
metadata/title accordion, which is literally designed for "show the agent's tool calls and
reasoning next to its answer" — not a workaround, the intended use case. It would need less
custom code than Streamlit to get a basic trace-in-chat working. This was corrected once real
documentation was checked rather than relying on memory.

## Decision: Streamlit

Net of the data, Streamlit was chosen — not on popularity or trace-support-in-the-abstract
(where Gradio is genuinely competitive), but because `AgentResponse` is a rich structured
object (SQL used, a citations list, a markdown evidence table, a raw NLU JSON blob, a retry
flag, follow-up suggestions), not just a linear tool-call log. Streamlit's general-purpose
widgets and layout primitives (sidebar, columns, dataframe/json/code renderers) map onto that
variety more directly than squeezing it into one accordion per chat message.

## Sources

- [Streamlit vs Gradio: Data Apps or ML Demos? (2026)](https://www.modern-datatools.com/compare/streamlit-vs-gradio)
- [streamlit · 465.9M downloads on PyPI](https://pepy.tech/projects/streamlit)
- [PyPI Download Stats — gradio](https://pypistats.org/packages/gradio)
- [st.status - Streamlit Docs](https://docs.streamlit.io/develop/api-reference/status/st.status)
- [Agents And Tool Usage — Gradio Guides](https://gradio.app/guides/agents-and-tool-usage)
- [Gradio Chatbot Docs](https://gradio.app/docs/gradio/chatbot)
