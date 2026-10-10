---
type: Guide
title: Network Security Basics
description: Illustrative defensive guidance for securing local networks, firewalls, and detecting port scans.
tags: [network, firewall, port-scan, wifi]
status: stable
generated: { by: human:analyst, at: 2026-09-01T10:00:00Z }
verified: [{ by: process:editorial-check, at: 2026-09-02T10:00:00Z }]
stale_after: 2027-06-01T00:00:00Z
sources:
  - id: soc-triage
    resource: /cybersecurity/soc-alerts.md
    title: SOC Alert Triage (illustrative triage steps in this bundle)
---

# Network Security Basics

## Firewalls and Segmentation

Use a host firewall (such as Windows Firewall or UFW on Linux) and keep default-deny inbound rules.
Place IoT devices on a separate VLAN or guest network so a compromised camera cannot reach workstations.
Review firewall rules quarterly and remove unused port forwards.

## Detecting Port Scans

A port scan is when an external or internal host probes many ports to find open services.
Defensive steps: monitor firewall logs for repeated connection attempts, use an IDS such as Snort or Suricata, and rate-limit inbound connections.
Do not expose management ports (22, 3389) directly to the internet; require a VPN instead.

## Public Wi-Fi Safety

Avoid accessing sensitive accounts over open public Wi-Fi without a trusted VPN.
Turn off automatic Wi-Fi reconnection and file sharing on public networks.
Verify the exact network name with staff before joining, to avoid evil-twin hotspots.
