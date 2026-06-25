# HARDWARIO Tower → Home Assistant discovery service

Passive MQTT discovery service that makes HARDWARIO Tower sensors appear
automatically in Home Assistant.

It **listens** to the telemetry Tower nodes already publish on
`node/{alias}/...` and synthesises Home Assistant MQTT discovery messages from
what it observes — no firmware changes, no capability-advertisement protocol, no
hand-maintained device registry. Entities are grouped one HA device per node via
shared `device.identifiers`.

## Status

Design approved; implementation pending. Authoritative design:
[`docs/superpowers/specs/2026-06-25-tower-ha-discovery-design.md`](docs/superpowers/specs/2026-06-25-tower-ha-discovery-design.md).
Earlier exploratory notes are archived under [`docs/archive/`](docs/archive/).

## How it works (summary)

- Subscribe `node/+/#`; parse only true telemetry topics
  (`node/{alias}/{resource}/{address}/{quantity}` — exactly five `/`-segments;
  four-segment command topics like `.../trigger/set` are ignored).
- Map `resource`/`quantity` → HA `device_class`/`unit`/`expire_after` via a small
  static sensor map.
- Publish retained per-component discovery to `homeassistant/sensor/{id}/config`,
  all entities of a node sharing one `device` block.
- **Allowlist** by alias (default `^[^:]+:[^:]+:[0-9]+$`): only nodes renamed to
  the `role:location:id` convention are discovered — renaming *is* the opt-in, so
  gateway-default and dev/test nodes never leak.
- **First-discovery debounce** (default 120 s): buffer a new node's entities, then
  publish the device complete in one go.
- **Startup adoption:** rebuild in-memory state from the broker's retained
  discovery configs (`adopt → reconcile → go live`); the service holds no
  persistent state of its own.
- Small HTTP API (health/readiness probes + list/forget) on Ingress.

## Development

> _To be completed during implementation._ Will cover: venv setup, running
> locally against a broker, running the `assert`-based self-check, building the
> container image (look up and pin **current stable** Python + `paho-mqtt` at
> build time), and deploying to the `home-assistant` namespace.

## HTTP API

> _To be completed during implementation._ `GET /health`, `GET /ready`,
> `GET /devices`, `DELETE /devices/{alias}`,
> `DELETE /devices/{alias}/entities/{object_id}` (mutating endpoints require a
> bearer token).

## Deferred features

Ideas intentionally **out of current scope** (sensors-only), recorded here so
they aren't lost:

- **Actuators (lights / controllable fans / pump-fill).** Not observable — they
  are command topics the device *subscribes* to — and the current
  "smart endpoints, dumb pipes" resilient-control firmware is not HA-compatible.
  Path when ready: build HA-compatible actuator firmware first, have each custom
  node publish a small purpose-built *actuator-layout* message, and add a thin
  per-firmware adapter in this service that maps it to HA `light`/`fan`/etc.
  discovery — reusing the existing device-grouping, naming, allowlist and
  retained-lifecycle machinery. The sensor path stays untouched.

- **Explicit state store (e.g. NATS JetStream KV).** Only needed if we ever want
  state that *isn't* derivable from retained discovery configs — e.g. a
  forget/audit history. Not required while seen-state is rebuilt from retained
  configs at startup. If added, prefer the existing JetStream KV over a PVC
  (already running, replicated, no volume pinning).

- **Telemetry-stream replay as cold-start.** The Tower telemetry is persisted in
  JetStream, so startup could replay `node.>` history instead of adopting
  retained configs. Costs a second client (NATS/JetStream consumer) and a
  liveness time-window to avoid resurrecting decommissioned nodes. Only worth it
  if retained-config adoption proves insufficient.

- **`sw_version` on device cards.** Observation can't see firmware version; an
  optional gateway node-list lookup (`gateway/{id}/nodes`) could enrich device
  metadata.

- **Per-topic friendly-name overrides / richer naming.** Beyond the
  `role:location:id` generator and `location → label` map.
