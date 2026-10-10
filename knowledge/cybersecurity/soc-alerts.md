---
type: Playbook
title: SOC Alert Triage
description: Draft illustrative triage steps for common SOC alerts including phishing and malware.
tags: [soc, triage, phishing, malware]
status: draft
generated: { by: human:analyst, at: 2026-10-01T10:00:00Z }
stale_after: 2027-12-01T00:00:00Z
sources:
  - id: compromise-investigation
    resource: /soc/account-compromise-investigation.md
    title: Account Compromise Investigation (illustrative steps in this bundle)
---

# SOC Alert Triage

## Phishing Alert Triage

Possible phishing indicators include mismatched sender domains, urgent language, and unexpected attachments.
Suggested triage: quarantine the message, check mail gateway logs, and confirm with the reported user before closing the alert.
Verify sender headers and URLs in a sandbox; do not click links on a production workstation.

## Malware Alert Triage

Isolate the host from the network but leave it powered on to preserve memory forensics.
Suggested triage: collect EDR telemetry, check file hashes against threat intelligence, and escalate if lateral movement is seen.
Reimage from a known-good source after evidence is collected.

## False Positive Handling

Low-fidelity rules often fire on admin tools and vulnerability scanners.
Suggested triage: compare against an allowlist of known-good tools, document the reason, and tune the rule only after analyst review.
