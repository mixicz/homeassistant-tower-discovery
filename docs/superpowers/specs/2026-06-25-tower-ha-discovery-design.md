# Tower → Home Assistant Sensor Discovery — Design

- **Date:** 2026-06-25
- **Status:** Approved design, pending implementation plan
- **Verified against:** Home Assistant MQTT integration docs, June 2026

## Problem

A HARDWARIO Tower fleet (battery/radio nodes via a USB-dongle gateway) and a
Home Assistant instance share an MQTT broker. Tower nodes already publish sensor
telemetry to deterministic `node/{alias}/...` topics, but HA has no entities for
them. We want Tower sensors to appear in HA automatically, grouped one HA device
per node, with sensible names and proper staleness handling — without firmware
changes and without a hand-maintained device registry.

An earlier abandoned attempt (`src/ha-tower-discovery.py` + Jinja templates +
`doc/tower-advertise.md` capability protocol) is superseded by this design.

## Approach: passive observation

The service **listens** to the telemetry nodes already publish and synthesises HA
MQTT discovery messages from what it observes. No capability advertisement
protocol, no per-device descriptor files, no firmware changes for sensors.

```
node/+/#  ──▶  parse topic ──▶  matches sensor map?  ──▶  publish retained
(live telemetry)                       │  yes                 homeassistant/sensor/{id}/config
                                       │                      (device_class, unit, expire_after,
                                       │                       shared device block, origin)
                                       └─ allowlist filter on alias (rename = opt-in)
```

Rationale: ~90% of discovery need (sensors, including highly variable custom-node
sensor sets and ad-hoc added tags) is *read-only telemetry the device already
announces by publishing*. There is no source of truth to maintain — the live
topic stream is the source. The remaining ~10% (actuators) is non-observable and
deferred (see Non-goals).

## Goals

- Auto-discover all read-only Tower **sensors** across stock and custom nodes.
- Group entities into **one HA device per node** via shared `device.identifiers`.
- Human-readable device/entity names derived from the alias naming convention.
- Per-sensor-type **`expire_after`** so lost-connectivity sensors show
  `unavailable` rather than a stale value.
- **Allowlist** control over which nodes are published (dev/test nodes excluded).
- **First-discovery debounce** so a node appears in HA complete on first publish.
- **Operator API** (list / forget) on Ingress + **health probes** for Kubernetes.
- Deploy as a **Kubernetes Deployment** in the `home-assistant` namespace.
- Documented in **mixi-docs** plus a local README covering the dev cycle.
- Survive service and HA restarts.
- Zero firmware changes.

## Non-goals (deferred / out of scope)

- **Actuators** (lights W/RGB/RGBW, controllable fans, pump/fill). They are not
  observable (command topics the device subscribes to), their semantics live only
  in firmware config, and the current "smart endpoints, dumb pipes" control model
  is not HA-compatible. They require an HA-compatible actuator firmware effort
  first, after which they will be discovered via a **firmware-publish layer**
  (the node publishes a small purpose-built "my actuators" message the service
  consumes). This design leaves that as a clean future extension point; it is not
  built now.
- Gateway node-list querying (`gateway/{id}/nodes`) — not needed; observation
  learns every node from its topics. May be re-added later only to enrich device
  metadata (e.g. `sw_version`), which observation cannot see.
- Pushing config *to* devices (the never-finished "tower config service").

## Architecture

Single long-running Python process, co-located with the broker.

1. Connect to MQTT broker; subscribe `node/+/#`.
2. On each message, parse the topic as
   `node/{alias}/{resource}/{addr}/{quantity}`
   e.g. `node/climate-monitor:hall:0/thermometer/0:0/temperature`.
   (Note the alias itself may contain colons; see Topic parsing.)
3. Apply the **allowlist** to `{alias}`. If it does not match, ignore.
4. Look up `{resource}` + `{quantity}` in the **sensor map**. If absent, ignore
   (debug-log once).
5. Build the per-entity discovery config and route it through the
   **first-discovery debounce** (below): buffer it if the node is new, else
   publish immediately if changed.
6. Record the published entity in the persisted seen-state.

The unit `topic(s) → discovery message(s)` is a **pure function** and is the
primary test surface (no broker required). MQTT runs on `loop_start()` (paho
background thread); a periodic tick flushes debounce buffers; the HTTP API runs
in the main thread.

