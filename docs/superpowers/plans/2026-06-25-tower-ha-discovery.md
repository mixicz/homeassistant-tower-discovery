# Tower → HA Sensor Discovery — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the dead-code service in `src/ha-tower-discovery.py` into a working passive-observation discovery bridge that makes HARDWARIO Tower sensors auto-appear in Home Assistant via MQTT.

**Architecture:** Single Python process: pure topic-parsing functions in `src/discovery.py`, service orchestration (MQTT lifecycle, debounce, HTTP API) in `src/ha-tower-discovery.py`. MQTT runs on a paho background thread via `loop_start()`; the main thread serves HTTP and drives the periodic debounce tick. Seen-state is in-memory, recovered at startup by adopting retained broker configs.

**Tech Stack:** Python 3 (stdlib-heavy), `paho-mqtt` (only external dep), stdlib `http.server`, stdlib `json`, stdlib `threading`.

## Global Constraints

- Only external dependency: `paho-mqtt`. No Flask, no Jinja2, no PyYAML.
- HTTP server: stdlib `http.server` only — no micro-framework.
- Config file: JSON (stdlib `json`) — no YAML.
- Python base image and paho-mqtt version: **look up current stable at build time**, never copy from this doc.
- Tests: `assert`-based, stdlib only — no pytest, no fixtures.
- Five-segment telemetry rule: a message is telemetry iff `topic.split('/') == 5` AND `parts[0] == 'node'`. Never use regex gymnastics; segment count is the discriminator.
- Discovery form: per-component (one retained message per entity), NOT the bundled `components` form.
- `unique_id` = `object_id` = `sanitize(alias) + "__" + resource + "_" + sanitize(address) + "_" + quantity`, where sanitize replaces `[^a-zA-Z0-9_-]` with `_`.
- Do NOT emit `object_id` payload field (removed HA 2026.4).
- Namespace: `home-assistant`.
- Deployment strategy: `Recreate` (single replica only).
- Allowlist default: `^[^:]+:[^:]+:[0-9]+$` (three-part `role:location:id`).
- Image registry: `mifs01.intranet:5001` (private registry — no auth required on intranet).
- Image name: `mifs01.intranet:5001/home/tower-ha-discovery:<tag>`. **Never use `latest`**; tag with the git commit SHA (`git rev-parse --short HEAD`).
- Kubernetes manifests directory: `kubernetes/` (not `k8s/`).
- Secrets: **never commit secret values to git**. Use `scripts/create-secret.sh` instead.

---

## File Map

| Path | Action | Purpose |
|------|--------|---------|
| `src/discovery.py` | **Create** | Pure functions: `parse_topic`, `sanitize_object_id`, `build_object_id`, `sensor_meta`, `build_device_name`, `build_entity_name`, `build_discovery_payload`; constants: `SENSOR_MAP`, `DEFAULT_EXPIRE_AFTER`, `QUANTITY_LABELS` |
| `src/ha-tower-discovery.py` | **Rewrite** | Service: `Configuration`, `TowerDiscoveryService`, `make_handler`, `main()` |
| `src/test_discovery.py` | **Create** | Assert-based self-check; run with `python src/test_discovery.py` |
| `requirements.txt` | **Create** | `paho-mqtt` (pin exact version looked up at build time) |
| `Dockerfile` | **Create** | Minimal Python slim, non-root user, `paho-mqtt` |
| `kubernetes/configmap.yaml` | **Create** | Non-secret config + mounted JSON config file |
| `kubernetes/deployment.yaml` | **Create** | Deployment (Recreate, probes, env from ConfigMap+Secret) |
| `kubernetes/service.yaml` | **Create** | ClusterIP for HTTP API port |
| `kubernetes/ingress.yaml` | **Create** | Traefik ingress for the HTTP API |
| `scripts/create-secret.sh` | **Create** | One-time secret provisioning script (not committed to git — add to `.gitignore`) |
| `README.md` | **Update** | Fill in dev cycle section (venv, local run, self-check, build, deploy, API) |

---

## Task 1: Scaffold & cleanup

**Files:**
- Create: `requirements.txt`
- Create: `src/discovery.py` (stubs only)
- Rewrite: `src/ha-tower-discovery.py` (clear dead code, leave `main()` stub)

**Interfaces:**
- Produces: empty `src/discovery.py` with placeholder `pass` bodies for all functions Task 2 will fill in; `src/ha-tower-discovery.py` reduced to a runnable stub.

- [ ] **Step 1: Create `requirements.txt`**

Look up the current stable paho-mqtt version:
```
pip index versions paho-mqtt
```
Take the highest stable version (e.g. `2.1.0`) and write:
```
paho-mqtt==<current-stable>
```

- [ ] **Step 2: Create `src/discovery.py` with stubs**

```python
import re

SENSOR_MAP = {}
DEFAULT_EXPIRE_AFTER = 7200
QUANTITY_LABELS = {}


def parse_topic(topic: str) -> dict | None:
    pass


def sanitize_object_id(s: str) -> str:
    pass


def build_object_id(alias: str, resource: str, address: str, quantity: str) -> str:
    pass


def sensor_meta(resource: str, quantity: str, overrides: dict | None = None) -> dict | None:
    pass


def build_device_name(alias: str, location_labels: dict | None = None,
                      name_overrides: dict | None = None) -> str:
    pass


def build_entity_name(resource: str, quantity: str, address: str,
                      sibling_count: int = 1,
                      name_overrides: dict | None = None) -> str:
    pass


def build_discovery_payload(
    parsed: dict,
    meta: dict,
    device_name: str,
    entity_name: str,
) -> tuple[str, str, dict]:
    """Returns (object_id, discovery_topic, payload_dict)."""
    pass
```

- [ ] **Step 3: Rewrite `src/ha-tower-discovery.py` to a clean stub**

```python
#!/usr/bin/env python3
"""Tower → Home Assistant passive sensor discovery service."""

import sys


def main():
    print('Tower HA Discovery — not yet implemented', file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt src/discovery.py src/ha-tower-discovery.py
git commit -m "chore: scaffold new service; clear dead code"
```

---

## Task 2: Pure functions & test (TDD)

**Files:**
- Create: `src/test_discovery.py`
- Modify: `src/discovery.py` (implement all functions)

**Interfaces:**
- Consumes: nothing from prior tasks except the stub file shapes.
- Produces:
  - `parse_topic(topic: str) -> dict | None` — `{"alias", "resource", "address", "quantity"}` or `None`
  - `sanitize_object_id(s: str) -> str`
  - `build_object_id(alias, resource, address, quantity) -> str`
  - `sensor_meta(resource, quantity, overrides=None) -> dict | None` — `{"device_class", "unit", "expire_after"}` or `None`
  - `build_device_name(alias, location_labels=None, name_overrides=None) -> str`
  - `build_entity_name(resource, quantity, address, sibling_count=1, name_overrides=None) -> str`
  - `build_discovery_payload(parsed, meta, device_name, entity_name) -> (object_id, disc_topic, payload_dict)`

