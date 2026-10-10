---
type: Reference
title: Endpoint Alert Evidence
description: Illustrative guidance on what endpoint telemetry to collect for a login investigation.
tags: [endpoint, edr, evidence, forensics]
status: stable
generated: { by: human:analyst, at: 2026-09-10T10:00:00Z }
verified: [{ by: process:editorial-check, at: 2026-09-11T10:00:00Z }]
stale_after: 2027-06-01T00:00:00Z
sources:
  - id: compromise
    resource: /soc/account-compromise-investigation.md
    title: Account Compromise Investigation in this bundle
---

# Endpoint Alert Evidence

All guidance below is illustrative and for training use. Preserve evidence before remediation.

## Host Telemetry to Collect

Pull EDR process trees, newly created scheduled tasks or services, and browser session or token artifacts for the suspect host and time window.
Record host IP, MAC, logged-on users, and active network connections at collection time.
Isolate the host only after volatile evidence is captured, per [Account Compromise Investigation](/soc/account-compromise-investigation.md).[^compromise]

## Correlating Logins to Endpoints

Match the login source IP and timestamp against VPN, DHCP, and EDR inventory to identify the actual device.
A login with no matching managed device suggests an unmanaged or external host; treat it as higher risk.
Note gaps explicitly: missing EDR coverage is itself a finding, not proof of cleanliness.

## Evidence Handling

Keep original timestamps, hashes, and collection commands with every artifact.
Store copies in the case folder before analysis so remediation cannot destroy evidence.

[^compromise]: Account Compromise Investigation in this bundle
