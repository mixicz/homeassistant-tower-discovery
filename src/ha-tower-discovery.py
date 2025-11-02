#!/usr/bin/env python3
import time
import paho.mqtt.client as mqtt
import json
import os
import argparse
import jinja2
from jinja2 import Environment, FileSystemLoader
from flask import Flask
import os
import argparse
from pprint import pprint


class Configuration:
    def __init__(self):
        self.mqtt_broker = "mqtt.example.com"
        self.mqtt_port = 1883
        self.mqtt_topic_discovery = "gateway/{}/nodes/get"
        self.mqtt_topic_nodes = "gateway/{}/nodes"
        self.mqtt_topic_advertisement = "homeassistant/devices"
        self.gateway_id = "usb-dongle"
        self.advertise_interval = None
        # self.advertise_interval = 24*60*60
        self.firmware_dir = "firmware"
        self.debug = False

    def load_from_env(self):
        self.mqtt_broker = os.getenv("MQTT_BROKER", self.mqtt_broker)
        self.mqtt_port = os.getenv("MQTT_PORT", self.mqtt_port)
        self.mqtt_topic_discovery = os.getenv("MQTT_TOPIC_DISCOVERY", self.mqtt_topic_discovery)
        self.mqtt_topic_nodes = os.getenv("MQTT_TOPIC_NODES", self.mqtt_topic_nodes)
        self.mqtt_topic_advertisement = os.getenv("MQTT_TOPIC_ADVERTISEMENT", self.mqtt_topic_advertisement)
        self.gateway_id = os.getenv("GATEWAY_ID", self.gateway_id)
        self.advertise_interval = os.getenv("ADVERTISE_INTERVAL", self.advertise_interval)
        self.firmware_dir = os.getenv("FIRMWARE_DIR", self.firmware_dir)

    def parse_cmd_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--broker", type=str, help="MQTT broker address")
        parser.add_argument("--port", type=int, help="MQTT broker port")
        parser.add_argument("--discovery-topic", type=str, help="MQTT topic for discovery")
        parser.add_argument("--nodes-topic", type=str, help="MQTT topic for nodes")
        parser.add_argument("--advertisement-topic", type=str, help="MQTT topic for advertisement")
        parser.add_argument("--gateway-id", type=str, help="HArdwario USB dongle Gateway ID")
        parser.add_argument("--interval", type=int, help="Advertisement interval in seconds")
        parser.add_argument("--firmware-dir", type=str, help="Firmware directory")
        parser.add_argument("--debug", action="store_true", help="Enable debug mode")
        args = parser.parse_args()

        if args.broker:
            self.mqtt_broker = args.broker
        if args.port:
            self.mqtt_port = args.port
        if args.discovery_topic:
            self.mqtt_topic_discovery = args.discovery_topic
        if args.nodes_topic:
            self.mqtt_topic_nodes = args.nodes_topic
        if args.advertisement_topic:
            self.mqtt_topic_advertisement = args.advertisement_topic
        if args.gateway_id:
            self.gateway_id = args.gateway_id
        if args.interval:
            self.advertise_interval = args.interval
        if args.firmware_dir:
            self.firmware_dir = args.firmware_dir
        if args.debug:
            self.debug = True

# Load configuration
config = Configuration()
config.load_from_env()
config.parse_cmd_args()

# Jinja template configuration
template_loader = FileSystemLoader(config.firmware_dir)
template_env = Environment(loader=template_loader)

# MQTT client setup
client = mqtt.Client()

