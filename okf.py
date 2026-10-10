"""Deterministic OKF v0.2 core: parsing, trust, links, retrieval math, plans.

No LLM, no network, no Streamlit here. Trust rules are enforced by this
module in plain Python; retrieved content is treated as untrusted data
(it is only displayed, never executed).

Follows https://github.com/GoogleCloudPlatform/open-knowledge-format (v0.2):
only `type` is required; unknown types/keys, broken links and missing
optional fields must be tolerated, never rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

try:
    import numpy as np
except ImportError:  # cosine math falls back to pure python
    np = None

BASE_DIR = Path(__file__).parent
BUNDLE_ROOT = BASE_DIR / "knowledge"
RESERVED_NAMES = {"index.md", "log.md"}
VALID_STATUSES = {"draft", "stable", "deprecated"}

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
FOOTNOTE_RE = re.compile(r"\[\^([^\]]+)\]")

SIMILARITY_THRESHOLD = 0.30
TOP_K = 5


# ---------- Concepts ----------

@dataclass
class Concept:
    """One OKF concept. `meta` preserves ALL frontmatter keys, known or not."""
    id: str                      # bundle-relative path without .md, e.g. soc/auth-log-sources
    path: Path
    rel: str                     # path relative to repo root for display
    meta: dict = field(default_factory=dict)
    body: str = ""
    links: list = field(default_factory=list)   # [(text, target)]
    issues: list = field(default_factory=list)  # conformance notes, never fatal


def _split_frontmatter(text: str):
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[1], parts[2]
    return None, text


def parse_concept_file(path: Path, bundle_root: Path = BUNDLE_ROOT) -> Concept | None:
    """Parse one file into a Concept. Returns None only if unreadable."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        rel = str(path.relative_to(BASE_DIR))
    except ValueError:
        rel = path.name
    try:
        cid = str(path.relative_to(bundle_root)).replace("\\", "/")[:-3]
    except ValueError:
        cid = path.stem

    raw_fm, body = _split_frontmatter(text)
    meta: dict = {}
    issues: list[str] = []
    if raw_fm is None:
        issues.append("missing frontmatter block")
    else:
        try:
            loaded = yaml.safe_load(raw_fm)
            meta = loaded if isinstance(loaded, dict) else {}
            if not isinstance(loaded, dict):
                issues.append("frontmatter is not a mapping")
        except yaml.YAMLError:
            issues.append("unparseable frontmatter YAML")
    if not str(meta.get("type", "")).strip():
        issues.append("missing required 'type' field")

    # Legacy v0.1 fallback: timestamp -> generated (spec section 13).
    if "generated" not in meta and meta.get("timestamp"):
        meta["generated"] = {"by": "legacy:unknown", "at": meta.pop("timestamp")}

    links = [(m.group(1), m.group(2)) for m in LINK_RE.finditer(body)
             if not re.match(r"(?i)(https?://|mailto:|#)", m.group(2))]
    return Concept(id=cid, path=path, rel=rel, meta=meta,
                   body=body.strip(), links=links, issues=issues)


def normalize_verified(meta: dict) -> list[dict]:
    """verified may be a list, a bare mapping (= one-element list), or legacy.

    Returns a list of event dicts. Tolerates legacy booleans from pre-OKF notes.
    """
    v = meta.get("verified")
    if v is None:
        return []
    if isinstance(v, dict):
        return [v]
    if isinstance(v, list):
        return [e for e in v if isinstance(e, dict)]
    if v is True:  # legacy pre-OKF boolean
        gen = meta.get("generated") or {}
        at = gen.get("at") if isinstance(gen, dict) else None
        return [{"by": "legacy:unknown", "at": at}]
    return []  # False, strings, anything else -> unverified


def trust_tier(meta: dict) -> str:
    """Derive trust tier from verified actors (spec section 5.3)."""
    events = normalize_verified(meta)
    if not events:
        return "unverified"
    if any(str(e.get("by", "")).startswith("human:") for e in events):
        return "human-reviewed"
    return "machine-confirmed"


