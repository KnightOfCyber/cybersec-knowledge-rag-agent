"""SOC Investigation Copilot (OKF v0.2 + semantic retrieval).

Given an alert or analyst question: retrieve relevant OKF concepts with
semantic search, traverse a bounded number of markdown links, evaluate
trust deterministically in okf.py, and draft an evidence-grounded plan.

Read-only: never blocks accounts or touches live systems.
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import streamlit as st
from sentence_transformers import SentenceTransformer

import okf
from okf import (
    BUNDLE_ROOT,
    SIMILARITY_THRESHOLD,
    TOP_K,
    build_plan,
    cosine_top_k,
    evaluate_trust,
    has_useful_evidence,
    insufficient_message,
    load_bundle,
    extract_alert_facts,
    resolve_link,
    traverse_links,
    trust_warnings,
)

st.set_page_config(page_title="SOC Investigation Copilot", page_icon="🛡️")

MODEL_NAME = "all-MiniLM-L6-v2"
BASE_DIR = Path(__file__).parent


def load_local_env(path: Path = BASE_DIR / ".env") -> None:
    """Load simple KEY=VALUE entries without overriding the process environment."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b-q4_K_M").strip()

__all__ = ["MODEL_NAME", "TOP_K", "SIMILARITY_THRESHOLD", "load_chunks",
           "retrieve", "has_useful_evidence", "trust_warnings",
           "investigate", "main"]


# ---------- Compatibility shims (chunk-level API used by eval) ----------

def load_chunks(knowledge_dir: Path = BUNDLE_ROOT) -> list[dict]:
    _, chunks = load_bundle(knowledge_dir)
    return chunks


@st.cache_resource
def get_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


@st.cache_resource
def get_index():
    """Load concepts, chunks and embeddings once for the Streamlit app."""
    concepts, chunks = load_bundle()
    model = get_model()
    if not chunks:
        return concepts, chunks, np.zeros((0, 0), dtype=np.float32)
    embeddings = model.encode(
        [c["text"] for c in chunks], normalize_embeddings=True
    )
    return concepts, chunks, np.asarray(embeddings, dtype=np.float32)


def retrieve(query: str, chunks: list[dict], embeddings: np.ndarray,
             model, top_k: int = TOP_K) -> list[tuple[dict, float]]:
    """Top-k (chunk, relevance-score) pairs. Score is relevance ONLY, not trust."""
    if not chunks or embeddings.size == 0:
        return []
    q = np.asarray(
        model.encode([query], normalize_embeddings=True), dtype=np.float32)[0]
    return [(chunks[i], score) for i, score in cosine_top_k(q, embeddings, top_k)]


# ---------- Investigation pipeline ----------

def investigate(question: str, concepts: dict, chunks: list[dict],
                embeddings: np.ndarray, model,
                top_k: int = TOP_K, max_hops: int = 1) -> dict:
    """Run retrieve -> link-traverse -> trust-evaluate -> plan. Deterministic
    except for the embedding similarity scores. No LLM involved."""
    results = retrieve(question, chunks, embeddings, model, top_k=top_k)
    # Keep relevance score separate from trust status.
    evidence = [(c, s, f"semantic match (relevance {s:.2f})") for c, s in results
                if s >= SIMILARITY_THRESHOLD]
    start_ids = sorted({c["concept_id"] for c, _, _ in evidence})
    related = traverse_links(start_ids, concepts) if start_ids else []
    for cid, via in related:
        concept = concepts[cid]
        title = str(concept.meta.get("title", cid))
        first = (concept.body.split("\n")[0][:200] or title)
        evidence.append(({"concept_id": cid, "source": concept.rel,
                          "section": title, "text": first,
                          "meta": concept.meta},
                         0.0, f"linked from {via}"))
    plan = build_plan(question, evidence, related, concepts) if evidence \
        else {"summary": "", "steps": [], "related": [],
              "missing": [], "limitations": [],
              "alert": extract_alert_facts(question)}
    return {"results": results, "evidence": evidence, "related": related, "plan": plan}


