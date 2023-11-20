import time
import paho.mqtt.client as mqtt
import json
import os
import argparse
from jinja2 import Environment, FileSystemLoader
from flask import Flask


class Configuration:
    def __init__(self):
        self.mqtt_broker = "mqtt.example.com"
        self.mqtt_port = 1883
        self.mqtt_topic_discovery = "gateway/{id}/nodes/get"
        self.mqtt_topic_nodes = "gateway/{id}/nodes"
        self.mqtt_topic_advertisement = "homeassistant/devices"
        self.advertise_interval = None
        self.firmware_dir = "firmware"

    def load_from_env(self):
        self.mqtt_broker = os.getenv("MQTT_BROKER", self.mqtt_broker)
        self.mqtt_port = os.getenv("MQTT_PORT", self.mqtt_port)
        self.mqtt_topic_discovery = os.getenv("MQTT_TOPIC_DISCOVERY", self.mqtt_topic_discovery)
        self.mqtt_topic_nodes = os.getenv("MQTT_TOPIC_NODES", self.mqtt_topic_nodes)
        self.mqtt_topic_advertisement = os.getenv("MQTT_TOPIC_ADVERTISEMENT", self.mqtt_topic_advertisement)

    def parse_cmd_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--interval", type=int, help="Advertisement interval in seconds")
        args = parser.parse_args()
        if args.interval:
            self.advertise_interval = args.interval
        

config = Configuration()
config.load_from_env()
config.parse_cmd_args()

# Jinja template configuration
template_loader = FileSystemLoader(config.firmware_dir)
template_env = Environment(loader=template_loader)

# MQTT client setup
client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker")
    client.subscribe(config.mqtt_topic_nodes)

def on_message(client, userdata, msg):
    if msg.topic == config.mqtt_topic_nodes:
        devices = json.loads(msg.payload)
        advertise_devices(devices)

def send_discovery_message():
    client.publish(config.mqtt_topic_discovery, "")

def advertise_devices(devices):
    for device in devices:
        template = template_env.get_template(device["firmware"] + ".yaml")
        json_message = template.render(device=device)
        client.publish(config.mqtt_topic_advertisement, json_message)

def main():
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(config.mqtt_broker, config.mqtt_port, 60)

    if config.advertise_interval:
        client.loop_start()
        while True:
            send_discovery_message()
            time.sleep(config.advertise_interval)
    else:
        client.loop_forever()

# Flask app setup
app = Flask(__name__)

@app.route('/health')
def health_check():
    return 'OK'

if __name__ == "__main__":
    main()