### Step 1 — Write the failing tests

- [ ] **Step 1: Create `src/test_discovery.py`**

```python
"""Assert-based self-check for src/discovery.py. Run: python src/test_discovery.py"""
import re
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from discovery import (
    parse_topic, sanitize_object_id, build_object_id,
    sensor_meta, build_device_name, build_entity_name, build_discovery_payload,
)

DEFAULT_ALLOWLIST = r'^[^:]+:[^:]+:[0-9]+$'


def _pipeline(topic, location_labels=None, name_overrides=None,
              sibling_count=1, allowlist=DEFAULT_ALLOWLIST):
    """Simulate the observe→filter→lookup→build pipeline. Returns (oid, disc_topic, payload) or None."""
    parsed = parse_topic(topic)
    if parsed is None:
        return None
    if not re.match(allowlist, parsed['alias']):
        return None
    meta = sensor_meta(parsed['resource'], parsed['quantity'])
    if meta is None:
        return None
    device_name = build_device_name(parsed['alias'], location_labels, name_overrides)
    entity_name = build_entity_name(parsed['resource'], parsed['quantity'],
                                    parsed['address'], sibling_count, name_overrides)
    return build_discovery_payload(parsed, meta, device_name, entity_name)


# --- parse_topic ---

def test_parse_topic_valid():
    r = parse_topic('node/climate-monitor:hall:0/thermometer/0:0/temperature')
    assert r == {'alias': 'climate-monitor:hall:0', 'resource': 'thermometer',
                 'address': '0:0', 'quantity': 'temperature'}, r


def test_parse_topic_command_ignored():
    # 6 segments — command topic, must return None
    assert parse_topic('node/led-pwm:schodiste:0/led-pwm/-/trigger/set') is None


def test_parse_topic_too_few_segments():
    assert parse_topic('node/alias:loc:0/thermometer/0:0') is None


def test_parse_topic_wrong_prefix():
    assert parse_topic('gateway/alias:loc:0/thermometer/0:0/temperature') is None


# --- sanitize_object_id / build_object_id ---

def test_sanitize_colons():
    assert sanitize_object_id('water-cooling-controller:rack:0') == 'water-cooling-controller_rack_0'


def test_sanitize_address():
    assert sanitize_object_id('1:3') == '1_3'


def test_build_object_id():
    oid = build_object_id('water-cooling-controller:rack:0', 'thermometer', '1:3', 'temperature')
    assert oid == 'water-cooling-controller_rack_0__thermometer_1_3_temperature', oid


# --- sensor_meta ---

def test_sensor_meta_temperature():
    m = sensor_meta('thermometer', 'temperature')
    assert m == {'device_class': 'temperature', 'unit': '°C', 'expire_after': 1500}, m


def test_sensor_meta_humidity():
    m = sensor_meta('hygrometer', 'relative-humidity')
    assert m == {'device_class': 'humidity', 'unit': '%', 'expire_after': 1500}, m


def test_sensor_meta_rpm_wildcard():
    m = sensor_meta('fan', 'rpm')
    assert m is not None
    assert m['unit'] == 'rpm'
    assert m['expire_after'] == 600
    assert m.get('device_class') is None, m


def test_sensor_meta_unknown():
    assert sensor_meta('led-pwm', 'trigger') is None


def test_sensor_meta_override():
    overrides = {('thermometer', 'temperature'): {'expire_after': 300}}
    m = sensor_meta('thermometer', 'temperature', overrides)
    assert m['expire_after'] == 300
    assert m['device_class'] == 'temperature'  # base value preserved


# --- build_device_name ---

def test_device_name_three_part():
    name = build_device_name('climate-monitor:hall:0', {'hall': 'Hall'})
    assert name == 'Hall — Climate Monitor', repr(name)


def test_device_name_instance_zero_omitted():
    name = build_device_name('climate-monitor:hall:0', {'hall': 'Hall'})
    assert '0' not in name.split('—')[1]  # instance 0 not appended


def test_device_name_nonzero_instance():
    name = build_device_name('motion-detector:schodiste:1')
    # instance 1 should appear
    assert '1' in name


def test_device_name_title_case_fallback():
    # no location_labels map → title-case of raw token
    name = build_device_name('climate-monitor:hall:0')
    assert 'Hall' in name, repr(name)


def test_device_name_alias_override():
    name = build_device_name('climate-monitor:hall:0',
                              name_overrides={'climate-monitor:hall:0': 'My Device'})
    assert name == 'My Device'


# --- build_entity_name ---

def test_entity_name_temperature():
    name = build_entity_name('thermometer', 'temperature', '0:0')
    assert name == 'Temperature', repr(name)


def test_entity_name_humidity():
    name = build_entity_name('hygrometer', 'relative-humidity', '0:2')
    assert name == 'Humidity', repr(name)


def test_entity_name_sibling_includes_address():
    name = build_entity_name('thermometer', 'temperature', '1:3', sibling_count=2)
    assert '1:3' in name, repr(name)


def test_entity_name_single_no_address():
    name = build_entity_name('thermometer', 'temperature', '0:0', sibling_count=1)
    assert '0:0' not in name, repr(name)


# --- full pipeline ---

def test_pipeline_temperature():
    r = _pipeline('node/climate-monitor:hall:0/thermometer/0:0/temperature',
                  location_labels={'hall': 'Hall'})
    assert r is not None
    oid, disc_topic, payload = r
    assert disc_topic == f'homeassistant/sensor/{oid}/config'
    assert payload['device_class'] == 'temperature'
    assert payload['unit_of_measurement'] == '°C'
    assert payload['expire_after'] == 1500
    assert payload['unique_id'] == oid
    assert payload['device']['name'] == 'Hall — Climate Monitor'
    assert payload['name'] == 'Temperature'


def test_pipeline_gateway_default_alias_filtered():
    # two-part alias — rejected by default allowlist
    assert _pipeline('node/climate-monitor:0/thermometer/0:0/temperature') is None


def test_pipeline_command_ignored():
    assert _pipeline('node/led-pwm:schodiste:0/led-pwm/-/trigger/set') is None


def test_pipeline_led_pwm_node_has_humidity():
    r = _pipeline('node/led-pwm:schodiste:0/hygrometer/0:2/relative-humidity')
    assert r is not None
    _, _, payload = r
    assert payload['device_class'] == 'humidity'


def test_pipeline_multi_bus_share_device():
    r1 = _pipeline('node/water-cooling-controller:rack:0/thermometer/1:3/temperature')
    r2 = _pipeline('node/water-cooling-controller:rack:0/thermometer/0:0/temperature')
    assert r1 is not None and r2 is not None
    _, _, p1 = r1
    _, _, p2 = r2
    assert p1['device']['identifiers'] == ['water-cooling-controller:rack:0']
    assert p1['device']['identifiers'] == p2['device']['identifiers']


def test_pipeline_rpm():
    r = _pipeline('node/water-cooling-controller:rack:0/fan/0/rpm')
    assert r is not None
    _, _, payload = r
    assert 'device_class' not in payload
    assert payload['unit_of_measurement'] == 'rpm'
    assert payload['expire_after'] == 600


def test_pipeline_state_topic():
    r = _pipeline('node/climate-monitor:hall:0/thermometer/0:0/temperature')
    assert r is not None
    _, _, payload = r
    assert payload['state_topic'] == 'node/climate-monitor:hall:0/thermometer/0:0/temperature'


def test_pipeline_origin():
    r = _pipeline('node/climate-monitor:hall:0/thermometer/0:0/temperature')
    assert r is not None
    _, _, payload = r
    assert payload['origin']['name'] == 'tower-ha-discovery'


def test_pipeline_no_deprecated_object_id_field():
    r = _pipeline('node/climate-monitor:hall:0/thermometer/0:0/temperature')
    assert r is not None
    _, _, payload = r
    assert 'object_id' not in payload  # HA 2026.4 removed this field


TESTS = [
    test_parse_topic_valid, test_parse_topic_command_ignored,
    test_parse_topic_too_few_segments, test_parse_topic_wrong_prefix,
    test_sanitize_colons, test_sanitize_address, test_build_object_id,
    test_sensor_meta_temperature, test_sensor_meta_humidity,
    test_sensor_meta_rpm_wildcard, test_sensor_meta_unknown, test_sensor_meta_override,
    test_device_name_three_part, test_device_name_instance_zero_omitted,
    test_device_name_nonzero_instance, test_device_name_title_case_fallback,
    test_device_name_alias_override,
    test_entity_name_temperature, test_entity_name_humidity,
    test_entity_name_sibling_includes_address, test_entity_name_single_no_address,
    test_pipeline_temperature, test_pipeline_gateway_default_alias_filtered,
    test_pipeline_command_ignored, test_pipeline_led_pwm_node_has_humidity,
    test_pipeline_multi_bus_share_device, test_pipeline_rpm,
    test_pipeline_state_topic, test_pipeline_origin,
    test_pipeline_no_deprecated_object_id_field,
]

if __name__ == '__main__':
    failed = []
    for t in TESTS:
        try:
            t()
        except Exception as e:
            failed.append(f'  FAIL {t.__name__}: {e}')
    if failed:
        print('\n'.join(failed))
        sys.exit(1)
    print(f'All {len(TESTS)} tests passed.')
```