def lifecycle_status(meta: dict) -> str:
    """Absent status means stable (spec section 5.4)."""
    return str(meta.get("status", "stable")).lower().strip() or "stable"


def parse_instant(value) -> datetime | None:
    """Parse an ISO 8601 instant; tolerate date-only YYYY-MM-DD as UTC midnight."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day)
    else:
        s = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
        if len(s) == 10:  # date-only
            dt = datetime(dt.year, dt.month, dt.day)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_stale(meta: dict, now: datetime | None = None) -> bool:
    """A concept is stale when now >= stale_after (spec section 5.5)."""
    if now is None:
        now = datetime.now(timezone.utc)
    if meta.get("stale_after") is None:
        return False
    instant = parse_instant(meta["stale_after"])
    if instant is None:
        return False  # unparseable date -> flagged in warnings, not stale
    return now >= instant


def evaluate_trust(meta: dict, now: datetime | None = None) -> dict:
    """Deterministic trust verdict. Never calls an LLM.

    Authoritative = stable status + some verification + not stale.
    Draft, deprecated, stale or unverified content is never authoritative.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    tier = trust_tier(meta)
    status = lifecycle_status(meta)
    stale = is_stale(meta, now)
    warnings: list[str] = []
    missing: list[str] = []

    if status == "draft":
        warnings.append("Status is 'draft': not yet reviewed, possibly incomplete. Verify before acting.")
    elif status == "deprecated":
        warnings.append("Status is 'deprecated': kept for history, no longer current. Do not follow it.")
    elif status not in VALID_STATUSES:
        warnings.append(f"Unknown status '{status}': treated as non-authoritative.")

    if tier == "unverified":
        warnings.append("Unverified: no 'verified' confirmation present. Treat as unconfirmed.")
        missing.append("verified")
    if "generated" not in meta:
        missing.append("generated")
    if not meta.get("sources"):
        missing.append("sources")
    if parse_instant(meta.get("stale_after")) is None and meta.get("stale_after") is not None:
        warnings.append(f"Unparseable 'stale_after' value '{meta.get('stale_after')}'.")
    if stale:
        warnings.append("Outdated: 'stale_after' has passed. Content may no longer be current.")

    authoritative = status == "stable" and tier != "unverified" and not stale
    return {"tier": tier, "status": status, "stale": stale,
            "authoritative": authoritative, "warnings": warnings, "missing": missing}


def trust_warnings(meta: dict) -> list[str]:
    """Backwards-compatible wrapper returning just the warning strings."""
    return evaluate_trust(meta)["warnings"]


# ---------- Sections (retrieval units) ----------

def chunk_concept(concept: Concept) -> list[dict]:
    """Split a concept body into sections by ## headings.

    Each chunk keeps a reference to the full meta dict so trust travels
    with the text. Relevance scores are stored separately at retrieval time.
    """
    chunks = []
    matches = list(HEADING_RE.finditer(concept.body))
    if not matches:
        if concept.body.strip():
            chunks.append({"concept_id": concept.id, "source": concept.rel,
                           "section": str(concept.meta.get("title", concept.id)),
                           "text": concept.body.strip(), "meta": concept.meta})
        return chunks
    intro = concept.body[:matches[0].start()].strip()
    if intro:
        chunks.append({"concept_id": concept.id, "source": concept.rel,
                       "section": str(concept.meta.get("title", concept.id)),
                       "text": intro, "meta": concept.meta})
    for i, m in enumerate(matches):
        section = m.group(1).strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(concept.body)
        text = concept.body[m.end():end].strip()
        if text:
            chunks.append({"concept_id": concept.id, "source": concept.rel,
                           "section": section, "text": f"{section}\n{text}",
                           "meta": concept.meta})
    return chunks


