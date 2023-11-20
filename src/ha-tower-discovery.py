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
        self.mqtt_topic_discovery = "gateway/{}/nodes/get"
        self.mqtt_topic_nodes = "gateway/{}/nodes"
        self.mqtt_topic_advertisement = "homeassistant/devices"
        self.gateway_id = "usb-dongle"
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
    client.subscribe(config.mqtt_topic_nodes.format(config.gateway_id))

def on_message(client, userdata, msg):
    if msg.topic == config.mqtt_topic_nodes.format(config.gateway_id):
        # format of device list:
        # [{"id": "72335554ea02", "alias": "led-pwm:terasa:0"}, {"id": "d704ee327346", "alias": "motion-detector:terasa:0"}, {"id": "373ca27b396d", "alias": "button:vchod:0"}, {"id": "13d444d82727", "alias": "doorbell:bell:0"}, {"id": "eaf0e05f9dfa", "alias": "climate-monitor:0"}, {"id": "7de0a3693435", "alias": "motion-detector:schodiste:0"}, {"id": "e450ffcccdba", "alias": "motion-detector:schodiste:1"}, {"id": "094d268ec673", "alias": "led-pwm:schodiste:0"}, {"id": "99309c1c2843", "alias": "motion-detector:puda:0"}, {"id": "80331b60364d", "alias": "led-pwm:puda:0"}]
        devices = json.loads(msg.payload)
        
        for device in devices:
            alias_parts = device["alias"].split(":")
            device["firmware"] = alias_parts[0]
        
        advertise_devices(devices)

def send_discovery_message():
    client.publish(config.mqtt_topic_discovery.format(config.gateway_id), "")

def advertise_devices(devices):
    for device in devices:
        template = template_env.get_template(device["firmware"] + ".yaml")
        json_message = template.render(device=device)
        client.publish(config.mqtt_topic_advertisement, json_message)

def main():
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(config.mqtt_broker, config.mqtt_port, 60)
    
    # Flask app setup
    app = Flask(__name__)

    @app.route('/health')
    def health_check():
        return 'OK'


    if config.advertise_interval:
        client.loop_start()
        while True:
            send_discovery_message()
            time.sleep(config.advertise_interval)
    else:
        client.loop_forever()

if __name__ == "__main__":
    main()