- [ ] **Step 2: Run tests — confirm they all fail**

```bash
python src/test_discovery.py
```
Expected: multiple FAIL lines (functions return `None`/`pass`). Exit code 1.

### Step 3 — Implement `src/discovery.py`

- [ ] **Step 3: Implement `src/discovery.py` — full implementation**

```python
import re

# Sensor map: (resource, quantity) -> {device_class, unit, expire_after}
# device_class=None means no device_class key is emitted.
SENSOR_MAP = {
    ('thermometer', 'temperature'):      {'device_class': 'temperature',                     'unit': '°C',  'expire_after': 1500},
    ('hygrometer', 'relative-humidity'): {'device_class': 'humidity',                        'unit': '%',   'expire_after': 1500},
    ('lux-meter', 'illuminance'):        {'device_class': 'illuminance',                     'unit': 'lx',  'expire_after': 1500},
    ('barometer', 'pressure'):           {'device_class': 'atmospheric_pressure',            'unit': 'hPa', 'expire_after': 1500},
    ('barometer', 'altitude'):           {'device_class': 'distance',                        'unit': 'm',   'expire_after': 7200},
    ('voc-sensor', 'tvoc'):              {'device_class': 'volatile_organic_compounds_parts', 'unit': 'ppb', 'expire_after': 1500},
    ('voc-lp-sensor', 'tvoc'):           {'device_class': 'volatile_organic_compounds_parts', 'unit': 'ppb', 'expire_after': 1500},
    ('battery', 'voltage'):              {'device_class': 'voltage',                         'unit': 'V',   'expire_after': 7200},
}

_RPM_META = {'device_class': None, 'unit': 'rpm', 'expire_after': 600}

DEFAULT_EXPIRE_AFTER = 7200

QUANTITY_LABELS = {
    'temperature': 'Temperature',
    'relative-humidity': 'Humidity',
    'illuminance': 'Illuminance',
    'pressure': 'Pressure',
    'altitude': 'Altitude',
    'tvoc': 'TVOC',
    'voltage': 'Battery Voltage',
    'rpm': 'Fan Speed',
}


def parse_topic(topic: str) -> dict | None:
    """Return parsed telemetry fields, or None for commands/invalid topics."""
    parts = topic.split('/')
    if len(parts) != 5 or parts[0] != 'node':
        return None
    return {'alias': parts[1], 'resource': parts[2], 'address': parts[3], 'quantity': parts[4]}


def sanitize_object_id(s: str) -> str:
    """Replace chars outside [a-zA-Z0-9_-] with underscores."""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', s)


def build_object_id(alias: str, resource: str, address: str, quantity: str) -> str:
    return sanitize_object_id(f'{alias}__{resource}_{address}_{quantity}')


def sensor_meta(resource: str, quantity: str, overrides: dict | None = None) -> dict | None:
    """Look up sensor metadata. Returns a copy with overrides applied, or None if unknown."""
    base = SENSOR_MAP.get((resource, quantity)) or (_RPM_META if quantity == 'rpm' else None)
    if base is None:
        return None
    result = dict(base)
    if overrides:
        result.update(overrides.get((resource, quantity), {}))
    return result


def build_device_name(alias: str, location_labels: dict | None = None,
                      name_overrides: dict | None = None) -> str:
    """Build human-readable device name from alias. Format: '{Location} — {Role}'."""
    if name_overrides and alias in name_overrides:
        return name_overrides[alias]
    parts = alias.split(':')
    role = parts[0].replace('-', ' ').title()
    location_raw = parts[1] if len(parts) > 1 else ''
    instance = parts[2] if len(parts) > 2 else '0'
    location = (location_labels or {}).get(location_raw, location_raw.title())
    suffix = f' {instance}' if instance not in ('0', '') else ''
    return f'{location} — {role}{suffix}'


def build_entity_name(resource: str, quantity: str, address: str,
                      sibling_count: int = 1,
                      name_overrides: dict | None = None) -> str:
    """Return entity label; appends address if sibling_count > 1."""
    if name_overrides and (resource, quantity, address) in name_overrides:
        return name_overrides[(resource, quantity, address)]
    label = QUANTITY_LABELS.get(quantity, quantity.replace('-', ' ').title())
    if sibling_count > 1:
        label = f'{label} {address}'
    return label


def build_discovery_payload(
    parsed: dict,
    meta: dict,
    device_name: str,
    entity_name: str,
) -> tuple[str, str, dict]:
    """Build HA MQTT discovery payload. Returns (object_id, discovery_topic, payload_dict)."""
    alias = parsed['alias']
    resource = parsed['resource']
    address = parsed['address']
    quantity = parsed['quantity']

    object_id = build_object_id(alias, resource, address, quantity)
    state_topic = f'node/{alias}/{resource}/{address}/{quantity}'
    discovery_topic = f'homeassistant/sensor/{object_id}/config'

    payload: dict = {
        'name': entity_name,
        'unique_id': object_id,
        'state_topic': state_topic,
        'expire_after': meta['expire_after'],
        'device': {
            'identifiers': [alias],
            'name': device_name,
            'model': alias.split(':')[0],
            'manufacturer': 'HARDWARIO',
        },
        'origin': {'name': 'tower-ha-discovery'},
    }
    if meta.get('device_class') is not None:
        payload['device_class'] = meta['device_class']
    if meta.get('unit'):
        payload['unit_of_measurement'] = meta['unit']

    return object_id, discovery_topic, payload
```

