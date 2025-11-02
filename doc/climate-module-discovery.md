# HARDWARIO Climate Module MQTT Discovery Configuration for Home Assistant

## Overview

This document provides corrected MQTT discovery JSON payloads for HARDWARIO Climate Module using **alias-based topics** instead of hexadecimal IDs. The Climate Module includes: lux-meter, hygrometer, barometer, thermometer, and mini battery module.

## Key Corrections

- **Alias Usage**: All MQTT topics use aliases (e.g., `climate-monitor:0`) instead of hex IDs
- **Safe Identifiers**: Colons (`:`) are replaced with underscores (`_`) in Home Assistant identifiers
- **Climate Module**: Focuses specifically on climate sensors (not general sensor module)
- **Mini Battery**: Uses the mini battery module voltage topic

## Example Configuration

**Node Details:**
- Hex ID: `eaf0e05f9dfa` 
- Alias: `climate-monitor:0`
- Safe Alias: `climate-monitor_0` (for identifiers)

## Version 1: Full Names (Recommended for Development)

### Discovery Topic
```
homeassistant/device/climate-monitor_0/config
```

### JSON Payload
```json
{
  "device": {
    "identifiers": ["climate-monitor_0"],
    "name": "HARDWARIO Climate Module climate-monitor:0",
    "manufacturer": "HARDWARIO",
    "model": "Climate Module",
    "sw_version": "v1.3.0",
    "configuration_url": "https://docs.hardwario.com/"
  },
  "origin": {
    "name": "HARDWARIO Tower",
    "sw_version": "v1.3.0",
    "support_url": "https://docs.hardwario.com/"
  },
  "components": {
    "temperature": {
      "platform": "sensor",
      "device_class": "temperature",
      "unit_of_measurement": "°C",
      "state_topic": "node/climate-monitor:0/thermometer/0:0/temperature",
      "unique_id": "climate-monitor_0_temperature",
      "name": "Temperature"
    },
    "humidity": {
      "platform": "sensor",
      "device_class": "humidity",
      "unit_of_measurement": "%",
      "state_topic": "node/climate-monitor:0/hygrometer/0:2/relative-humidity",
      "unique_id": "climate-monitor_0_humidity",
      "name": "Humidity"
    },
    "pressure": {
      "platform": "sensor",
      "device_class": "atmospheric_pressure",
      "unit_of_measurement": "hPa",
      "state_topic": "node/climate-monitor:0/barometer/0:0/pressure",
      "unique_id": "climate-monitor_0_pressure",
      "name": "Pressure"
    },
    "altitude": {
      "platform": "sensor",
      "device_class": "distance",
      "unit_of_measurement": "m",
      "state_topic": "node/climate-monitor:0/barometer/0:0/altitude",
      "unique_id": "climate-monitor_0_altitude",
      "name": "Altitude"
    },
    "illuminance": {
      "platform": "sensor",
      "device_class": "illuminance",
      "unit_of_measurement": "lx",
      "state_topic": "node/climate-monitor:0/lux-meter/0:0/illuminance",
      "unique_id": "climate-monitor_0_illuminance",
      "name": "Illuminance"
    },
    "battery_voltage": {
      "platform": "sensor",
      "device_class": "voltage",
      "unit_of_measurement": "V",
      "state_topic": "node/climate-monitor:0/battery/mini/voltage",
      "unique_id": "climate-monitor_0_battery_voltage",
      "name": "Battery Voltage"
    }
  }
}
```

## Version 2: Abbreviated Names (Memory Optimized)

### Discovery Topic
```
homeassistant/device/climate-monitor_0/config
```

