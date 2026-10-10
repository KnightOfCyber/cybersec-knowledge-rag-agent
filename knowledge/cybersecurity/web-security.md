---
type: Guide
title: Web Security Fundamentals
description: Illustrative defensive practices against XSS, SQL injection, and insecure authentication.
tags: [web, xss, sqli, authentication]
status: stable
generated: { by: human:analyst, at: 2026-09-01T10:00:00Z }
verified: [{ by: process:editorial-check, at: 2026-09-02T10:00:00Z }]
stale_after: 2027-03-01T00:00:00Z
sources:
  - id: mitre-attack
    resource: https://attack.mitre.org/
    title: MITRE ATT&CK knowledge base (public reference)
---

# Web Security Fundamentals

## Cross-Site Scripting (XSS)

Treat all user input as untrusted. Escape output in HTML templates and use framework auto-escaping.
Set a Content-Security-Policy header to limit where scripts can load from.
Store session tokens in HttpOnly, Secure cookies rather than localStorage where possible.

## SQL Injection Prevention

Always use parameterized queries or prepared statements; never build SQL with string formatting.
Apply least-privilege database accounts so a web app user cannot drop tables or read other schemas.
Validate input type and length on the server side, and log rejected queries for review.

## Authentication and Sessions

Require MFA for admin accounts and rate-limit login attempts to slow credential stuffing.
Hash passwords with a memory-hard function such as bcrypt, scrypt, or Argon2id; never store plaintext passwords.
Expire sessions on logout and after inactivity, and rotate session IDs after login.
