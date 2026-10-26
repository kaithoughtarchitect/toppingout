# Security

Topping Out runs inside your own repo, with your own coding agent and your own keys. It ships no service and holds no data.

## Reporting a problem

If you find a security problem (a script that could leak a secret, run something it shouldn't, or push without the owner's word), please report it privately: on this repo's **Security** tab, choose **Report a vulnerability**. Please don't open a public issue for it.

Say what you ran, what happened, and how to reproduce it. Reports are answered on a best-effort basis; there is no paid support.

## What is in scope

- The scripts in this repo (`skills/`, `scripts/`, the installer `skills/f-setup/install.mjs`).
- The rules the method sets for the foreman (`RULES.md`), where following them as written could cause harm.

Problems in Claude Code, other coding agents, GitHub or model providers belong with those projects.