### JSON Payload (Abbreviated)
```json
{
  "dev": {
    "ids": ["climate-monitor_0"],
    "name": "HARDWARIO Climate Module climate-monitor:0",
    "mf": "HARDWARIO",
    "mdl": "Climate Module",
    "sw": "v1.3.0",
    "cu": "https://docs.hardwario.com/"
  },
  "o": {
    "name": "HARDWARIO Tower",
    "sw": "v1.3.0",
    "url": "https://docs.hardwario.com/"
  },
  "cmps": {
    "temp": {
      "p": "sensor",
      "dev_cla": "temperature",
      "unit_of_meas": "°C",
      "stat_t": "node/climate-monitor:0/thermometer/0:0/temperature",
      "uniq_id": "climate-monitor_0_temperature",
      "name": "Temperature"
    },
    "hum": {
      "p": "sensor",
      "dev_cla": "humidity",
      "unit_of_meas": "%",
      "stat_t": "node/climate-monitor:0/hygrometer/0:2/relative-humidity",
      "uniq_id": "climate-monitor_0_humidity",
      "name": "Humidity"
    },
    "pres": {
      "p": "sensor",
      "dev_cla": "atmospheric_pressure",
      "unit_of_meas": "hPa",
      "stat_t": "node/climate-monitor:0/barometer/0:0/pressure",
      "uniq_id": "climate-monitor_0_pressure",
      "name": "Pressure"
    },
    "alt": {
      "p": "sensor",
      "dev_cla": "distance",
      "unit_of_meas": "m",
      "stat_t": "node/climate-monitor:0/barometer/0:0/altitude",
      "uniq_id": "climate-monitor_0_altitude",
      "name": "Altitude"
    },
    "lux": {
      "p": "sensor",
      "dev_cla": "illuminance",
      "unit_of_meas": "lx",
      "stat_t": "node/climate-monitor:0/lux-meter/0:0/illuminance",
      "uniq_id": "climate-monitor_0_illuminance",
      "name": "Illuminance"
    },
    "batt": {
      "p": "sensor",
      "dev_cla": "voltage",
      "unit_of_meas": "V",
      "stat_t": "node/climate-monitor:0/battery/mini/voltage",
      "uniq_id": "climate-monitor_0_battery_voltage",
      "name": "Battery Voltage"
    }
  }
}
```

## Home Assistant Representation

### Device Information
- **Device Name**: HARDWARIO Climate Module climate-monitor:0
- **Device ID**: climate-monitor_0
- **Manufacturer**: HARDWARIO
- **Model**: Climate Module

### Generated Entities
The following entities will be automatically created in Home Assistant:

| Entity ID | Name | Type | State Topic |
|-----------|------|------|-------------|
| `sensor.hardwario_climate_module_climate-monitor_0_temperature` | Temperature | sensor | `node/climate-monitor:0/thermometer/0:0/temperature` |
| `sensor.hardwario_climate_module_climate-monitor_0_humidity` | Humidity | sensor | `node/climate-monitor:0/hygrometer/0:2/relative-humidity` |
| `sensor.hardwario_climate_module_climate-monitor_0_pressure` | Pressure | sensor | `node/climate-monitor:0/barometer/0:0/pressure` |
| `sensor.hardwario_climate_module_climate-monitor_0_altitude` | Altitude | sensor | `node/climate-monitor:0/barometer/0:0/altitude` |
| `sensor.hardwario_climate_module_climate-monitor_0_illuminance` | Illuminance | sensor | `node/climate-monitor:0/lux-meter/0:0/illuminance` |
| `sensor.hardwario_climate_module_climate-monitor_0_battery_voltage` | Battery Voltage | sensor | `node/climate-monitor:0/battery/mini/voltage` |

## Key Abbreviations Reference

| Full Name | Abbreviated |
|-----------|-------------|
| `device` | `dev` |
| `identifiers` | `ids` |
| `manufacturer` | `mf` |
| `model` | `mdl` |
| `sw_version` | `sw` |
| `configuration_url` | `cu` |
| `origin` | `o` |
| `support_url` | `url` |
| `availability_topic` | `avty_t` |
| `payload_available` | `pl_avail` |
| `payload_not_available` | `pl_not_avail` |
| `components` | `cmps` |
| `platform` | `p` |
| `device_class` | `dev_cla` |
| `unit_of_measurement` | `unit_of_meas` |
| `state_topic` | `stat_t` |
| `unique_id` | `uniq_id` |

## Implementation Notes

1. **Alias Conversion**: Replace `:` with `_` in identifiers but keep original alias in MQTT topics
2. **Climate Module Focus**: Only includes sensors specific to the climate module
3. **Mini Battery**: Uses `battery/mini/voltage` topic instead of standard battery
4. **Temperature Sensor**: Uses `thermometer/0:0/temperature` (Climate Module tag) instead of Core Module
5. **Availability**: Optional but recommended for device online/offline status tracking

## MQTT Topics Used

- **Temperature**: `node/climate-monitor:0/thermometer/0:0/temperature`
- **Humidity**: `node/climate-monitor:0/hygrometer/0:2/relative-humidity`
- **Pressure**: `node/climate-monitor:0/barometer/0:0/pressure`
- **Altitude**: `node/climate-monitor:0/barometer/0:0/altitude`
- **Illuminance**: `node/climate-monitor:0/lux-meter/0:0/illuminance`
- **Battery**: `node/climate-monitor:0/battery/mini/voltage`

This configuration will create a single device in Home Assistant with all climate sensors properly grouped and automatically discovered.