---
type: Reference
title: Proposed EDR Query Draft
description: Draft illustrative sketch of an EDR query for login correlation, not yet reviewed.
tags: [edr, draft, hunting]
status: draft
generated: { by: human:analyst, at: 2026-10-05T10:00:00Z }
stale_after: 2027-12-01T00:00:00Z
sources:
  - id: endpoint-evidence
    resource: /soc/endpoint-alert-evidence.md
    title: Endpoint Alert Evidence in this bundle
---

# Proposed EDR Query Draft

This is an unreviewed draft sketch. Verify every field name against your own EDR schema before use.

## Sketch Query Idea

A possible starting sketch joins logon events to device inventory on IP and time, roughly: filter logons in the alert window, then join to inventory on source IP.
Field names below are placeholders, not tested queries: `device_ip`, `logon_time`, `account_name`.
Cross-check any result with [Endpoint Alert Evidence](/soc/endpoint-alert-evidence.md) collection steps before relying on it.[^endpoint-evidence]

[^endpoint-evidence]: Endpoint Alert Evidence in this bundle