def call_llm(question: str, evidence: list) -> str | None:
    """Optional evidence-only LLM summary. None when no key is configured."""
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        return None
    base = os.getenv("LLM_API_BASE", "https://api.openai.com/v1").strip().rstrip("/")
    model_name = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
    context = "\n\n".join(
        f"[Source: {c['source']} | Section: {c['section']}]\n{c['text'][:1200]}"
        for c, _, _ in evidence[:5]
    )
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system",
             "content": ("You summarize SOC evidence using ONLY the provided "
                         "sections. Cite source filenames. Never present "
                         "draft, deprecated, stale or unverified content as "
                         "authoritative. If evidence is insufficient, say so.")},
            {"role": "user", "content": f"Evidence:\n{context}\n\nAlert: {question}"},
        ],
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"LLM request failed: {exc}"


# ---------- Local Ollama generation ----------

def check_ollama() -> tuple[bool, str]:
    """Check local Ollama and verify that the configured model is installed."""
    try:
        request = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(request, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        names = {
            str(item.get("name", ""))
            for item in data.get("models", [])
            if isinstance(item, dict)
        }
        if OLLAMA_MODEL not in names:
            return False, (
                f"Ollama is available, but `{OLLAMA_MODEL}` is not installed. "
                f"Run `ollama pull {OLLAMA_MODEL}`; using deterministic mode."
            )
        return True, f"Local Ollama mode (`{OLLAMA_MODEL}`)."
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return False, (
            f"Ollama is unavailable at `{OLLAMA_BASE_URL}` ({exc}); "
            f"install/start Ollama and pull `{OLLAMA_MODEL}`. "
            "Using deterministic mode."
        )


def _valid_citations(answer: str, evidence: list) -> bool:
    """Reject generated citations that are not present in retrieved evidence."""
    allowed = {f"{c['source']}#{c['section']}" for c, _, _ in evidence}
    cited = set()
    for line in answer.splitlines():
        if line.lower().startswith("citation:"):
            cited.update(part.strip("` .") for part in line.split(":", 1)[1].split(","))
    return not cited or cited.issubset(allowed)


def call_ollama(question: str, evidence: list) -> tuple[str | None, str]:
    """Generate an evidence-only answer with Ollama, or explain fallback."""
    available, status = check_ollama()
    if not available:
        return None, status
    facts = extract_alert_facts(question)
    context = "\n\n".join(
        f"[Source: {c['source']}#{c['section']} | Trust: "
        f"{evaluate_trust(c['meta'])['tier']}]\n{c['text'][:1200]}"
        for c, _, _ in evidence[:8]
    )
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "prompt": (
            "You are a read-only SOC investigation assistant. Use ONLY the "
            "evidence below. Do not invent events, indicators, citations, or "
            "actions. Do not treat unverified, draft, deprecated, or stale "
            "evidence as authoritative. Return sections Executive summary, "
            "Assessment and confidence, Evidence, Investigation steps, "
            "Missing evidence, Warnings, and Limitations. For factual claims "
            "and recommendations, add `Citation: ` followed by exact source "
            "IDs from the evidence. Separate observed facts, hypotheses, "
            "missing evidence, and recommended checks.\n\n"
            f"Alert type: {facts['type']}\n"
            f"Observed facts (do not alter): {facts['observed_facts']}\n"
            f"Alert: {question}\n\nEvidence:\n{context}"
        ),
    }
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        answer = str(data["response"]).strip()
        if not answer or not _valid_citations(answer, evidence):
            return None, "Ollama returned invalid citations; using deterministic mode."
        return answer, status
    except (OSError, urllib.error.URLError, KeyError, TypeError,
            json.JSONDecodeError) as exc:
        return None, f"Ollama generation failed ({exc}); using deterministic mode."


# ---------- Streamlit GUI ----------

