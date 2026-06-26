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