### First-discovery debounce

When the first entity for an **unseen node** (alias not in seen-state) is
observed, the service does **not** publish immediately. It opens a buffer for
that node and starts a timer (configurable, default **120 s**). On device boot
every sensor emits a fresh measurement, so the window gives the node a fair
chance to reveal its full sensor set. When the timer expires, all buffered
entities for the node are published together (retained), so the device appears in
HA complete on first try rather than growing entity-by-entity.

After a node is established (its buffer has flushed once), any *newly* observed
entity for it publishes immediately — no second debounce. Changed content for an
already-published entity is an immediate idempotent upsert.

`ponytail:` one timer per pending node, flushed by the periodic tick; no
scheduler library.

### Topic parsing

Tower telemetry topic shape after the gateway prefix is
`node/{alias}/{resource}/{address}/{quantity}`. The alias can contain colons
(`role:location:id`), and the address uses `bus:device` (e.g. `1:3`). Parse by:
- strip leading `node/`,
- the **alias** is everything up to the resource segment — match the alias
  against the allowlist regex first (which is anchored and colon-structured), then
  treat the remainder as `{resource}/{address}/{quantity}`.

`ponytail:` if alias-vs-resource boundary is ever ambiguous, the allowlist regex
(`^[^:]+:[^:]+:[0-9]+$` over the alias) disambiguates because resources are not
colon-triples. Revisit only if a real topic breaks this.

### Discovery message format

Per-component discovery (not the bundled device/`components` form), because it is
incremental: each newly observed sensor is one independent retained message;
existing entities are never touched.

Topic: `homeassistant/sensor/{object_id}/config` where `object_id` is
`sanitize(alias) + "__" + resource + "_" + address + "_" + quantity`, sanitised
to `[a-zA-Z0-9_-]`. `unique_id` = the same `object_id`.

Example payload:

```json
{
  "name": "Loop Temperature",
  "unique_id": "water-cooling-controller_rack_0__thermometer_1_3_temperature",
  "state_topic": "node/water-cooling-controller:rack:0/thermometer/1:3/temperature",
  "device_class": "temperature",
  "unit_of_measurement": "°C",
  "expire_after": 1500,
  "device": {
    "identifiers": ["water-cooling-controller:rack:0"],
    "name": "Rack — Water Cooling Controller",
    "model": "water-cooling-controller",
    "manufacturer": "HARDWARIO"
  },
  "origin": { "name": "tower-ha-discovery" }
}
```

All entities of a node carry the **same** `device.identifiers` (the alias) → HA
merges them into one device. `unique_id` is always set (required for grouping and
for in-HA renaming to persist). We do **not** emit the deprecated `object_id`
payload field (removed HA 2026.4); if pinning an entity_id is ever wanted, use
`default_entity_id`.

### Sensor map (the only domain knowledge)

A small static table mapping observed `resource`/`quantity` to HA metadata and a
default `expire_after`. Seeded from the resource→entity table in the archived
`docs/archive/tower-advertise.md` and the observed firmware topics. Unknown
resources are ignored.

| resource / quantity                 | device_class                     | unit | expire_after (s) |
|-------------------------------------|----------------------------------|------|------------------|
| `thermometer` / `temperature`       | temperature                      | °C   | 1500             |
| `hygrometer` / `relative-humidity`  | humidity                         | %    | 1500             |
| `lux-meter` / `illuminance`         | illuminance                      | lx   | 1500             |
| `barometer` / `pressure`            | atmospheric_pressure             | hPa  | 1500             |
| `barometer` / `altitude`            | distance                         | m    | 7200             |
| `voc-sensor` / `tvoc`               | volatile_organic_compounds_parts | ppb  | 1500             |
| `voc-lp-sensor` / `tvoc`            | volatile_organic_compounds_parts | ppb  | 1500             |
| `battery` / `voltage`               | voltage                          | V    | 7200             |
| `*` / `rpm`                         | (none)                           | rpm  | 600              |

Global default `expire_after` = 7200 (2 h) for any mapped type without an
explicit value. All values overridable in config. Adding a sensor type later =
one row.

### Naming

Aliases follow `role:location:id` (the user's convention; the gateway's default
`role:id` two-part form is intentionally **not** matched by the allowlist).

