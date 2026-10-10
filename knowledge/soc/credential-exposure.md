---
type: Guide
title: Credential Exposure
description: Illustrative guidance for handling exposed passwords and tokens during an investigation.
tags: [credentials, rotation, secrets, mfa]
status: stable
generated: { by: human:analyst, at: 2026-09-12T10:00:00Z }
verified: [{ by: process:editorial-check, at: 2026-09-13T10:00:00Z }]
stale_after: 2027-06-01T00:00:00Z
sources:
  - id: secret-detection
    resource: /cybersecurity/secret-detection.md
    title: Secret Detection and Handling in this bundle
---

# Credential Exposure

All guidance below is illustrative and for training use.

## Rotation on Suspected Compromise

Rotate credentials only when compromise is suspected or exposure is confirmed; avoid scheduled mass rotations that push users toward weak passwords.[^secret-detection]
Revoke active sessions and tokens at rotation time, otherwise the old session stays usable.
Prefer phishing-resistant MFA (such as FIDO2 keys) when re-enrolling the account after rotation.

## Detecting Exposure

Check whether the account's password appears in known breach corpora or internal secret scans; see [Secret Detection and Handling](/cybersecurity/secret-detection.md) for scanning tools.
Review password-reset and MFA-change events around the alert time for attacker-driven changes.
Treat committed or published tokens as compromised and rotate them immediately.

## Conflicting Older Advice

An older deprecated note in this bundle, [Legacy Password Rotation](/soc/legacy-password-rotation.md), recommends forcing password changes every 30 days.
That advice is deprecated and conflicts with this concept: follow this current guidance instead of the legacy note.

[^secret-detection]: Secret Detection and Handling in this bundle
