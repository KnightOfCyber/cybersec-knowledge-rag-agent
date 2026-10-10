"""End-to-end SOC copilot evaluation with the real semantic model.

Run:  python eval.py
Covers: multi-document login investigation, linked concepts, draft,
deprecated/stale, no-evidence, conflicting guidance, source attribution.
Exits non-zero on failure. Needs sentence-transformers + torch installed.
"""

import numpy as np

import app as app_module
from okf import evaluate_trust, load_bundle

CASES = [
    {"name": "multi-document login investigation",
     "query": "Impossible travel login: jdoe authenticated from two countries within 20 minutes",
     "expect_concepts": {"soc/suspicious-login-detection",
                         "soc/account-compromise-investigation",
                         "soc/auth-log-sources"},
     "min_steps": 2},
    {"name": "linked concepts",
     "query": "Which Windows event IDs show failed logons?",
     "expect_concepts": {"soc/auth-log-sources"},
     "min_steps": 1},
    {"name": "conflicting guidance (30-day rotation)",
     "query": "Should we force password rotation every 30 days?",
     "expect_concepts": {"soc/credential-exposure", "soc/legacy-password-rotation"},
     "min_steps": 1},
    {"name": "draft EDR query",
     "query": "Give me an EDR query that correlates logons to devices",
     "expect_concepts": set(),  # informational: report rank, trust asserted separately
     "min_steps": 0},
    {"name": "no supporting evidence",
     "query": "How do I calibrate a laboratory spectroscope?",
     "expect_concepts": set(),
     "min_steps": 0},
]


def main() -> int:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("SKIP: sentence-transformers not installed; run pytest for model-free tests.")
        return 2
    concepts, chunks = load_bundle()
    print(f"Loaded {len(concepts)} concepts, {len(chunks)} sections.")
    model = SentenceTransformer(app_module.MODEL_NAME)
    embeddings = np.asarray(
        model.encode([c["text"] for c in chunks], normalize_embeddings=True),
        dtype=np.float32)

    passed, total = 0, 0
    for case in CASES:
        total += 1
        out = app_module.investigate(case["query"], concepts, chunks, embeddings, model)
        got = {c["concept_id"] for c, _, _ in out["evidence"]}
        steps = out["plan"]["steps"]
        if case["name"] == "no supporting evidence":
            ok = not out["evidence"] and steps == []
            detail = "no evidence (correct)" if ok else f"unexpected evidence {got}"
        elif case["name"] == "draft EDR query":
            trust = evaluate_trust(concepts["soc/proposed-edr-query"].meta)
            rank = next((i for i, (c, _, _) in enumerate(out["evidence"], 1)
                         if c["concept_id"] == "soc/proposed-edr-query"), None)
            ok = trust["authoritative"] is False and trust["status"] == "draft"
            detail = f"draft authoritative={trust['authoritative']} (correct); retrieval rank={rank}"
        else:
            hit = got & case["expect_concepts"]
            ok = bool(hit) and len(steps) >= case["min_steps"]
            detail = f"concepts={sorted(got)} steps={len(steps)}"
        # Attribution: every step citation must resolve to a real concept.
        attrib_ok = all(s["concept_id"] in concepts for s in steps)
        ok = ok and attrib_ok
        print(f"[{'PASS' if ok else 'FAIL'}] {case['name']}\n       -> {detail}")
        passed += ok

    # Deterministic trust assertions (no model involved).
    total += 1
    legacy = evaluate_trust(concepts["soc/legacy-password-rotation"].meta)
    draft = evaluate_trust(concepts["soc/proposed-edr-query"].meta)
    trust_ok = (not legacy["authoritative"] and legacy["stale"]
                and not draft["authoritative"])
    print(f"[{'PASS' if trust_ok else 'FAIL'}] trust rules "
          f"(deprecated+stale and draft both non-authoritative)")
    passed += trust_ok

    print(f"\nResult: {passed}/{total} passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