- **device.name** = `{Location} — {Role}` (e.g. `schodiste:` → "Schodiště");
  instance id appended only when > 0.
- **entity name** = the sensor type label (e.g. "Temperature"); for nodes with
  multiple sensors of one type, append the address (e.g. "Temperature 1:3").
- A configurable `location → label` map handles diacritics/capitalisation;
  default is title-case of the raw token.
- A configurable per-alias/per-entity **override map** handles oddities.
- Generated names are defaults only — HA-UI renames persist via `unique_id`.

### Filtering (allowlist)

A denylist is unusable: the gateway auto-assigns `role:id` aliases that would be
discovered before the user can rename them. Therefore **allowlist** of alias
regexes:

- Default rule: `^[^:]+:[^:]+:[0-9]+$` — matches the three-part
  `role:location:id` convention only. Effect: **renaming a node to the proper
  convention is the act of opting it into HA.** Dev/test nodes left at the
  gateway default `role:id` are never discovered; no cleanup needed.
- Additional allow patterns may be configured.

### Lifecycle & retained-message semantics

- **Add / update:** publish retained config to the entity topic. Re-publishing
  identical content is skipped (seen-state); re-publishing changed content is an
  idempotent HA upsert keyed on the discovery topic — existing entities do not
  reset.
- **Remove an entity:** publish a **zero-length retained** payload to its config
  topic. Because configs are retained, "stop publishing" is *not* removal — the
  retained message must be actively cleared or HA re-discovers it on reconnect.
- **Remove a device:** HA drops it automatically once its last entity is removed.
- **Reconcile:** when the allowlist changes such that a previously-discovered node
  no longer matches, the service clears that node's retained configs (empty
  payloads) on next run.
- **Forget (manual):** an operator-triggered path (the **Service API**, below)
  to clear a specific node's/entity's retained configs and drop it from
  seen-state.
- **Stale pruning:** OFF by default — a silent battery/radio node is asleep, not
  gone. `expire_after` already makes its entities show `unavailable`. (YAGNI;
  add opt-in pruning only if needed.)

### Persistence

Seen-state (set of published entity object_ids + their last-published content
hash) in a small JSON file (stdlib `json`), reloaded on start. Discovery configs
are retained on the broker regardless, so HA keeps entities across restarts; the
state file is to avoid redundant republishing and to drive reconcile/forget.

### Configuration surface

Broker host/port/credentials, `node/` and discovery (`homeassistant/`) prefixes,
allowlist patterns, sensor-map overrides (device_class/unit/`expire_after` per
type), global default `expire_after`, **first-discovery debounce seconds (default
120)**, `location → label` map, name override map, state-file path, **HTTP API
bind address/port**, debug. Config via env + CLI (existing `Configuration`
pattern); larger maps (sensor-map, locations, overrides) via a mounted config
file (ConfigMap).

## Service API & health

A small HTTP server (stdlib `http.server`, no framework) for operations and
Kubernetes probes. Read-only endpoints are unauthenticated; mutating endpoints
require a bearer token (from a Secret) since they're exposed on Ingress.

| Method & path            | Purpose |
|--------------------------|---------|
| `GET /health`            | Liveness: process up. Always 200 if serving. |
| `GET /ready`             | Readiness: 200 only when MQTT is connected. |
| `GET /devices`           | List discovered nodes and their entities (from seen-state). |
| `DELETE /devices/{alias}`| Forget a node: clear its retained discovery configs, drop from seen-state. |
| `DELETE /devices/{alias}/entities/{object_id}` | Forget a single entity. |

`ponytail:` stdlib `http.server` with a tiny path dispatch covers six endpoints;
upgrade to a micro-framework only if the API grows materially.

Probes: `livenessProbe` → `GET /health`; `readinessProbe` → `GET /ready`. A
readiness flip on MQTT disconnect keeps the pod from being treated as healthy
while disconnected.

## Deployment (Kubernetes)

Runs as a `Deployment` (single replica — it holds debounce buffers and a state
file; multiple replicas would double-publish) in the **`home-assistant`**
namespace.

