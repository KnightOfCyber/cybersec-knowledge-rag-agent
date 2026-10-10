---
type: Guide
title: Secret Detection and Handling
description: Illustrative guidance for detecting leaked API keys and responding safely.
tags: [secrets, tokens, gitleaks, incident-response]
status: stable
generated: { by: human:analyst, at: 2026-09-01T10:00:00Z }
verified: [{ by: process:editorial-check, at: 2026-09-02T10:00:00Z }]
stale_after: 2027-01-01T00:00:00Z
sources:
  - id: cred-exposure
    resource: /soc/credential-exposure.md
    title: Credential Exposure (illustrative rotation guidance in this bundle)
---

# Secret Detection and Handling

## Preventing Leaked Secrets

Never commit API keys, passwords, or tokens to git. Use environment variables or a secret manager instead.
Add a pre-commit hook with tools like gitleaks or trufflehog to catch secrets before they are pushed.
Keep an `.env` file for local secrets and never commit it; commit only `.env.example` with placeholder values.

## Detecting Exposed Tokens

Scan repositories regularly with gitleaks (`gitleaks detect --source .`) or GitHub secret scanning alerts.
Look for high-entropy strings, `AKIA` AWS key prefixes, `ghp_` GitHub token prefixes, and `sk-` API key patterns.
Monitor cloud billing and login alerts for unexpected usage that may indicate a leaked credential.

## Responding to a Leaked Token

Treat any committed or published token as compromised. Revoke and rotate it immediately, then purge it from git history.
Check access logs for misuse between the leak time and the rotation time. See [Credential Exposure](/soc/credential-exposure.md) for the rotation checklist.
Replace the secret in all deployed environments and verify the old value no longer works.