def main():
    st.title("SOC Investigation Copilot")
    st.caption(
        "Drafts evidence-grounded investigation plans from the local OKF bundle. "
        "Read-only: it takes no live security actions."
    )

    concepts, chunks, embeddings = get_index()
    if not chunks:
        st.error("No knowledge concepts found in `knowledge/`.")
        return

    question = st.text_area(
        "Paste a SOC alert or analyst question:",
        placeholder="e.g. Impossible-travel login: user jdoe from two countries within 20 minutes",
        height=100)
    ask = st.button("Investigate")

    if not ask:
        return
    if not question.strip():
        st.warning("Please enter an alert or question first.")
        return

    with st.spinner("Retrieving evidence..."):
        model = get_model()
        out = investigate(question, concepts, chunks, embeddings, model)

    if not out["evidence"]:
        st.info(insufficient_message())
        if out["results"]:
            with st.expander("Why no evidence? (closest misses)"):
                for c, s in out["results"][:3]:
                    st.markdown(f"- `{c['source']}#{c['section']}` relevance `{s:.2f}` "
                                f"(below threshold `{SIMILARITY_THRESHOLD}`)")
        return

    plan = out["plan"]

    st.subheader("Evidence summary")
    st.markdown(plan["summary"])
    if plan.get("alert"):
        st.markdown("**Observed facts**")
        for fact in plan["alert"]["observed_facts"]:
            st.markdown(f"- {fact}")
        st.markdown("**Hypotheses requiring verification**")
        for hypothesis in plan.get("hypotheses", []):
            st.markdown(f"- {hypothesis}")
    for chunk, score, reason in out["evidence"]:
        if score <= 0:
            continue  # link-discovered items are listed under Related knowledge
        trust = evaluate_trust(chunk["meta"])
        badge = "authoritative" if trust["authoritative"] else trust["tier"]
        st.markdown(
            f"- **{chunk['source']}** — *{chunk['section']}* "
            f"(relevance `{score:.2f}`; trust `{badge}`) — *{reason}*")
        for w in trust["warnings"]:
            st.warning(f"{chunk['source']}: {w}")

    st.subheader("Investigation steps")
    for i, step in enumerate(plan["steps"], 1):
        label = "authoritative" if step["authoritative"] else f"tentative ({step['tier']})"
        st.markdown(f"**{i}. {step['title']}** [{label}]\n\n{step['action']}\n\n"
                    f"Citation: `{step['citation']}`")
        for w in step["warnings"]:
            st.warning(f"Step {i}: {w}")

    st.subheader("Related knowledge")
    if out["related"]:
        for cid, via in out["related"]:
            concept = concepts[cid]
            st.markdown(f"- **{concept.rel}** — *{concept.meta.get('title', cid)}* "
                        f"(linked from `{via}`)")
    else:
        st.markdown("No linked concepts discovered.")

    llm_answer, llm_status = call_ollama(question, out["evidence"])
    if llm_answer is not None:
        st.subheader("LLM summary (evidence-only, optional)")
        st.markdown(llm_answer)
        st.caption(llm_status)
    else:
        st.info(f"Deterministic extractive mode: {llm_status}")

    st.subheader("Trust and freshness")
    any_warn = False
    for chunk, score, reason in out["evidence"]:
        trust = evaluate_trust(chunk["meta"])
        if trust["warnings"] or trust["missing"]:
            any_warn = True
            st.markdown(f"- `{chunk['source']}`: tier `{trust['tier']}`, "
                        f"status `{trust['status']}`, stale `{trust['stale']}`" +
                        (f", missing `{', '.join(trust['missing'])}`" if trust["missing"] else ""))
    if not any_warn:
        st.markdown("All cited concepts are stable, verified, and fresh.")

    st.subheader("Missing evidence and limitations")
    if plan["missing"]:
        st.markdown("Plan areas with no supporting concept: "
                    + ", ".join(f"`{m}`" for m in plan["missing"]))
    for line in plan["limitations"]:
        st.markdown(f"- {line}")


if __name__ == "__main__":
    main()
