---
type: Playbook
title: Incident Escalation
description: Illustrative criteria and steps for escalating a login investigation to incident response.
tags: [escalation, incident-response, severity]
status: stable
generated: { by: human:analyst, at: 2026-09-12T10:00:00Z }
verified: [{ by: process:editorial-check, at: 2026-09-13T10:00:00Z }]
stale_after: 2027-06-01T00:00:00Z
sources:
  - id: compromise
    resource: /soc/account-compromise-investigation.md
    title: Account Compromise Investigation in this bundle
---

# Incident Escalation

All guidance below is illustrative and for training use. Severity calls always need analyst judgement.

## When to Escalate

Escalate when compromise is confirmed, when lateral movement or data access is found, or when a privileged account is involved.[^compromise]
Escalate also when evidence is inconclusive but the account is high-value; uncertainty about key accounts is itself a reason.
Do not wait for complete evidence if active misuse is ongoing.

## How to Escalate

Open an incident with the alert summary, scoped accounts and hosts, collected evidence locations, and known gaps.
Page the on-call responder for confirmed compromise of privileged accounts or active data theft; otherwise queue for next-business-day review.
Link the investigation notes from [Account Compromise Investigation](/soc/account-compromise-investigation.md) into the incident record.

## Read-only Copilot Boundary

This copilot never blocks accounts, isolates hosts, or revokes sessions itself; it only drafts the plan.
Every containment action needs explicit human approval in the ticketing or EDR console.

[^compromise]: Account Compromise Investigation in this bundle