def sanitize_object_id(s):
    # Replace unsupported characters with underscore; keep alnum, '-' and '_'
    import re
    return re.sub(r'[^A-Za-z0-9_-]', '_', s)

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker")
    client.subscribe(config.mqtt_topic_nodes.format(config.gateway_id))

    # Subscribe to device-originated HomeAssistant discovery topics:
    # node/{id}/homeassistant/{component}/{sub_id}/#
    client.subscribe("node/+/homeassistant/+/+/#")


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload

    # Node list (discovery of devices) - existing behavior
    if topic == config.mqtt_topic_nodes.format(config.gateway_id):
        if config.debug:
            print("Received device list: {} -> {}".format(config.gateway_id, payload))
        # format of device list:
        # [{"id": "72335554ea02", "alias": "led-pwm:terasa:0"}, {"id": "d704ee327346", "alias": "motion-detector:terasa:0"}, {"id": "373ca27b396d", "alias": "button:vchod:0"}, {"id": "13d444d82727", "alias": "doorbell:bell:0"}, {"id": "eaf0e05f9dfa", "alias": "climate-monitor:0"}, {"id": "7de0a3693435", "alias": "motion-detector:schodiste:0"}, {"id": "e450ffcccdba", "alias": "motion-detector:schodiste:1"}, {"id": "094d268ec673", "alias": "led-pwm:schodiste:0"}, {"id": "99309c1c2843", "alias": "motion-detector:puda:0"}, {"id": "80331b60364d", "alias": "led-pwm:puda:0"}]
        try:
            devices = json.loads(payload)
        except Exception as e:
            print("Error parsing device list:", e)
            return

        for device in devices:
            alias_parts = device["alias"].split(":")
            device["firmware"] = alias_parts[0]
            device["safe_alias"] = sanitize_object_id(device["alias"])
            device["version"] = device.get("version", "v0")  # Default version if not provided

        if config.debug:
            print("  \--> device list: {}".format(devices))

        advertise_devices(devices)
        return

    # Forward device-originated HomeAssistant discovery messages only
    parts = topic.split('/')
    # Expecting: node/{id}/homeassistant/{component}/{sub_id}/... (config payload usually at the end)
    if len(parts) >= 5 and parts[0] == 'node' and parts[2] == 'homeassistant':
        node_id = parts[1]
        component = parts[3]
        sub_id = parts[4]

        # Build object_id as '{ID}-{sub_id}' and sanitize
        object_id = sanitize_object_id(f"{node_id}-{sub_id}")

        # Target discovery config topic for HomeAssistant
        target_topic = f"homeassistant/{component}/{object_id}/config"

        # Only forward the discovery/config payload. Do not forward subsequent command/state topics.
        # We assume the device publishes discovery under this node/... topic namespace.
        try:
            # Attempt to parse payload as JSON and prepend node prefix to topic fields inside
            node_prefix = f"{parts[0]}/{parts[1]}/"
            forwarded_payload = payload
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    # For each string field that looks like an MQTT topic, prepend node prefix
                    for k, v in list(parsed.items()):
                        if isinstance(v, str) and '/' in v:
                            # Do not modify absolute homeassistant discovery target paths
                            if v.startswith('homeassistant/'):
                                continue
                            # Avoid double-prefixing
                            if v.startswith(node_prefix):
                                continue
                            # Strip leading slashes
                            vv = v.lstrip('/')
                            parsed[k] = node_prefix + vv
                    forwarded_payload = json.dumps(parsed)
            except Exception:
                # if not JSON, forward raw payload
                forwarded_payload = payload

            # Publish the (possibly modified) payload as retained so HA can discover the entity
            client.publish(target_topic, forwarded_payload, qos=0, retain=True)
            if config.debug:
                print(f"Forwarded discovery: {topic} -> {target_topic}")
        except Exception as e:
            print("Error forwarding discovery payload:", e)
        return

    # Otherwise ignore other messages to avoid forwarding commands/events for led-pwm
    if config.debug:
        print(f"Ignored topic: {topic}")

def send_discovery_message():
    client.publish(config.mqtt_topic_discovery.format(config.gateway_id), "")

def advertise_devices(devices):
    for device in devices:
        try:
            template = template_env.get_template(device["firmware"] + ".yaml")
            json_message = template.render(device=device)
            client.publish(config.mqtt_topic_advertisement, json_message)
        except jinja2.exceptions.TemplateNotFound:
            if config.debug:
                print(f"Template file {device['firmware']}.yaml not found")

def main():
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(config.mqtt_broker, config.mqtt_port, 60)
    
    # Flask app setup
    app = Flask(__name__)

    @app.route('/health')
    def health_check():
        if config.debug:
            pprint("Health check endpoint called")
        return 'OK'


    if config.advertise_interval:
        client.loop_start()
        while True:
            send_discovery_message()
            time.sleep(config.advertise_interval)
    else:
        send_discovery_message()
        client.loop_forever()

if __name__ == "__main__":
    main()