- [ ] **Step 4: Run tests — confirm all pass**

```bash
python src/test_discovery.py
```
Expected: `All 30 tests passed.`

- [ ] **Step 5: Commit**

```bash
git add src/discovery.py src/test_discovery.py
git commit -m "feat: pure discovery functions with full test coverage"
```

---

## Task 3: Configuration class

**Files:**
- Modify: `src/ha-tower-discovery.py` (add `Configuration` class)

**Interfaces:**
- Produces: `Configuration` instance with all config attributes set, loadable via `cfg = Configuration(); cfg.load()`.
- Key attributes: `mqtt_broker`, `mqtt_port`, `mqtt_user`, `mqtt_password`, `node_prefix`, `discovery_prefix`, `http_bind`, `http_port`, `api_token`, `debounce_seconds`, `adopt_quiescence`, `adopt_timeout`, `default_expire_after`, `allowlist` (list of regex strings), `location_labels` (dict), `name_overrides` (dict), `sensor_map_overrides` (dict), `debug`.

- [ ] **Step 1: Write `Configuration` class in `src/ha-tower-discovery.py`**

```python
#!/usr/bin/env python3
"""Tower → Home Assistant passive sensor discovery service."""

import argparse
import json
import os
import sys


class Configuration:
    def __init__(self):
        # MQTT
        self.mqtt_broker = 'localhost'
        self.mqtt_port = 1883
        self.mqtt_user = ''
        self.mqtt_password = ''
        # Topics
        self.node_prefix = 'node'
        self.discovery_prefix = 'homeassistant'
        # HTTP API
        self.http_bind = '0.0.0.0'
        self.http_port = 8080
        self.api_token = ''
        # Timing
        self.debounce_seconds = 120.0
        self.adopt_quiescence = 1.0
        self.adopt_timeout = 10.0
        self.default_expire_after = 7200
        # From config file / defaults
        self.allowlist = [r'^[^:]+:[^:]+:[0-9]+$']
        self.location_labels: dict = {}
        self.name_overrides: dict = {}
        self.sensor_map_overrides: dict = {}
        self.debug = False
        self.config_file = ''

    def load(self):
        self._from_env()
        self._from_args()
        if self.config_file:
            self._from_file(self.config_file)

    def _from_env(self):
        e = os.environ.get
        self.mqtt_broker   = e('MQTT_BROKER', self.mqtt_broker)
        self.mqtt_port     = int(e('MQTT_PORT', self.mqtt_port))
        self.mqtt_user     = e('MQTT_USER', self.mqtt_user)
        self.mqtt_password = e('MQTT_PASSWORD', self.mqtt_password)
        self.node_prefix      = e('NODE_PREFIX', self.node_prefix)
        self.discovery_prefix = e('DISCOVERY_PREFIX', self.discovery_prefix)
        self.http_bind = e('HTTP_BIND', self.http_bind)
        self.http_port = int(e('HTTP_PORT', self.http_port))
        self.api_token = e('API_TOKEN', self.api_token)
        self.debounce_seconds  = float(e('DEBOUNCE_SECONDS', self.debounce_seconds))
        self.adopt_quiescence  = float(e('ADOPT_QUIESCENCE', self.adopt_quiescence))
        self.adopt_timeout     = float(e('ADOPT_TIMEOUT', self.adopt_timeout))
        self.default_expire_after = int(e('DEFAULT_EXPIRE_AFTER', self.default_expire_after))
        self.config_file = e('CONFIG_FILE', self.config_file)
        self.debug = e('DEBUG', '').lower() in ('1', 'true', 'yes')

    def _from_args(self):
        p = argparse.ArgumentParser(description='Tower → HA discovery service')
        p.add_argument('--broker')
        p.add_argument('--port', type=int)
        p.add_argument('--user')
        p.add_argument('--password')
        p.add_argument('--http-port', type=int)
        p.add_argument('--debounce', type=float)
        p.add_argument('--config-file')
        p.add_argument('--debug', action='store_true')
        args = p.parse_args()
        if args.broker:       self.mqtt_broker = args.broker
        if args.port:         self.mqtt_port = args.port
        if args.user:         self.mqtt_user = args.user
        if args.password:     self.mqtt_password = args.password
        if args.http_port:    self.http_port = args.http_port
        if args.debounce:     self.debounce_seconds = args.debounce
        if args.config_file:  self.config_file = args.config_file
        if args.debug:        self.debug = True

    def _from_file(self, path: str):
        with open(path) as f:
            data = json.load(f)
        if 'allowlist' in data:
            self.allowlist = data['allowlist']
        if 'location_labels' in data:
            self.location_labels = data['location_labels']
        if 'name_overrides' in data:
            self.name_overrides = data['name_overrides']
        if 'sensor_map_overrides' in data:
            # Keys are "resource/quantity" strings; convert to tuple keys
            self.sensor_map_overrides = {
                tuple(k.split('/', 1)): v
                for k, v in data['sensor_map_overrides'].items()
            }


def main():
    cfg = Configuration()
    cfg.load()
    print(f'Config loaded: broker={cfg.mqtt_broker}:{cfg.mqtt_port}, debug={cfg.debug}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Verify config loads without error**

```bash
python src/ha-tower-discovery.py
```
Expected: `Config loaded: broker=localhost:1883, debug=False`

- [ ] **Step 3: Commit**

```bash
git add src/ha-tower-discovery.py
git commit -m "feat: Configuration class with env, CLI, and JSON file support"
```

---

## Task 4: MQTT lifecycle (connect → adopt → reconcile → go live)

**Files:**
- Modify: `src/ha-tower-discovery.py` (add `TowerDiscoveryService` with startup phases)

**Interfaces:**
- Consumes: `Configuration` (Task 3), `parse_topic`, `sanitize_object_id` (Task 2 — imported from `discovery`)
- Produces:
  - `TowerDiscoveryService(config)` class
  - `service.run()` — blocks; completes adopt+reconcile, then enters live observation
  - `service.mqtt_connected: bool` — True when MQTT connection is up
  - `service._seen_state: dict` — `{object_id: {hash, alias, resource, quantity, address}}`
  - `service._allowlist_match(alias) -> bool`
  - `service.client` — paho MQTT client

Seen-state schema:
```python
# _seen_state[object_id] = {
#   'hash':     str,      # md5hex of last published JSON payload
#   'alias':    str,
#   'resource': str,
#   'quantity': str,
#   'address':  str,
# }
```

- [ ] **Step 1: Add import block and `TowerDiscoveryService` skeleton to `src/ha-tower-discovery.py`**

Add these imports at the top (after the existing imports):
```python
import hashlib
import json
import re
import threading
import time