def load_bundle(bundle_root: Path = BUNDLE_ROOT):
    """Load all concepts, skipping reserved index.md/log.md files."""
    concepts: dict[str, Concept] = {}
    if bundle_root.exists():
        for path in sorted(bundle_root.rglob("*.md")):
            if path.name in RESERVED_NAMES:
                continue
            concept = parse_concept_file(path, bundle_root)
            if concept is not None:
                concepts[concept.id] = concept
    chunks = [c for concept in concepts.values() for c in chunk_concept(concept)]
    return concepts, chunks


# ---------- Links ----------

def resolve_link(target: str, from_concept: Concept,
                 concepts: dict[str, Concept],
                 bundle_root: Path = BUNDLE_ROOT) -> str | None:
    """Resolve a markdown link target to a concept id. None if broken/external.

    Broken links are tolerated (spec section 6.1): they mean not-yet-written
    knowledge, not malformed data.
    """
    t = target.split("#")[0].strip()
    if not t or not t.endswith(".md"):
        return None
    if t.startswith("/"):
        cid = t[1:-3]
    else:
        resolved = (from_concept.path.parent / t).resolve()
        try:
            cid = str(resolved.relative_to(bundle_root.resolve())).replace("\\", "/")[:-3]
        except ValueError:
            return None
    return cid if cid in concepts else None


def traverse_links(start_ids: list[str], concepts: dict[str, Concept],
                   max_hops: int = 1, max_results: int = 6) -> list[tuple[str, str]]:
    """Breadth-first walk of concept links, bounded. Returns [(id, via_id)]."""
    seen = set(start_ids)
    found: list[tuple[str, str]] = []
    frontier = list(start_ids)
    for _ in range(max_hops):
        nxt = []
        for cid in frontier:
            concept = concepts.get(cid)
            if concept is None:
                continue
            for _, target in concept.links:
                rid = resolve_link(target, concept, concepts)
                if rid and rid not in seen:
                    seen.add(rid)
                    found.append((rid, cid))
                    nxt.append(rid)
                    if len(found) >= max_results:
                        return found
        frontier = nxt
    return found


# ---------- Retrieval math (model-agnostic) ----------

def cosine_top_k(query_vec, matrix, k: int = TOP_K) -> list[tuple[int, float]]:
    """Top-k cosine similarities for L2-normalized vectors. Returns [(idx, score)]."""
    if np is not None and isinstance(matrix, np.ndarray) and matrix.size:
        scores = matrix @ np.asarray(query_vec, dtype=np.float32)
        order = np.argsort(-scores)[:k]
        return [(int(i), float(scores[i])) for i in order]
    # Pure-python fallback (used by tests with stub vectors).
    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))
    scored = sorted(((i, dot(query_vec, row)) for i, row in enumerate(matrix)),
                    key=lambda p: -p[1])
    return scored[:k]


def has_useful_evidence(results) -> bool:
    return bool(results) and results[0][1] >= SIMILARITY_THRESHOLD


# ---------- Investigation plan (deterministic, evidence-grounded) ----------

# Each candidate step names the concept(s) that can support it. A step is
# included only when retrieved or linked evidence covers it; otherwise it
# is reported as missing evidence. No LLM is involved.
PLAN_STEPS = [
    ("Scope the alert",
     ["soc/suspicious-login-detection", "soc/account-compromise-investigation"],
     "Confirm the account, anomalous login time, source IP/location, and alert time."),
    ("Collect authentication log evidence",
     ["soc/auth-log-sources"],
     "Pull sign-in/logon events for the window plus one day on each side; note gaps."),
    ("Check endpoint evidence",
     ["soc/endpoint-alert-evidence"],
     "Collect EDR telemetry from involved hosts before remediation; preserve evidence."),
    ("Assess account compromise",
     ["soc/account-compromise-investigation"],
     "Determine scope across VPN/mail/SSO/servers; contain only after preservation."),
    ("Check credential exposure",
     ["soc/credential-exposure"],
     "Check for leaked/breached credentials; rotate only on suspected compromise."),
    ("Decide escalation",
     ["soc/incident-escalation"],
     "Escalate on confirmed compromise, lateral movement, or high-value accounts."),
]


