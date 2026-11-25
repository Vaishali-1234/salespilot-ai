"""Page 4: Knowledge Base & RAG Inspector."""

import streamlit as st

from frontend.api_client import api_client
from frontend.styles import render_hero


def render_knowledge_base_page() -> None:
    render_hero(
        "Knowledge Base & RAG Pipeline",
        "Inspect indexed TechNova Solutions documents, test FAISS semantic retrieval, and ingest new documents.",
    )

    kb = api_client.list_knowledge()
    docs = kb.get("documents", [])
    st.info(
        f"**Documents Indexed:** {len(docs)} &nbsp;|&nbsp; **Total FAISS Chunks:** {kb.get('total_chunks', 0)} "
        f"&nbsp;|&nbsp; **Embedding Engine:** `{kb.get('embedding_mode', 'unknown')}`"
    )

    col_test, col_add = st.columns([1.2, 1.0], gap="large")
    with col_test:
        st.markdown("### Test Semantic RAG Retrieval")
        query = st.text_input("Ask a question to inspect top matching chunks", "What pricing plans does TechNova offer?")
        top_k = st.slider("Top-K Chunks", min_value=1, max_value=6, value=3)
        if st.button("Run FAISS Similarity Search", type="primary"):
            res = api_client.query_knowledge(query, top_k=top_k)
            if not res.get("found"):
                st.warning("No matching chunks exceeded the similarity threshold (anti-hallucination guard triggered).")
            else:
                for item in res["results"]:
                    with st.expander(f"{item['source']} (Score: {item['score']}) — {item['chunk_id']}", expanded=True):
                        st.markdown(item["content"])

    with col_add:
        st.markdown("### Add Knowledge Document & Rebuild Index")
        with st.form("add_kb_doc"):
            fname = st.text_input("Filename (e.g., case_studies.txt)", "")
            content = st.text_area("Document Content", height=160, placeholder="# Case Study\n...")
            if st.form_submit_button("Save & Rebuild FAISS Index"):
                if not fname.strip() or len(content.strip()) < 10:
                    st.error("Please enter a valid filename and at least 10 characters of content.")
                else:
                    res = api_client.add_knowledge(fname.strip(), content.strip())
                    st.success(f"Saved `{res['filename']}` and rebuilt FAISS ({res['rebuild']['chunks']} chunks).")
                    st.rerun()

    st.markdown("### Indexed Company Documents")
    for doc in docs:
        with st.expander(f"{doc['source']} — {doc['title']} ({doc['characters']} chars)"):
            st.text(doc["content"])