import paho.mqtt.client as mqtt

from discovery import (
    parse_topic, sanitize_object_id, build_object_id,
    sensor_meta, build_device_name, build_entity_name, build_discovery_payload,
)
```

- [ ] **Step 2: Implement `TowerDiscoveryService` with lifecycle methods**

Add the full class to `src/ha-tower-discovery.py` (before `main()`):

```python
class TowerDiscoveryService:
    def __init__(self, config: Configuration):
        self.config = config
        self._lock = threading.Lock()
        self._seen_state: dict = {}           # object_id -> {hash, alias, resource, quantity, address}
        self._debounce_buffer: dict = {}      # alias -> {started_at, topics: [parsed_topic, ...]}
        self.mqtt_connected = False
        self._adopting = False
        self._adopt_last_msg = 0.0
        self._adopt_start = 0.0

        self.client = mqtt.Client()
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message    = self._on_message
        if config.mqtt_user:
            self.client.username_pw_set(config.mqtt_user, config.mqtt_password)

    # ------------------------------------------------------------------ allowlist

    def _allowlist_match(self, alias: str) -> bool:
        return any(re.match(pat, alias) for pat in self.config.allowlist)

    # ------------------------------------------------------------------ MQTT callbacks

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.mqtt_connected = True
            if self.config.debug:
                print('MQTT connected')
        else:
            print(f'MQTT connect failed: rc={rc}', file=__import__('sys').stderr)

    def _on_disconnect(self, client, userdata, rc):
        self.mqtt_connected = False
        if self.config.debug:
            print(f'MQTT disconnected: rc={rc}')

    def _on_message(self, client, userdata, msg):
        if self._adopting:
            self._handle_adopt_message(msg)
            return
        self._handle_live_message(msg)

    def _handle_adopt_message(self, msg):
        self._adopt_last_msg = time.monotonic()
        if not msg.payload:
            return  # empty = already cleared, skip
        try:
            payload = json.loads(msg.payload)
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        if payload.get('origin', {}).get('name') != 'tower-ha-discovery':
            return
        # Extract object_id from topic: homeassistant/sensor/{object_id}/config
        parts = msg.topic.split('/')
        if len(parts) != 4:
            return
        object_id = parts[2]
        payload_hash = hashlib.md5(msg.payload).hexdigest()
        # Reconstruct resource/quantity/address from state_topic
        state_topic = payload.get('state_topic', '')
        parsed = parse_topic(state_topic)
        alias = payload.get('device', {}).get('identifiers', [''])[0]
        with self._lock:
            self._seen_state[object_id] = {
                'hash': payload_hash,
                'alias': alias,
                'resource': parsed['resource'] if parsed else '',
                'quantity': parsed['quantity'] if parsed else '',
                'address':  parsed['address']  if parsed else '',
            }

    def _handle_live_message(self, msg):
        pass  # implemented in Task 5

    # ------------------------------------------------------------------ startup phases

    def _wait_for_connect(self, timeout: float = 30.0):
        start = time.monotonic()
        while not self.mqtt_connected:
            if time.monotonic() - start > timeout:
                raise RuntimeError('MQTT connect timeout')
            time.sleep(0.1)

    def _adopt(self):
        disc_topic = f'{self.config.discovery_prefix}/sensor/+/config'
        self._adopting = True
        self._adopt_last_msg = time.monotonic()
        self._adopt_start = time.monotonic()
        self.client.subscribe(disc_topic)

        while True:
            idle    = time.monotonic() - self._adopt_last_msg
            elapsed = time.monotonic() - self._adopt_start
            if idle >= self.config.adopt_quiescence or elapsed >= self.config.adopt_timeout:
                break
            time.sleep(0.05)

        self._adopting = False
        self.client.unsubscribe(disc_topic)
        if self.config.debug:
            print(f'Adoption complete: {len(self._seen_state)} entities in seen-state')

    def _reconcile(self):
        with self._lock:
            to_clear = [
                oid for oid, entry in self._seen_state.items()
                if not self._allowlist_match(entry['alias'])
            ]
        for oid in to_clear:
            self.client.publish(
                f'{self.config.discovery_prefix}/sensor/{oid}/config',
                b'', retain=True,
            )
            with self._lock:
                self._seen_state.pop(oid, None)
        if self.config.debug and to_clear:
            print(f'Reconciled {len(to_clear)} entities no longer on allowlist')

    def _go_live(self):
        self.client.subscribe(f'{self.config.node_prefix}/+/#')
        if self.config.debug:
            print('Live observation started')

    # ------------------------------------------------------------------ main entry

    def run(self):
        self.client.connect(self.config.mqtt_broker, self.config.mqtt_port, keepalive=60)
        self.client.loop_start()
        self._wait_for_connect()
        self._adopt()
        self._reconcile()
        self._go_live()
        # HTTP server + tick loop added in Task 6; placeholder for now
        try:
            while True:
                time.sleep(1)
                self._tick()
        except KeyboardInterrupt:
            pass
        finally:
            self.client.loop_stop()

    def _tick(self):
        pass  # implemented in Task 5
```

Update `main()`:
```python
def main():
    cfg = Configuration()
    cfg.load()
    service = TowerDiscoveryService(cfg)
    service.run()
