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
