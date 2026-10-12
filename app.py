import pandas as pd
import streamlit as st

from text2sql import config
from text2sql.agent import TextToSQLAgent
from text2sql.llm import get_llm
from text2sql.schema import build_schema_text

st.set_page_config(page_title="Text-to-SQL Analyst", page_icon="🧮", layout="wide")
st.title("Text-to-SQL Analyst")
st.caption("Ask in plain English. Get an answer and the query behind it.")

EXAMPLES = [
    "Which country has the most customers?",
    "Top 5 artists by total revenue",
    "How many invoices were issued each year?",
    "Which genre generates the most revenue?",
]

with st.sidebar:
    st.header("Settings")
    provider = st.selectbox("LLM provider", ["gemini", "anthropic"])
    model = st.text_input("Model (blank = default from .env)", value="") or None
    use_retries = st.toggle("Self-correction retries (max 3)", value=True)
    use_desc = st.toggle("Column descriptions in prompt", value=True)
    use_examples = st.toggle("Few-shot examples in prompt", value=True)
    clarify = st.toggle("Ask clarifying question if ambiguous", value=False)
    show_schema = st.toggle("Show schema sent to the model", value=False)

if not config.DB_PATH.exists():
    st.error(f"Database not found at {config.DB_PATH}. Run `python download_db.py` first.")
    st.stop()

if show_schema:
    with st.expander("Schema", expanded=True):
        st.code(build_schema_text(config.DB_PATH, config.DESCRIPTIONS_PATH, use_descriptions=use_desc))

if "question" not in st.session_state:
    st.session_state.question = ""

cols = st.columns(len(EXAMPLES))
for col, ex in zip(cols, EXAMPLES):
    if col.button(ex, use_container_width=True):
        st.session_state.question = ex

question = st.text_input("Your question", key="question", placeholder="e.g. Which artist has the most albums?")

if st.button("Ask", type="primary") and question.strip():
    try:
        agent = TextToSQLAgent(
            get_llm(provider, model), use_retries=use_retries, use_descriptions=use_desc,
            use_examples=use_examples, allow_clarification=clarify,
        )
        with st.spinner("Thinking..."):
            result = agent.run(question.strip())
    except Exception as exc:
        st.error(f"Could not run the agent: {exc}")
        st.stop()

    if result.clarification:
        st.info(f"Quick question before I write the query: **{result.clarification}**")
        st.stop()

    if result.refusal:
        st.warning(f"I can't answer that from this database: {result.refusal}")
        st.stop()

    if result.success:
        st.subheader("Answer")
        st.write(result.answer)
    else:
        st.error(result.answer)
        if result.error:
            st.caption(f"Last error: {result.error}")

    if result.sql:
        st.subheader("SQL")
        st.code(result.sql, language="sql")

    if result.success:
        st.subheader("Result")
        st.dataframe(pd.DataFrame(result.rows, columns=result.columns), use_container_width=True)
        if result.truncated:
            st.caption(f"Showing the first {config.MAX_ROWS} rows only.")

    if len(result.attempts) > 1 or not result.success:
        with st.expander(f"Attempts ({len(result.attempts)})"):
            for i, a in enumerate(result.attempts, 1):
                st.markdown(f"**Attempt {i}** - {'ok' if a.error is None else 'failed'}")
                st.code(a.sql, language="sql")
                if a.error:
                    st.caption(a.error)
