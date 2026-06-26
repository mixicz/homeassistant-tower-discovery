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
