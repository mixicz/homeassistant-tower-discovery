#!/usr/bin/env python3
"""Tower → Home Assistant passive sensor discovery service."""

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time

import paho.mqtt.client as mqtt

from discovery import (
    parse_topic, sanitize_object_id, build_object_id,
    sensor_meta, build_device_name, build_entity_name, build_discovery_payload,
)


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
            print(f'MQTT connect failed: rc={rc}', file=sys.stderr)

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


def main():
    cfg = Configuration()
    cfg.load()
    service = TowerDiscoveryService(cfg)
    service.run()


if __name__ == '__main__':
    main()