Manifests (`deploy/` or `k8s/`):
- **Deployment** — the container, env from ConfigMap + Secret, probes, a
  `PersistentVolumeClaim` (or hostPath, per cluster norms) mounted for the
  state file so seen-state survives restarts, `strategy: Recreate` (single
  writer).
- **ConfigMap** — non-secret config (prefixes, allowlist, sensor-map, locations,
  debounce, expire defaults).
- **Secret** — broker credentials, API bearer token.
- **Service** (ClusterIP) — exposes the HTTP API port.
- **Ingress** — publishes the API; mutating endpoints protected by the bearer
  token (TLS per cluster norms).

Image: a minimal Python base (e.g. `python:3.12-slim`), `paho-mqtt` installed,
non-root user. Build/versioning per existing cluster conventions; confirm the
current stable Python base image at build time.

`ponytail:` start at one replica; no HA/leader-election machinery until a real
need exists. Version selection (Python base image, paho-mqtt) confirmed against
current stable at implementation time, not assumed here.

## Documentation

- **Local `README.md`** — dev cycle: venv setup, run locally against a broker,
  run the self-check, build the image, deploy to the cluster, and use the API
  (forget/list).
- **mixi-docs page** — operational doc in the documentation repo. Call
  `get_conventions()` first and follow it (lint + strict-build gate). Cover what
  the service does, the allowlist rename-to-opt-in workflow, the forget API, and
  troubleshooting (entity stuck, stale value, dev node leaked).

## Reuse / archive / delete from existing repo

- **Reuse:** `Configuration` class (env + CLI), MQTT connect skeleton,
  `templates/climate-monitor.yaml` as a field-shape reference, the
  resource→entity table from `tower-advertise.md`.
- **Archive (do not delete):** merge the legacy `doc/` directory into `docs/` and
  move the old design notes (`climate-module-discovery.md`, `tower-advertise.md`)
  to **`docs/archive/`**. They record prior thinking (incl. the superseded packed
  caps protocol) and stay for reference.
- **Delete (dead code only):** broken single-topic `advertise_devices` publish;
  the `node/+/homeassistant/...` forward/rewrite path; dead Flask `/health`;
  gateway node-list query.
- **Dependencies:** `paho-mqtt` only. Drop `jinja2` and `flask` — no templates
  (discovery built in code from the sensor map) and the HTTP API uses stdlib
  `http.server`.

## HA compatibility notes (verified June 2026)

- Per-component discovery topic `<prefix>/<component>/[<node_id>/]<object_id>/config`
  is current and supported.
- Device grouping by shared `device.identifiers` is the documented mechanism.
- `unique_id` is required for grouped/editable entities.
- `origin` recommended for per-component (required only for device-based); we
  include it.
- Removal via empty payload; device removed when unreferenced.
- `expire_after` → entity becomes `unavailable` after N seconds without an update.
- Deprecated `object_id` payload field (removed 2026.4) → `default_entity_id`; we
  avoid the field entirely.
- `color_mode`/`brightness` discovery keys removed (2025.3) — relevant to the
  future actuator layer only.

## Verify-on-wire (must confirm against the real broker)

1. Gateway publishes sensor values as **raw numeric payloads** (so `state_topic`
   works with no `value_template`). If values are JSON-wrapped, add a
   `value_template` per sensor type.
2. Gateway sensor **state** topics are **not retained** (retained state + 
   `expire_after` replays an expired value on HA restart). We do not control
   gateway retain; note behaviour and document.
3. Exact topic segmentation for each real sensor (alias-vs-resource boundary).

## Testing

One `assert`-based self-check (`__main__` or `test_*.py`, stdlib only): feed a
list of representative observed topics (stock climate, WCC multi-bus thermometers,
led-pwm humidity, a gateway-default `role:id` alias that must be filtered out)
through the pure `topics → discovery messages` function and assert:
- correct topic, `device_class`, `unit`, `expire_after`, `unique_id`;
- all entities of one alias share `device.identifiers` (one device);
- non-allowlisted aliases produce nothing;
- generated names match the convention.

## Future extension: actuators

When HA-compatible actuator firmware exists, custom nodes publish a small
purpose-built actuator-layout message; the service grows a thin per-firmware
adapter that maps it to HA `light`/`fan`/etc. discovery, reusing the same
device-grouping, naming, allowlist, and retained-lifecycle machinery defined
here. No change to the sensor path.
