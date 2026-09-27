# Security Policy

**OmniScale Enterprise Pro** — Designed and Developed by NIKHIL CHARY SRIRAMOJU

## Reporting a vulnerability

Please do **not** open a public GitHub issue for security vulnerabilities.

Instead, use GitHub's private reporting:
[Security → Report a vulnerability](https://github.com/Nikhil-creat/omniscale-enterprise-pro/security/advisories/new)

Include:
- A description of the vulnerability and its potential impact
- Steps to reproduce (a minimal repro is ideal)
- Any suggested fix, if you have one

## Supported versions

Only the `main` branch is actively maintained and receives security fixes.

## Automated scanning

This repository runs:
- **CodeQL** static analysis on every push/PR and weekly (`.github/workflows/codeql.yml`)
- **Dependabot** dependency and Docker base-image updates weekly (`.github/dependabot.yml`)