def extract_alert_facts(question: str) -> dict:
    """Classify an alert conservatively and retain analyst-provided wording."""
    text = " ".join(str(question).split())
    lower = text.lower()
    if any(term in lower for term in ("api token", "api key", "access token",
                                      "bearer token", "secret leaked",
                                      "token exposed", "credential exposed")):
        alert_type = "exposed_api_token"
    elif any(term in lower for term in ("powershell", "pwsh")) and \
            any(term in lower for term in ("login", "logon", "sign-in", "authentication")):
        alert_type = "suspicious_login_with_powershell"
    elif any(term in lower for term in ("login", "logon", "sign-in",
                                        "authentication", "impossible travel")):
        alert_type = "suspicious_login"
    else:
        alert_type = "unsupported"
    fragments = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    facts = fragments or ([text] if text else [])
    return {"type": alert_type, "observed_facts": facts, "raw": text}


ALERT_PLAN_STEPS = {
    "exposed_api_token": [
        ("Identify token scope and owner", ["cybersecurity/secret-detection", "soc/credential-exposure"],
         "Confirm the token type, owner, permissions, repositories or services in scope, and whether the alert identifies a specific token."),
        ("Establish exposure duration and location", ["cybersecurity/secret-detection", "soc/credential-exposure"],
         "Preserve the exposure timestamp, first-seen location, repository/path, branch, commit, and any history needed to bound exposure."),
        ("Review repository history and copies", ["cybersecurity/secret-detection"],
         "Search commits, branches, forks, build logs, artifacts, caches, and other copies for the token or related secret."),
        ("Check for token use and audit evidence", ["soc/auth-log-sources", "soc/credential-exposure"],
         "Correlate service, API, identity, and network audit records for token use during the exposure window; record gaps and unknowns."),
        ("Apply documented revocation or rotation policy", ["soc/credential-exposure", "soc/incident-escalation"],
         "Verify the applicable policy and owner approval before revocation or rotation; this copilot does not perform the action."),
        ("Assess impact and escalation", ["soc/incident-escalation"],
         "Assess affected services, data access, and confirmed use, then escalate according to the supported incident criteria."),
    ],
    "suspicious_login_with_powershell": [
        ("Preserve the alert facts and timeline", ["soc/suspicious-login-detection", "soc/account-compromise-investigation"],
         "Record the observed authentication event and endpoint PowerShell alert in their original order, including timestamps, account, source, and host details."),
        ("Correlate authentication and endpoint timelines", ["soc/auth-log-sources", "soc/endpoint-alert-evidence"],
         "Align sign-in/logon records with PowerShell process, parent-process, user, host, and network telemetry to test whether the events are related."),
        ("Validate the login and endpoint context", ["soc/suspicious-login-detection", "soc/endpoint-alert-evidence"],
         "Check source IP or location, device ownership, session details, command-line evidence, and whether the PowerShell activity was expected."),
        ("Assess account and host compromise", ["soc/account-compromise-investigation", "soc/endpoint-alert-evidence"],
         "Look for follow-on access, persistence, lateral movement, credential use, and additional affected endpoints without taking containment actions."),
        ("Check credential exposure", ["soc/credential-exposure"],
         "Check whether the account or related credentials appear in exposure evidence and document what is not yet known."),
        ("Decide escalation", ["soc/incident-escalation"],
         "Escalate based on corroborated account compromise, malicious endpoint activity, lateral movement, or high-value asset involvement."),
    ],
    "suspicious_login": PLAN_STEPS,
}


