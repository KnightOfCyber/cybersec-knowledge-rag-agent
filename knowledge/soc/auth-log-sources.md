---
type: Reference
title: Authentication Log Sources
description: Illustrative reference of where authentication events live on common platforms.
tags: [authentication, logging, windows, linux, entra]
status: stable
generated: { by: human:analyst, at: 2026-09-10T10:00:00Z }
verified: [{ by: process:editorial-check, at: 2026-09-11T10:00:00Z }]
stale_after: 2027-06-01T00:00:00Z
sources:
  - id: login-detection
    resource: /soc/suspicious-login-detection.md
    title: Suspicious Login Detection in this bundle
---

# Authentication Log Sources

All guidance below is illustrative and for training use. Field names vary by version and configuration.

## Windows Logon Events

Collect Security log events such as 4624 (successful logon), 4625 (failed logon), and 4648 (explicit credential logon).[^login-detection]
Forward domain controller logs to the SIEM; workstation-only collection misses lateral movement.
Include Logon Type, source IP, and process name in the forwarded fields.

## Linux and SSH Authentication

Review `auth.log` / `secure` log for `sshd` accepted and failed password events, plus `sudo` usage.
Centralize with journald forwarding or syslog so a compromised host cannot silently drop its own logs.
See the [Linux hardening notes](/cybersecurity/linux-security.md) for reducing SSH exposure.

## Cloud Identity Logs

Pull Entra ID / workspace sign-in logs including IP, location, device compliance, MFA result, and conditional-access outcome.
Alert on legacy protocol use (IMAP, POP, SMTP AUTH) and on MFA fatigue patterns such as repeated push prompts.
Join cloud sign-ins with [Endpoint Alert Evidence](/soc/endpoint-alert-evidence.md) by device ID where possible.

[^login-detection]: Suspicious Login Detection in this bundle
