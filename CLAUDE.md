# CLAUDE.md

Passive MQTT discovery service: listens to HARDWARIO Tower telemetry and
synthesises Home Assistant MQTT discovery messages. Sensors only.

Authoritative design: `docs/superpowers/specs/2026-06-25-tower-ha-discovery-design.md`.
User-facing docs and dev cycle: `README.md`. Read both before non-trivial changes.

## Layout

- `src/discovery.py` — pure functions: topic parsing, sensor map, payload builders. No I/O. All unit-tested.
- `src/ha-tower-discovery.py` — the service: `Configuration`, `TowerDiscoveryService` (MQTT + lifecycle), HTTP handler, `main`.
- `src/test_discovery.py` — stdlib `assert` self-check, no framework. Run: `.venv/bin/python src/test_discovery.py`.
- `kubernetes/` — Deployment (namespace `home-assistant`, `strategy: Recreate`), ConfigMap, Service, Ingress.

## Invariants (don't break these)

- **Telemetry vs command topics:** only `node/{alias}/{resource}/{address}/{quantity}` — exactly 5 `/`-segments — is telemetry. 6-segment command topics (`.../trigger/set`) are messages *to* the device and MUST be ignored. This is the core correctness rule.
- **Allowlist is opt-in by rename.** Default `^[^:]+:[^:]+:[0-9]+$` matches only nodes renamed to `role:location:id`; gateway-default `name:id` aliases must not leak into HA.
- **Discovery is per-component** (`homeassistant/sensor/{id}/config`), retained, all entities of a node sharing one `device` block. Removal = empty retained payload.
- No persistent state: seen-state is rebuilt from retained configs on startup (adopt → reconcile → go live).

## Conventions

- Dependencies: stdlib + `paho-mqtt` only. Don't add deps for what a few lines do.
- Non-trivial logic gets an `assert` case in `test_discovery.py` — no other test framework.
- Image tags = git short SHA, never `latest` (see README build section).