```

- [ ] **Step 3: Verify service connects and adopts (requires a local broker)**

If you have a broker available:
```bash
MQTT_BROKER=<your-broker> DEBUG=true python src/ha-tower-discovery.py
```
Expected output: `MQTT connected`, `Adoption complete: N entities in seen-state`, `Live observation started`.

If no broker available, verify syntax is error-free:
```bash
python -c "import src.ha_tower_discovery" 2>&1 || python -c "
import sys; sys.argv=['x']
exec(open('src/ha-tower-discovery.py').read().split('def main')[0])
print('Syntax OK')
"
```
Expected: no import errors.

- [ ] **Step 4: Commit**

```bash
git add src/ha-tower-discovery.py
git commit -m "feat: MQTT lifecycle — connect, adopt, reconcile, go live"
```

---

## Task 5: Live observation & debounce

**Files:**
- Modify: `src/ha-tower-discovery.py` — implement `_handle_live_message`, `_tick`, `_flush_node`, `_publish_entity_locked`, and public `forget_node` / `forget_entity`

**Interfaces:**
- Consumes: `TowerDiscoveryService` (Task 4); all pure functions from `discovery.py` (Task 2)
- Produces:
  - `service.forget_node(alias) -> bool`
  - `service.forget_entity(alias, object_id) -> bool`
  - `service.get_devices() -> dict` (for HTTP API in Task 6)

Debounce buffer schema:
```python
# _debounce_buffer[alias] = {
#   'started_at': float,          # time.monotonic()
#   'topics': [parsed_topic, ...] # list of parsed_topic dicts (may have duplicates — dedup by resource+address+quantity)
# }
```

- [ ] **Step 1: Implement `_handle_live_message` in `TowerDiscoveryService`**

Replace the `pass` body of `_handle_live_message` with:

```python
def _handle_live_message(self, msg):
    parsed = parse_topic(msg.topic)
    if parsed is None:
        return
    alias = parsed['alias']
    if not self._allowlist_match(alias):
        if self.config.debug:
            print(f'Ignored (not allowlisted): {alias}')
        return
    meta = sensor_meta(parsed['resource'], parsed['quantity'],
                        self.config.sensor_map_overrides)
    if meta is None:
        if self.config.debug:
            print(f'Ignored (unknown sensor): {parsed["resource"]}/{parsed["quantity"]}')
        return

    with self._lock:
        is_new_node = (alias not in self._seen_state_aliases() and
                       alias not in self._debounce_buffer)
        if is_new_node:
            # Start debounce buffer for this alias
            self._debounce_buffer[alias] = {
                'started_at': time.monotonic(),
                'topics': [],
            }

        if alias in self._debounce_buffer:
            # Deduplicate by (resource, address, quantity)
            key = (parsed['resource'], parsed['address'], parsed['quantity'])
            existing_keys = {(t['resource'], t['address'], t['quantity'])
                             for t in self._debounce_buffer[alias]['topics']}
            if key not in existing_keys:
                self._debounce_buffer[alias]['topics'].append(parsed)
        else:
            # Node already established — publish immediately
            self._publish_immediately_locked(parsed, meta)

def _seen_state_aliases(self) -> set:
    """Return set of aliases in seen_state. Must be called with lock held."""
    return {e['alias'] for e in self._seen_state.values()}
```

- [ ] **Step 2: Implement `_tick` and `_flush_node`**

Replace the `pass` body of `_tick` and add `_flush_node`:

```python
def _tick(self):
    now = time.monotonic()
    to_flush = []
    with self._lock:
        for alias, buf in list(self._debounce_buffer.items()):
            if now - buf['started_at'] >= self.config.debounce_seconds:
                to_flush.append((alias, buf['topics']))
                del self._debounce_buffer[alias]
    for alias, topics in to_flush:
        self._flush_node(alias, topics)

def _flush_node(self, alias: str, topics: list):
    """Publish all buffered entities for a node, with correct sibling counts."""
    from collections import Counter
    counts = Counter((t['resource'], t['quantity']) for t in topics)
    with self._lock:
        for parsed in topics:
            meta = sensor_meta(parsed['resource'], parsed['quantity'],
                                self.config.sensor_map_overrides)
            if meta is None:
                continue
            sibling_count = counts[(parsed['resource'], parsed['quantity'])]
            device_name = build_device_name(parsed['alias'],
                                            self.config.location_labels,
                                            self.config.name_overrides)
            entity_name = build_entity_name(parsed['resource'], parsed['quantity'],
                                            parsed['address'], sibling_count,
                                            self.config.name_overrides)
            object_id, disc_topic, payload = build_discovery_payload(
                parsed, meta, device_name, entity_name)
            self._publish_entity_locked(object_id, disc_topic, payload, parsed)
```

- [ ] **Step 3: Implement `_publish_immediately_locked` and `_publish_entity_locked`**

```python
def _publish_immediately_locked(self, parsed: dict, meta: dict):
    """Publish a single entity for an already-established node. Lock must be held."""
    rq = (parsed['resource'], parsed['quantity'])
    sibling_count = sum(
        1 for e in self._seen_state.values()
        if e['alias'] == parsed['alias']
        and e['resource'] == parsed['resource']
        and e['quantity'] == parsed['quantity']
    ) + 1

    device_name = build_device_name(parsed['alias'],
                                    self.config.location_labels,
                                    self.config.name_overrides)
    entity_name = build_entity_name(parsed['resource'], parsed['quantity'],
                                    parsed['address'], sibling_count,
                                    self.config.name_overrides)
    object_id, disc_topic, payload = build_discovery_payload(
        parsed, meta, device_name, entity_name)
    self._publish_entity_locked(object_id, disc_topic, payload, parsed)


def _publish_entity_locked(self, object_id: str, disc_topic: str,
                            payload: dict, parsed: dict):
    """Publish a discovery config if content changed. Lock must be held."""
    body = json.dumps(payload, ensure_ascii=False).encode()
    new_hash = hashlib.md5(body).hexdigest()
    existing = self._seen_state.get(object_id)
    if existing and existing['hash'] == new_hash:
        return  # unchanged — skip
    self.client.publish(disc_topic, body, retain=True)
    self._seen_state[object_id] = {
        'hash': new_hash,
        'alias': parsed['alias'],
        'resource': parsed['resource'],
        'quantity': parsed['quantity'],
        'address': parsed['address'],
    }
    if self.config.debug:
        print(f'Published: {disc_topic}')
```

- [ ] **Step 4: Implement `get_devices`, `forget_node`, `forget_entity`**

```python
def get_devices(self) -> dict:
    with self._lock:
        by_alias: dict = {}
        for oid, entry in self._seen_state.items():
            alias = entry['alias']
            by_alias.setdefault(alias, []).append({
                'object_id': oid,
                'state_topic': (
                    f'{self.config.node_prefix}/{alias}/'
                    f'{entry["resource"]}/{entry["address"]}/{entry["quantity"]}'
                ),
            })
        return {'devices': [
            {'alias': alias, 'entities': entities}
            for alias, entities in sorted(by_alias.items())
        ]}


def forget_node(self, alias: str) -> bool:
    with self._lock:
        to_delete = [oid for oid, e in self._seen_state.items() if e['alias'] == alias]
        if not to_delete:
            return False
        for oid in to_delete:
            self.client.publish(
                f'{self.config.discovery_prefix}/sensor/{oid}/config',
                b'', retain=True,
            )
            del self._seen_state[oid]
        self._debounce_buffer.pop(alias, None)
        return True


def forget_entity(self, alias: str, object_id: str) -> bool:
    with self._lock:
        entry = self._seen_state.get(object_id)
        if not entry or entry['alias'] != alias:
            return False
        self.client.publish(
            f'{self.config.discovery_prefix}/sensor/{object_id}/config',
            b'', retain=True,
        )
        del self._seen_state[object_id]
        return True
