"""SOC Investigation Copilot tests. Run:  python -m pytest tests/ -v

Fast tests use only stdlib + PyYAML (+ numpy if present) with hand-built
evidence and stub vectors. Only the last test needs the real
sentence-transformers model and is skipped when it is unavailable.
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

import okf
from okf import (
    build_plan,
    chunk_concept,
    cosine_top_k,
    evaluate_trust,
    extract_alert_facts,
    has_useful_evidence,
    insufficient_message,
    load_bundle,
    normalize_verified,
    parse_concept_file,
    resolve_link,
    traverse_links,
)

ROOT = Path(__file__).parent.parent
BUNDLE = ROOT / "knowledge"


@pytest.fixture(scope="module")
def bundle():
    concepts, chunks = load_bundle(BUNDLE)
    return concepts, chunks


def test_bundle_loads_all_soc_concepts(bundle):
    concepts, chunks = bundle
    for cid in ["soc/suspicious-login-detection", "soc/auth-log-sources",
                "soc/endpoint-alert-evidence",
                "soc/account-compromise-investigation",
                "soc/credential-exposure", "soc/incident-escalation"]:
        assert cid in concepts, f"missing concept {cid}"
    assert len(chunks) > 20
    # Reserved files are not concepts.
    assert not any(c.endswith("index") or c.endswith("log") for c in concepts)


def test_multi_document_investigation(bundle):
    """A suspicious-login plan must cite at least two distinct concepts."""
    concepts, chunks = bundle
    by_concept = {}
    for c in chunks:
        by_concept.setdefault(c["concept_id"], []).append(c)
    evidence = [
        (by_concept["soc/suspicious-login-detection"][0], 0.72, "semantic match"),
        (by_concept["soc/auth-log-sources"][0], 0.65, "semantic match"),
        (by_concept["soc/account-compromise-investigation"][0], 0.60, "semantic match"),
    ]
    related = traverse_links(
        ["soc/suspicious-login-detection", "soc/auth-log-sources"], concepts)
    plan = build_plan("impossible travel login", evidence, related, concepts)
    cited = {s["concept_id"] for s in plan["steps"]}
    assert len(cited) >= 2, f"plan cites only {cited}"
    assert plan["steps"], "plan has no steps"


def test_alert_profiles_preserve_facts_and_differ(bundle):
    concepts, chunks = bundle

    def evidence_for(ids):
        return [
            (next(c for c in chunks if c["concept_id"] == cid), 0.8, "semantic match")
            for cid in ids
        ]

    login = build_plan(
        "12 failed logins from 203.0.113.8 at 10:15 UTC",
        evidence_for(["soc/suspicious-login-detection", "soc/auth-log-sources"]),
        [], concepts)
    token = build_plan(
        "Exposed API token in repository history for 47 minutes",
        evidence_for(["soc/credential-exposure", "cybersecurity/secret-detection"]),
        [], concepts)
    chained = build_plan(
        "Suspicious login at 10:15 UTC followed by PowerShell alert on host ENG-42",
        evidence_for(["soc/suspicious-login-detection",
                      "soc/auth-log-sources", "soc/endpoint-alert-evidence"]),
        [], concepts)

    login_titles = {step["title"] for step in login["steps"]}
    token_titles = {step["title"] for step in token["steps"]}
    chained_titles = {step["title"] for step in chained["steps"]}
    assert "Identify token scope and owner" in token_titles
    assert "Correlate authentication and endpoint timelines" in chained_titles
    assert login_titles != token_titles
    assert token_titles != chained_titles
    assert "47 minutes" in token["summary"]
    assert "10:15 UTC" in chained["summary"]
    assert "ENG-42" in chained["summary"]


def test_unsupported_alert_is_explicit(bundle):
    concepts, chunks = bundle
    evidence = [(chunks[0], 0.8, "semantic match")]
    plan = build_plan("What is the weather tomorrow?", evidence, [], concepts)
    assert plan["alert"]["type"] == "unsupported"
    assert any("not recognized" in item for item in plan["limitations"])


def test_invalid_ollama_citation_is_rejected():
    import app as app_module
    evidence = [({
        "source": "knowledge/soc/auth-log-sources.md",
        "section": "Authentication Log Sources",
        "text": "Event evidence.",
        "meta": {},
    }, 0.8, "semantic match")]
    assert not app_module._valid_citations(
        "Assessment\nCitation: knowledge/soc/not-retrieved.md#Unknown", evidence)


def test_linked_concepts_discovered(bundle):
    """Traversal from suspicious-login-detection must find auth-log-sources."""
    concepts, _ = bundle
    related = traverse_links(["soc/suspicious-login-detection"], concepts,
                             max_hops=1, max_results=6)
    found = {cid for cid, _ in related}
    assert "soc/auth-log-sources" in found, f"link walk found {found}"
    assert len(related) <= 6, "traversal exceeded bound"


def test_draft_guidance_never_authoritative(bundle):
    concepts, _ = bundle
    trust = evaluate_trust(concepts["soc/proposed-edr-query"].meta)
    assert trust["status"] == "draft"
    assert trust["tier"] == "unverified"
    assert trust["authoritative"] is False
    assert any("draft" in w.lower() for w in trust["warnings"])


def test_deprecated_stale_knowledge_flagged(bundle):
    concepts, _ = bundle
    trust = evaluate_trust(concepts["soc/legacy-password-rotation"].meta)
    assert trust["status"] == "deprecated"
    assert trust["stale"] is True
    assert trust["authoritative"] is False
    text = " ".join(trust["warnings"]).lower()
    assert "deprecated" in text and "stale_after" in text or "outdated" in text


def test_no_supporting_evidence():
    assert has_useful_evidence([]) is False
    assert has_useful_evidence([({"concept_id": "x"}, 0.10)]) is False
    plan = build_plan("spectroscope calibration", [], [], {})
    assert plan["steps"] == []
    assert "Insufficient evidence" in insufficient_message()


def test_conflicting_guidance_prefers_authoritative(bundle):
    """30-day rotation question: current guide is authoritative, legacy is not."""
    concepts, chunks = bundle
    cur = next(c for c in chunks if c["concept_id"] == "soc/credential-exposure")
    leg = next(c for c in chunks if c["concept_id"] == "soc/legacy-password-rotation")
    evidence = [(leg, 0.80, "semantic match"), (cur, 0.75, "semantic match")]
    plan = build_plan("force password rotation every 30 days?", evidence, [], concepts)
    by_cid = {s["concept_id"]: s for s in plan["steps"]}
    assert by_cid["soc/credential-exposure"]["authoritative"] is True
    assert by_cid["soc/legacy-password-rotation"]["authoritative"] is False
    assert by_cid["soc/legacy-password-rotation"]["warnings"], \
        "deprecated step must carry warnings"


def test_source_attribution_correct(bundle):
    """Every plan step citation resolves to a real concept; score != trust."""
    concepts, chunks = bundle
    by_concept = {}
    for c in chunks:
        by_concept.setdefault(c["concept_id"], []).append(c)
    evidence = [(by_concept["soc/incident-escalation"][0], 0.70, "semantic match"),
                (by_concept["soc/endpoint-alert-evidence"][0], 0.66, "semantic match")]
    plan = build_plan("escalate host alert", evidence, [], concepts)
    for step in plan["steps"]:
        assert step["concept_id"] in concepts, f"dangling citation {step['citation']}"
        assert "score" in step and "tier" in step, "score and trust must be separate fields"
        assert isinstance(step["score"], float)


def test_okf_tolerance_unknown_fields_and_types(tmp_path):
    """Unknown types/keys preserved; bare verified mapping; defaults; broken links."""
    p = tmp_path / "weird.md"
    p.write_text("---\ntype: Custom Thing\ncustom_key: 42\n"
                 "verified: { by: human:reviewer, at: 2026-01-01T00:00:00Z }\n"
                 "---\n\nSee [ghost](./ghost.md).\n", encoding="utf-8")
    concept = parse_concept_file(p, tmp_path)
    assert concept.meta["type"] == "Custom Thing"  # tolerated, not rejected
    assert concept.meta["custom_key"] == 42  # preserved
    norm = normalize_verified(concept.meta)
    assert len(norm) == 1 and norm[0]["by"] == "human:reviewer"  # bare map -> list
    trust = evaluate_trust(concept.meta)
    assert trust["status"] == "stable"  # absent status defaults to stable
    assert trust["tier"] == "human-reviewed"
    assert resolve_link("./ghost.md", concept, {}) is None  # broken link tolerated


def test_index_and_log_present():
    index = (BUNDLE / "index.md").read_text(encoding="utf-8")
    assert "soc/suspicious-login-detection.md" in index
    log = (BUNDLE / "log.md").read_text(encoding="utf-8")
    dates = re.findall(r"^## (\d{4}-\d{2}-\d{2})", log, re.MULTILINE)
    assert dates and dates == sorted(dates, reverse=True), "log must be newest-first"


def test_cosine_top_k_math():
    vecs = [[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]]
    top = cosine_top_k([1.0, 0.0], vecs, k=2)
    assert top[0][0] == 0 and abs(top[0][1] - 1.0) < 1e-6
    assert top[1][0] == 2


def test_investigate_pipeline_wiring(bundle, monkeypatch):
    """End-to-end wiring with a stub embedder (threshold relaxed for stub)."""
    import app as app_module
    concepts, chunks = bundle

    class FakeModel:
        def encode(self, texts, normalize_embeddings=True):
            import math
            out = []
            for t in texts:
                v = [float("login" in t.lower()),
                     float("password" in t.lower()), 1.0]
                n = math.sqrt(sum(x * x for x in v))
                out.append([x / n for x in v])
            return out

    monkeypatch.setattr(app_module, "SIMILARITY_THRESHOLD", 0.0)
    import numpy as np
    fake = FakeModel()
    embeddings = np.asarray(fake.encode([c["text"] for c in chunks]),
                           dtype=np.float32)
    out = app_module.investigate("strange login activity", concepts, chunks,
                                 embeddings, fake)
    assert out["evidence"], "pipeline produced no evidence"
    assert out["plan"]["steps"], "pipeline produced no plan steps"


def test_ollama_generation_uses_local_api(monkeypatch):
    import app as app_module

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self.payload

    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        if request.full_url.endswith("/api/tags"):
            return FakeResponse(b'{"models": [{"name": "test-model"}]}')
        source = "knowledge/soc/test.md#Evidence"
        return FakeResponse(json.dumps({
            "response": f"Executive summary\nCitation: {source}"
        }).encode())

    import json
    monkeypatch.setattr(app_module, "OLLAMA_MODEL", "test-model")
    monkeypatch.setattr(app_module.urllib.request, "urlopen", fake_urlopen)
    evidence = [({
        "source": "knowledge/soc/test.md",
        "section": "Evidence",
        "text": "A test fact.",
        "meta": {},
    }, 0.8, "semantic match")]

    answer, status = app_module.call_ollama("test alert", evidence)
    assert answer and "Executive summary" in answer
    assert "Local Ollama mode" in status
    assert calls[1][0].full_url.endswith("/api/generate")
    assert json.loads(calls[1][0].data)["model"] == "test-model"


def test_llm_request_uses_configured_api_key(monkeypatch):
    """The optional provider request must authenticate with the configured key."""
    import app as app_module

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"choices": [{"message": {"content": "grounded summary"}}]}'

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(app_module.urllib.request, "urlopen", fake_urlopen)

    assert app_module.call_llm("test alert", []) == "grounded summary"
    assert captured["request"].headers["Authorization"] == "Bearer test-key"


def test_local_env_selects_configured_qwen_model(monkeypatch, tmp_path):
    import app as app_module

    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("OLLAMA_MODEL=qwen3:4b-q4_K_M\n", encoding="utf-8")

    app_module.load_local_env(env_file)

    assert os.environ["OLLAMA_MODEL"] == "qwen3:4b-q4_K_M"


def test_missing_ollama_model_uses_honest_fallback(monkeypatch):
    import app as app_module

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"models": [{"name": "other-model"}]}'

    monkeypatch.setattr(app_module, "OLLAMA_MODEL", "qwen3:4b-q4_K_M")
    monkeypatch.setattr(
        app_module.urllib.request, "urlopen", lambda request, timeout: FakeResponse())

    answer, status = app_module.call_ollama("test alert", [])

    assert answer is None
    assert "qwen3:4b-q4_K_M" in status
    assert "deterministic" in status.lower()


def test_ollama_generation_error_uses_safe_fallback(monkeypatch):
    import urllib.error
    import app as app_module

    def failing_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            class TagsResponse:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return b'{"models": [{"name": "qwen3:4b-q4_K_M"}]}'

            return TagsResponse()
        raise urllib.error.URLError("generation unavailable")

    monkeypatch.setattr(app_module, "OLLAMA_MODEL", "qwen3:4b-q4_K_M")
    monkeypatch.setattr(app_module.urllib.request, "urlopen", failing_urlopen)

    answer, status = app_module.call_ollama("test alert", [])

    assert answer is None
    assert "generation failed" in status.lower()
    assert "deterministic" in status.lower()


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("sentence_transformers") is None,
    reason="sentence-transformers not installed")
def test_real_model_suspicious_login(bundle):
    """Integration: real semantic retrieval grounds a login investigation."""
    from sentence_transformers import SentenceTransformer
    import numpy as np
    import app as app_module
    concepts, chunks = bundle
    model = SentenceTransformer(app_module.MODEL_NAME)
    embeddings = np.asarray(
        model.encode([c["text"] for c in chunks], normalize_embeddings=True),
        dtype=np.float32)
    out = app_module.investigate(
        "Impossible travel login: jdoe authenticated from two countries within 20 minutes",
        concepts, chunks, embeddings, model)
    assert out["evidence"], "no evidence retrieved for login alert"
    top_ids = {c["concept_id"] for c, s, _ in out["evidence"] if s > 0} | \
        {c["concept_id"] for c, _, _ in out["evidence"]}
    assert top_ids & {"soc/suspicious-login-detection",
                      "soc/account-compromise-investigation",
                      "soc/auth-log-sources"}, f"unexpected sources {top_ids}"
    # Relevance is not correctness: authoritative steps must come from trusted notes.
    for step in out["plan"]["steps"]:
        if step["authoritative"]:
            assert evaluate_trust(
                concepts[step["concept_id"]].meta)["authoritative"] is True
