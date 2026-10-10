---
type: Detection
title: Suspicious Login Detection
description: Illustrative guidance for recognizing suspicious authentication activity such as impossible travel and credential stuffing.
tags: [authentication, detection, impossible-travel, brute-force]
status: stable
generated: { by: human:analyst, at: 2026-09-10T10:00:00Z }
verified: [{ by: process:editorial-check, at: 2026-09-11T10:00:00Z }]
stale_after: 2027-06-01T00:00:00Z
sources:
  - id: auth-logs
    resource: /soc/auth-log-sources.md
    title: Authentication Log Sources in this bundle
  - id: compromise
    resource: /soc/account-compromise-investigation.md
    title: Account Compromise Investigation in this bundle
---

# Suspicious Login Detection

All guidance below is illustrative and for training use. Confirm against your own telemetry before acting.

## Impossible Travel

Flag logins from two distant locations within a time window too short for physical travel (for example, two countries within 30 minutes).[^auth-logs]
Corroborate with IP geolocation, VPN egress records, and the user's known travel schedule before concluding compromise.
Mobile carrier NAT and corporate VPN exits are common benign explanations; document them when ruled out.

## Brute Force and Credential Stuffing

Look for many failed logins followed by a success, or a burst of failures across many accounts from one source.
Rate-limit and alert on repeated `failed logon` events per source IP and per account, using [Authentication Log Sources](/soc/auth-log-sources.md) to find the right event IDs.
A success after a failure burst should pivot to [Account Compromise Investigation](/soc/account-compromise-investigation.md).[^compromise]

## Alert Triage Basics

Record the alert time, account, source IP, ASN, geolocation, user agent, and authentication method for every login alert.
If credential theft is suspected, also check [Credential Exposure](/soc/credential-exposure.md) for leaked-password handling.
Escalate per [Incident Escalation](/soc/incident-escalation.md) when compromise is confirmed or strongly suspected.

[^auth-logs]: Authentication Log Sources in this bundle
[^compromise]: Account Compromise Investigation in this bundle
