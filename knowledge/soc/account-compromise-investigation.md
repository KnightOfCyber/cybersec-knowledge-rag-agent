---
type: Playbook
title: Account Compromise Investigation
description: Illustrative step-by-step playbook for investigating a possibly compromised account.
tags: [investigation, account-takeover, playbook]
status: stable
generated: { by: human:analyst, at: 2026-09-12T10:00:00Z }
verified: [{ by: process:editorial-check, at: 2026-09-13T10:00:00Z }]
stale_after: 2027-06-01T00:00:00Z
sources:
  - id: login-detection
    resource: /soc/suspicious-login-detection.md
    title: Suspicious Login Detection in this bundle
  - id: auth-logs
    resource: /soc/auth-log-sources.md
    title: Authentication Log Sources in this bundle
  - id: endpoint-evidence
    resource: /soc/endpoint-alert-evidence.md
    title: Endpoint Alert Evidence in this bundle
  - id: escalation
    resource: /soc/incident-escalation.md
    title: Incident Escalation in this bundle
---

# Account Compromise Investigation

All guidance below is illustrative and for training use. Adapt the order to the alert at hand.

## Scope the Alert

Confirm the account, the anomalous login time, source IP, and location using [Suspicious Login Detection](/soc/suspicious-login-detection.md) indicators.[^login-detection]
List every system the account touched in the window: VPN, mail, SSO apps, and servers.
Time-box the scope first; an unbounded trawl wastes the response window.

## Collect Authentication and Endpoint Evidence

Pull sign-in and logon events from [Authentication Log Sources](/soc/auth-log-sources.md) for the full window, plus one day on each side.[^auth-logs]
Collect [Endpoint Alert Evidence](/soc/endpoint-alert-evidence.md) from each involved host before any remediation.[^endpoint-evidence]
Record what was unavailable (for example, logs aged out) as missing evidence in the case notes.

## Contain and Escalate

If compromise is confirmed, revoke sessions, rotate credentials per [Credential Exposure](/soc/credential-exposure.md), and require MFA re-registration.
Escalate to incident response following [Incident Escalation](/soc/incident-escalation.md) when data access or lateral movement is found.[^escalation]
Do not delete attacker artifacts until evidence is preserved.

[^login-detection]: Suspicious Login Detection in this bundle
[^auth-logs]: Authentication Log Sources in this bundle
[^endpoint-evidence]: Endpoint Alert Evidence in this bundle
[^escalation]: Incident Escalation in this bundle
