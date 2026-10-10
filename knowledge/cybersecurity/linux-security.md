---
type: Guide
title: Linux Security Essentials
description: Illustrative hardening steps for personal and small-team Linux systems.
tags: [linux, ssh, hardening]
status: stable
generated: { by: human:analyst, at: 2023-06-01T10:00:00Z }
verified: [{ by: process:editorial-check, at: 2023-06-02T10:00:00Z }]
stale_after: 2024-01-01T00:00:00Z
sources:
  - id: auth-logs
    resource: /soc/auth-log-sources.md
    title: Authentication Log Sources (illustrative log guidance in this bundle)
---

# Linux Security Essentials

## Updates and Patching

Enable automatic security updates and reboot when the kernel requires it.
Run `sudo apt update && sudo apt upgrade` (Debian/Ubuntu) regularly and track pending CVEs for exposed services.
Remove unused packages to shrink the attack surface.

## Users and SSH Hardening

Disable password login for SSH and use key-based authentication with `PasswordAuthentication no`.
Disable direct root login (`PermitRootLogin no`) and use sudo with individual user accounts.
Review `/etc/passwd` and `lastlog` for unexpected accounts or logins. Auth log locations are listed in [Authentication Log Sources](/soc/auth-log-sources.md).

## File Permissions and Sudo

Use least-privilege permissions: `chmod 600` for private keys, `chmod 755` for public directories.
Audit sudo rules with `sudo -l` and keep only required entries in `/etc/sudoers.d/`.
Monitor sensitive files such as `/etc/shadow` and `/etc/sudoers` for unexpected changes.