```

- [ ] **Step 5: Run the self-check — still passes**

```bash
python src/test_discovery.py
```
Expected: `All 30 tests passed.`

- [ ] **Step 6: Commit**

```bash
git add src/ha-tower-discovery.py
git commit -m "feat: live observation, debounce, publish, forget"
```

---

## Task 6: HTTP API

**Files:**
- Modify: `src/ha-tower-discovery.py` — add `make_handler(service)` and integrate into `run()`

**Interfaces:**
- Consumes: `TowerDiscoveryService.get_devices()`, `forget_node()`, `forget_entity()`, `mqtt_connected`, `config.api_token` (Task 5)
- Produces: HTTP server on `config.http_bind:config.http_port`

| Endpoint | Auth | Response |
|----------|------|----------|
| `GET /health` | none | 200 always |
| `GET /ready` | none | 200 if MQTT up, 503 otherwise |
| `GET /devices` | none | 200 + JSON |
| `DELETE /devices/{alias}` | Bearer | 204 or 404 |
| `DELETE /devices/{alias}/entities/{object_id}` | Bearer | 204 or 404 |

- [ ] **Step 1: Add `make_handler` function to `src/ha-tower-discovery.py`**

Add before `main()`:

```python
import http.server
import urllib.parse


def make_handler(service: 'TowerDiscoveryService'):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if service.config.debug:
                super().log_message(fmt, *args)

        def _send(self, code: int, body: bytes = b'', content_type: str = 'application/json'):
            self.send_response(code)
            if body:
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
            else:
                self.send_header('Content-Length', '0')
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _auth_ok(self) -> bool:
            token = service.config.api_token
            if not token:
                return True
            return self.headers.get('Authorization', '') == f'Bearer {token}'

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == '/health':
                self._send(200)
            elif path == '/ready':
                self._send(200 if service.mqtt_connected else 503)
            elif path == '/devices':
                body = json.dumps(service.get_devices(), ensure_ascii=False).encode()
                self._send(200, body)
            else:
                self._send(404)

        def do_DELETE(self):
            if not self._auth_ok():
                self._send(401)
                return
            path = urllib.parse.urlparse(self.path).path

            # DELETE /devices/{alias}/entities/{object_id}
            m = re.fullmatch(r'/devices/([^/]+)/entities/([^/]+)', path)
            if m:
                alias     = urllib.parse.unquote(m.group(1))
                object_id = urllib.parse.unquote(m.group(2))
                self._send(204 if service.forget_entity(alias, object_id) else 404)
                return

            # DELETE /devices/{alias}
            m = re.fullmatch(r'/devices/([^/]+)', path)
            if m:
                alias = urllib.parse.unquote(m.group(1))
                self._send(204 if service.forget_node(alias) else 404)
                return

            self._send(404)

    return Handler
```

Note: `re` and `json` are already imported earlier in the file.

- [ ] **Step 2: Replace the placeholder `while True` in `run()` with the HTTP + tick loop**

Replace this block in `run()`:
```python
        # HTTP server + tick loop added in Task 6; placeholder for now
        try:
            while True:
                time.sleep(1)
                self._tick()
        except KeyboardInterrupt:
            pass
        finally:
            self.client.loop_stop()
```

With:
```python
        handler = make_handler(self)
        httpd = http.server.HTTPServer((self.config.http_bind, self.config.http_port), handler)
        httpd.socket.settimeout(1.0)  # so _tick() runs roughly every second
        if self.config.debug:
            print(f'HTTP API on {self.config.http_bind}:{self.config.http_port}')
        try:
            while True:
                httpd.handle_request()
                self._tick()
        except KeyboardInterrupt:
            pass
        finally:
            self.client.loop_stop()
            httpd.server_close()
```

- [ ] **Step 3: Verify health endpoint (requires service to connect)**

If a broker is available:
```bash
MQTT_BROKER=<broker> DEBUG=true python src/ha-tower-discovery.py &
sleep 3
curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health
# Expected: 200
curl -s http://localhost:8080/devices
# Expected: {"devices": [...]}
kill %1
```

Otherwise verify syntax:
```bash
python -m py_compile src/ha-tower-discovery.py && echo 'Syntax OK'
```
Expected: `Syntax OK`

- [ ] **Step 4: Commit**

```bash
git add src/ha-tower-discovery.py
git commit -m "feat: HTTP API with health/ready/devices/forget endpoints"
```

---

## Task 7: Dockerfile & Kubernetes manifests

**Files:**
- Create: `Dockerfile`
- Create: `kubernetes/configmap.yaml`
- Create: `kubernetes/deployment.yaml`
- Create: `kubernetes/service.yaml`
- Create: `kubernetes/ingress.yaml`
- Create: `scripts/create-secret.sh`
- Modify: `.gitignore` (add `scripts/create-secret.sh` — the script itself is safe to commit, but any `.env` or credentials files nearby should not be)

**Interfaces:**
- Consumes: `requirements.txt` (Task 1)
- Produces: deployable image + k8s manifests for `home-assistant` namespace; secret provisioning script

- [ ] **Step 1: Look up current stable Python and paho-mqtt versions**

```bash
# Python slim tag: check https://hub.docker.com/_/python/tags (filter "slim")
# paho-mqtt:
pip index versions paho-mqtt 2>/dev/null | head -2
```
Record both. Use them below (replace `3.XX` and `X.Y.Z`). The Python minor version in `requirements.txt` must match the base image.

- [ ] **Step 2: Create `Dockerfile`**

```dockerfile
FROM python:3.XX-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
RUN useradd -r -u 1000 -s /bin/false app
USER app
CMD ["python", "src/ha-tower-discovery.py"]
```

- [ ] **Step 3: Build and push to private registry**

```bash
TAG=$(git rev-parse --short HEAD)
docker build -t mifs01.intranet:5001/home/tower-ha-discovery:${TAG} .
docker push mifs01.intranet:5001/home/tower-ha-discovery:${TAG}
echo "Image tag: ${TAG}"
```
Expected: image pushed successfully. Note the SHA tag — it goes into `kubernetes/deployment.yaml`.

- [ ] **Step 4: Create `kubernetes/configmap.yaml`**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tower-ha-discovery
  namespace: home-assistant
data:
  MQTT_BROKER: "mosquitto.home-assistant.svc.cluster.local"
  MQTT_PORT: "1883"
  NODE_PREFIX: "node"
  DISCOVERY_PREFIX: "homeassistant"
  HTTP_BIND: "0.0.0.0"
  HTTP_PORT: "8080"
  DEBOUNCE_SECONDS: "120"
  ADOPT_QUIESCENCE: "1"
  ADOPT_TIMEOUT: "10"
  DEFAULT_EXPIRE_AFTER: "7200"
  CONFIG_FILE: "/etc/tower-ha-discovery/config.json"
  DEBUG: "false"
  config.json: |
    {
      "allowlist": ["^[^:]+:[^:]+:[0-9]+$"],
      "location_labels": {},
      "name_overrides": {},
      "sensor_map_overrides": {}
    }
```

- [ ] **Step 5: Create `kubernetes/deployment.yaml`**

Replace `<TAG>` with the git SHA from Step 3.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tower-ha-discovery
  namespace: home-assistant
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: tower-ha-discovery
  template:
    metadata:
      labels:
        app: tower-ha-discovery
    spec:
      containers:
      - name: tower-ha-discovery
        image: mifs01.intranet:5001/home/tower-ha-discovery:<TAG>
        envFrom:
        - configMapRef:
            name: tower-ha-discovery
        - secretRef:
            name: tower-ha-discovery
        env:
        - name: CONFIG_FILE
          value: /etc/tower-ha-discovery/config.json
        volumeMounts:
        - name: config
          mountPath: /etc/tower-ha-discovery
        ports:
        - containerPort: 8080
          name: http
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 5
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: http
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: config
        configMap:
          name: tower-ha-discovery
          items:
          - key: config.json
            path: config.json
