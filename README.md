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

### Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Run self-check (no broker needed)

```bash
.venv/bin/python src/test_discovery.py
```

Expected: `All N tests passed.`

### Run locally against a broker

```bash
MQTT_BROKER=<your-broker> DEBUG=true .venv/bin/python src/ha-tower-discovery.py
```

The service connects, adopts existing retained configs (~1 s quiescence), then
listens on `node/+/#`. Allowlisted nodes with known sensor types appear in HA
after the debounce window (default 120 s). Use `--debounce 5` for faster
local testing.

### Build and push the image

Build and push (never use `latest` — tag with git SHA):

```bash
TAG=$(git rev-parse --short HEAD)
docker build -t mifs01.intranet:5001/home/tower-ha-discovery:${TAG} .
docker push mifs01.intranet:5001/home/tower-ha-discovery:${TAG}
# Then update the image tag in kubernetes/deployment.yaml and kubectl apply
```

### Provision the secret (once)

```bash
./scripts/create-secret.sh
```

Store the printed `API_TOKEN` in Bitwarden.

### Deploy to the cluster

```bash
kubectl apply -f kubernetes/
```

Verify:

```bash
kubectl -n home-assistant rollout status deploy/tower-ha-discovery
kubectl -n home-assistant logs -f deploy/tower-ha-discovery
```

## HTTP API

The service exposes a small HTTP API for operations and Kubernetes probes.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/health` | none | Liveness: 200 if process is serving |
| `GET` | `/ready` | none | Readiness: 200 if MQTT connected, 503 otherwise |
| `GET` | `/devices` | none | List discovered nodes and their entities (JSON) |
| `DELETE` | `/devices/{alias}` | Bearer | Remove a node: clear retained configs, drop from state |
| `DELETE` | `/devices/{alias}/entities/{object_id}` | Bearer | Remove a single entity |

Responses: `/health` and `/ready` return an empty body with the status code.
`/devices` returns `{"devices": [{"alias": "...", "entities": [{...}]}]}`.
Mutating endpoints return 204 on success, 401 on missing/wrong token, 404 on unknown alias/entity.

Mutating endpoints require `Authorization: Bearer <API_TOKEN>`.

### Examples

```bash
# List all discovered nodes
curl http://tower-discovery.mixi.cz/devices

# Remove a node (e.g. decommissioned)
curl -X DELETE \
  -H "Authorization: Bearer $API_TOKEN" \
  http://tower-discovery.mixi.cz/devices/climate-monitor%3Ahall%3A0

# Remove a single entity
curl -X DELETE \
  -H "Authorization: Bearer $API_TOKEN" \
  "http://tower-discovery.mixi.cz/devices/climate-monitor%3Ahall%3A0/entities/climate-monitor_hall_0__barometer_0_0_altitude"
```

URL-encode colons in alias (`:`→`%3A`).

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