def build_plan(question: str, evidence: list, related: list,
               concepts: dict[str, Concept],
               now: datetime | None = None) -> dict:
    """Build an investigation plan grounded ONLY in retrieved evidence.

    evidence: [(chunk, score, reason)] with score kept separate from trust.
    related: [(concept_id, via_id)] from link traversal.
    Returns {summary, steps, related, missing, limitations}.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    facts = extract_alert_facts(question)
    plan_steps = ALERT_PLAN_STEPS.get(facts["type"], PLAN_STEPS)
    covered = {c["concept_id"] for c, _, _ in evidence} | {cid for cid, _ in related}
    steps = []
    for title, concept_ids, action in plan_steps:
        supporting = [(c, s) for c, s, _ in evidence if c["concept_id"] in concept_ids]
        linked = [cid for cid in concept_ids
                if cid in covered and cid not in {c["concept_id"] for c, _ in supporting}]
        if not supporting and not linked:
            continue
        if supporting:
            chunk, score = supporting[0]
            trust = evaluate_trust(chunk["meta"], now)
            steps.append({
                "title": title, "action": action,
                "citation": f"{chunk['source']}#{chunk['section']}",
                "concept_id": chunk["concept_id"], "score": round(score, 2),
                "authoritative": trust["authoritative"], "tier": trust["tier"],
                "warnings": trust["warnings"],
            })
        else:
            concept = concepts.get(linked[0])
            trust = evaluate_trust(concept.meta if concept else {}, now)
            steps.append({
                "title": title, "action": action,
                "citation": f"{concept.rel if concept else linked[0]} (via link)",
                "concept_id": linked[0], "score": None,
                "authoritative": trust["authoritative"], "tier": trust["tier"],
                "warnings": trust["warnings"],
            })

    stepped = {s["concept_id"] for s in steps}
    for chunk, score, reason in evidence:
        if chunk["concept_id"] in stepped or score <= 0:
            continue  # linked discoveries are shown under Related knowledge
        trust = evaluate_trust(chunk["meta"], now)
        if trust["authoritative"]:
            continue  # authoritative but off-plan; stays visible in evidence list
        # Weak/conflicting evidence (draft, deprecated, stale, unverified)
        # is surfaced as a flagged step, never silently dropped.
        stepped.add(chunk["concept_id"])
        steps.append({
            "title": f"Review flagged evidence ({chunk['concept_id']})",
            "action": ("Retrieved content conflicts with, or is weaker than, "
                       "the plan above. Read it only to understand the "
                       "conflict, then follow the authoritative step."),
            "citation": f"{chunk['source']}#{chunk['section']}",
            "concept_id": chunk["concept_id"], "score": round(score, 2),
            "authoritative": False, "tier": trust["tier"],
            "warnings": trust["warnings"],
        })
    needed = {cid for _, cids, _ in plan_steps for cid in cids}
    missing = sorted(needed - covered)
    limitations = [
        "This copilot drafts investigation plans only. It never blocks accounts, isolates hosts, or revokes sessions.",
        "Retrieved content is untrusted reference text, not instructions to execute.",
        "A high relevance score means similar wording, not correctness; trust comes from verification metadata.",
    ]
    fact_summary = " ".join(facts["observed_facts"])
    hypotheses = {
        "exposed_api_token": ["The exposed token may have been copied or used; audit evidence is required."],
        "suspicious_login_with_powershell": ["The authentication and PowerShell events may be related; correlate timestamps and identities."],
        "suspicious_login": ["The login may be unauthorized; verify identity, device, location, and session evidence."],
        "unsupported": ["No alert-specific hypothesis is asserted until the event type is clarified."],
    }[facts["type"]]
    summary = (f"Alert type: {facts['type']}. Observed facts: {fact_summary or 'none provided'}. "
               f"Evidence covers {len(covered & needed)}/{len(needed)} plan areas "
               f"from {len(evidence)} retrieved section(s).")
    if facts["type"] == "unsupported":
        limitations.append("Alert type was not recognized; the plan uses the general investigation profile.")
    return {"summary": summary, "steps": steps, "related": related,
            "missing": missing, "limitations": limitations, "alert": facts,
            "hypotheses": hypotheses}


def insufficient_message() -> str:
    return ("Insufficient evidence: no section in the local knowledge bundle "
            "is similar enough to ground an investigation plan. Rephrase the "
            "alert, or add a concept covering this topic. No plan was generated.")