```

- [ ] **Step 6: Create `kubernetes/service.yaml`**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: tower-ha-discovery
  namespace: home-assistant
spec:
  selector:
    app: tower-ha-discovery
  ports:
  - name: http
    port: 8080
    targetPort: http
```

- [ ] **Step 7: Create `kubernetes/ingress.yaml`**

Cluster uses Traefik with `active24resolver` for TLS. Do NOT include `secretName` in the `tls` block (Traefik manages certs itself; `secretName` causes errors). Pick a hostname in the form `<name>.mixi.cz` and register it in DNS before deploying.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tower-ha-discovery
  namespace: home-assistant
  annotations:
    spec.ingressClassName: traefik
    traefik.ingress.kubernetes.io/router.tls.certresolver: active24resolver
spec:
  rules:
  - host: tower-discovery.mixi.cz   # TODO: confirm this hostname with the operator
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: tower-ha-discovery
            port:
              number: 8080
  tls:
  - hosts:
    - tower-discovery.mixi.cz        # same hostname, no secretName
```

- [ ] **Step 8: Create `scripts/create-secret.sh`**

This script is the one-time secret provisioner. It must be run by the operator — **never run it from an agent** to prevent the generated token leaking into conversation context.

```bash
#!/usr/bin/env bash
# One-time secret provisioner for tower-ha-discovery.
# Run manually: [MQTT_USER=x MQTT_PASSWORD=y] ./scripts/create-secret.sh
# Never run from an agent — token would leak into conversation context.
set -euo pipefail

NAMESPACE=home-assistant
SECRET_NAME=tower-ha-discovery

if kubectl -n "$NAMESPACE" get secret "$SECRET_NAME" &>/dev/null; then
    echo "Secret '$SECRET_NAME' already exists in namespace '$NAMESPACE'. Nothing to do."
    exit 0
fi

MQTT_USER="${MQTT_USER:-}"
MQTT_PASSWORD="${MQTT_PASSWORD:-}"

if [[ -z "$MQTT_USER" ]]; then
    read -rp "MQTT username (leave empty if broker needs no auth): " MQTT_USER
fi
if [[ -n "$MQTT_USER" && -z "$MQTT_PASSWORD" ]]; then
    read -rsp "MQTT password: " MQTT_PASSWORD; echo
fi

API_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

kubectl -n "$NAMESPACE" create secret generic "$SECRET_NAME" \
    --from-literal=MQTT_USER="$MQTT_USER" \
    --from-literal=MQTT_PASSWORD="$MQTT_PASSWORD" \
    --from-literal=API_TOKEN="$API_TOKEN"

echo ""
echo "Secret created. Store this API_TOKEN securely (e.g. in Bitwarden):"
echo "  API_TOKEN=${API_TOKEN}"
echo ""
echo "This is the only time it will be displayed."
```

```bash
chmod +x scripts/create-secret.sh
```

- [ ] **Step 9: Run secret provisioner (operator step — do not run from agent)**

```
./scripts/create-secret.sh
```
Store the printed `API_TOKEN` in Bitwarden before closing the terminal.

- [ ] **Step 10: Deploy manifests**

```bash
kubectl apply -f kubernetes/
```
Expected: configmap, deployment, service, ingress created/updated.

```bash
kubectl -n home-assistant rollout status deploy/tower-ha-discovery
```
Expected: `successfully rolled out`.

- [ ] **Step 11: Commit**

```bash
git add Dockerfile kubernetes/ scripts/create-secret.sh requirements.txt
git commit -m "feat: Dockerfile, Kubernetes manifests, and secret provisioner"
```

---

## Task 8: Documentation

**Files:**
- Modify: `README.md` (fill in dev cycle and HTTP API sections)
- Create: mixi-docs page via `mcp__home-docs__write_doc`

**Interfaces:**
- Consumes: completed service (Tasks 1–7)

- [ ] **Step 1: Fill in `README.md` dev cycle section**

Replace the `## Development` section with:

```markdown
## Development

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run self-check (no broker needed)

```bash
python src/test_discovery.py
```
Expected: `All N tests passed.`

### Run locally against a broker

```bash
MQTT_BROKER=<your-broker> DEBUG=true python src/ha-tower-discovery.py
```

The service connects, adopts existing retained configs (~1 s quiescence), then
listens on `node/+/#`. Allowlisted nodes with known sensor types appear in HA
after the debounce window (default 120 s). Use `--debounce 5` for faster
local testing.

### Build and push the image

Look up current stable Python + paho-mqtt before the first build:
```bash
pip index versions paho-mqtt   # confirm latest stable; update requirements.txt if needed
```

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
```

- [ ] **Step 2: Fill in `README.md` HTTP API section**

Replace the `## HTTP API` section with:

```markdown
## HTTP API

The service exposes a small API for operations and Kubernetes probes.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/health` | none | Liveness: 200 if process is serving |
| `GET` | `/ready` | none | Readiness: 200 if MQTT connected, 503 otherwise |
| `GET` | `/devices` | none | List discovered nodes and their entities |
| `DELETE` | `/devices/{alias}` | Bearer | Remove a node: clear retained configs, drop from state |
| `DELETE` | `/devices/{alias}/entities/{object_id}` | Bearer | Remove a single entity |

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
```

- [ ] **Step 3: Call `get_conventions()` before writing the mixi-docs page**

Use `mcp__home-docs__get_conventions` to fetch the doc conventions and follow them exactly.

- [ ] **Step 4: Write the mixi-docs operational page**

Use `mcp__home-docs__write_doc` to create a page at a path consistent with the docs structure (check `list_structure` first). The page should cover:

1. **What the service does** — one paragraph, link to the GitHub repo.
2. **Allowlist / rename-to-opt-in** — explain that renaming a node to `role:location:id` is the act of opting it into HA; gateway-default `role:id` nodes never appear.
3. **First-discovery debounce** — new nodes appear complete after 120 s, not entity-by-entity.
4. **Forget API** — when and how to use `DELETE /devices/{alias}`.
5. **Troubleshooting** table:

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Entity stuck with stale value | `expire_after` not set correctly | Check sensor map; file issue |
| Node not appearing | Alias not in allowlist | Rename node to `role:location:id` convention |
| Dev node leaked into HA | Was renamed to three-part form | `DELETE /devices/{alias}` to remove |
| Service not ready | MQTT disconnected | Check broker; `GET /ready` returns 503 |

- [ ] **Step 5: Run self-check one final time**

```bash
python src/test_discovery.py
```
Expected: all tests pass.

- [ ] **Step 6: Final commit**

```bash
git add README.md
git commit -m "docs: complete README dev cycle, HTTP API examples, and mixi-docs page"
```
