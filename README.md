# Smart Precision Irrigation System 2.2

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi-red?style=for-the-badge&logo=raspberrypi)
![Architecture](https://img.shields.io/badge/Architecture-Microservices-orange?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

##  Project Overview
The **Smart Precision Irrigation System** is an IoT-based platform designed to optimize agricultural water usage and prevent crop loss due to climate anomalies.

Unlike traditional timer-based systems, this platform employs a **Microservices Architecture** to make real-time decisions based on soil moisture data, local temperature, and external weather forecasts.

**Key Features:**
* **Smart Water Management:** Triggers irrigation based on crop type and moisture threshold.
* **Multi-Garden Support:** Manage multiple gardens with independent field configurations.
* **Gravity-Fed Irrigation:** Uses elevated water tanks for energy-efficient water delivery without pumps.
* **Frost Prevention:** Monitors temperature forecasts and publishes frost alerts when T < 2°C.
* **Rain-Aware:** Polls the **Open-Meteo API** to cancel scheduled irrigation if rain is predicted (>5mm).
* **Resource Tracking:** Monitors water consumption (L) per irrigation cycle.
* **Remote Monitoring:** Real-time weather alerts via **Telegram Bot** with system status viewing.
* **Data Analytics:** Uploads sensor data to **ThingSpeak** for visualization.
* **Dynamic ID Assignment:** Devices self-register via POST and receive auto-generated IDs.
* **Auto-Discovery:** Water Manager automatically discovers new devices every 60 seconds.

---

##  System Architecture
The software strictly follows **Object-Oriented Programming (OOP)** principles and uses **SenML** message format for all MQTT communications.

### 1. The Edge Layer (Sensors & Actuators)
Running on **Raspberry Pi Pico 2 W** microcontrollers:
* **Sensor Nodes (1):** Collect Soil Moisture and Temperature. Publish readings via MQTT. Register via POST, send heartbeats.
* **Actuator Nodes (1,2):** Control Solenoid Valves (gravity-fed). Subscribe to valve commands, publish valve status and water usage. Register via POST.

### 2. The Service Layer (Core Logic)
Running on a **Raspberry Pi 5** Gateway, communicating via **MQTT** and **REST**:
* **Resource Catalogue (port 8080):** Central registry with full CRUD (GET/POST/PUT/DELETE) for devices.
* **Status Service (port 9090):** Caches all device states with smart payload merging (combines soil_moisture + temperature from same sensor). Provides REST API for status queries.
* **Water Manager:** The brain of the operation. Triggers irrigation based on moisture threshold and crop type. Weather-aware (skips during rain/frost).
* **Weather-Check:** Background service polling Open-Meteo for rain AND frost forecasts. Publishes alerts via MQTT.
* **Telegram Bot:** Subscribes to weather/frost alerts via MQTT and forwards them to users. Queries Status Service via REST for system status.
* **ThingSpeak Adaptor:** Uploads sensor data from Field 1 to the cloud using wildcard MQTT subscriptions (works even when devices register after startup).

---

##  Device Architecture

The system uses **Object-Oriented inheritance** to avoid code duplication between sensors and actuators:

```
BaseDevice (common logic: self-registration, bootstrap, heartbeat, MQTT)
    ├── BaseSensor → SensorNode
    └── BaseActuator → ActuatorNode
```

| Class | File | Purpose |
|-------|------|---------|
| `BaseDevice` | `src/devices/base_device.py` | Self-registration (dynamic ID), bootstrap, heartbeat, MQTT setup |
| `BaseSensor` | `src/devices/base_device.py` | Sensing loop, publish readings |
| `BaseActuator` | `src/devices/base_device.py` | Command handling, status publishing |
| `SensorNode` | `src/devices/sensor_node.py` | Implements `sense()` for soil/temp |
| `ActuatorNode` | `src/devices/actuator_node.py` | Implements valve control logic |

**Why inheritance?** Sensor and actuator nodes share 80% of their code (self-registration, bootstrap, heartbeat, MQTT). Base classes handle the common logic, so device files only implement their unique behavior.

**Dynamic ID Assignment:** Devices register via POST without an ID. The Catalogue generates unique IDs in format `{type}_{garden_id}_{field_id}_{counter:03d}`.

---

##  Device Registration

Devices **self-register** with the Catalogue and receive dynamically assigned IDs:

```python
# Devices call POST /devices with type, garden_id, field_id
# Catalogue returns: assigned ID, topics, garden/field info
payload = {
    "type": "sensor",
    "garden_id": "garden_1",
    "field_id": "field_1",
    "name": "Sensor garden_1 field_1"
}
res = requests.post(url, json=payload)
result = res.json()
# {"status": "registered", "id": "sensor_garden_1_field_1_001", "topics": {...}}
```

Devices send heartbeats every ~60 seconds to keep registration alive.

---

##  Adding Additional Sensors & Actuators

You can register new devices manually using **Postman** or any REST client. The Catalogue assigns a unique ID automatically.

**Endpoint:** `POST http://localhost:8080/devices`

**Headers:** `Content-Type: application/json`

### Register a New Sensor (Dynamic ID):
```json
{
    "type": "sensor",
    "garden_id": "garden_1",
    "field_id": "field_2",
    "name": "Soil Sensor Garden 1 Field 2"
}
```

### Register a New Actuator (Dynamic ID):
```json
{
    "type": "actuator",
    "garden_id": "garden_1",
    "field_id": "field_2",
    "name": "Valve Garden 1 Field 2"
}
```

### JSON Fields:
| Field | Required | Description |
|-------|----------|-------------|
| `type` |  Yes | `"sensor"` or `"actuator"` |
| `garden_id` |  Yes | Garden identifier (e.g., `"garden_1"`) |
| `field_id` |  Yes | Field identifier (e.g., `"field_1"`) |
| `name` | No | Human-readable name |

### Expected Response:
```json
{
    "status": "registered",
    "id": "sensor_garden_1_field_2_001",
    "topics": {
        "publish": ["smart_irrigation/farm/garden_1/field_2/soil_moisture", "..."],
        "subscribe": []
    },
    "garden_id": "garden_1",
    "field_id": "field_2"
}
```

> **Note**: The Catalogue generates a unique ID and MQTT topics automatically. The Water Manager auto-discovers new devices every 60 seconds.

###  Auto-Simulation with Device Simulator

The **Device Simulator** automatically discovers and simulates ALL registered devices. No need to manually run individual device scripts!

**Key Features:**
- **Auto-Registration:** If no devices exist, automatically registers a default sensor and actuator for `garden_1/field_1`
- **Auto-Discovery:** Polls the Catalogue every 60 seconds to find new devices
- **Parallel Simulation:** Runs multiple sensors and actuators simultaneously in separate threads

**How it works:**
1. On startup, checks if any devices exist in the Catalogue
2. If none exist, registers default devices (sensor + actuator for garden_1/field_1)
3. Starts simulating all registered devices
4. Every 60 seconds, checks for newly added devices and simulates them too

**Running the Device Simulator:**
```bash
python src/devices/device_simulator.py
```

> **Tip**: The launcher scripts (`scripts/macos/start.py`) automatically start the Device Simulator!

###  Manual Device Scripts (Alternative)

If you prefer to run individual device processes manually:

```bash
# Run a specific sensor
python src/devices/sensor_node.py garden_1 field_3

# Run a specific actuator
python src/devices/actuator_node.py garden_1 field_3
```

**Why manual mode?** In a real IoT deployment, each device is a physical microcontroller. The manual scripts simulate a single physical device each.

---

##  Multiple Gardens Support

The system supports multiple gardens, each with their own fields and crop configurations:

```json
{
    "gardens": {
        "garden_1": {
            "name": "Main Garden",
            "location": {"lat": 45.06, "lon": 7.66},
            "fields": {
                "field_1": {"crop_type": "tomato", "field_size_m2": 100},
                "field_2": {"crop_type": "wheat", "field_size_m2": 200}
            }
        },
        "garden_2": {
            "name": "Secondary Garden",
            "fields": {
                "field_1": {"crop_type": "lettuce", "field_size_m2": 50}
            }
        }
    }
}
```

### Add a New Garden via Postman:
**Endpoint:** `POST http://localhost:8080/gardens`

```json
{
    "id": "garden_3",
    "name": "Rooftop Garden",
    "location": {"lat": 45.08, "lon": 7.68},
    "fields": {
        "field_1": {
            "crop_type": "tomato",
            "field_size_m2": 25,
            "flow_rate_lpm": 10.0
        }
    }
}
```

---

##  SenML Message Format

All MQTT messages follow the course-standard SenML format:

**Sensor Data (numeric values):**
```json
[
    {"bn": "sensor_garden_1_field_1_001", "n": "soil_moisture", "t": 1735084800.0, "v": 25.5},
    {"bn": "sensor_garden_1_field_1_001", "n": "temperature", "t": 1735084800.0, "v": 22.1}
]
```

**Actuator Status (string values):**
```json
[
    {"bn": "actuator_garden_1_field_1_001", "n": "valve_status", "t": 1735084800.0, "vs": "OPEN"}
]
```

| Field | Description |
|-------|-------------|
| `bn` | Base name (device ID) |
| `n` | Measurement name |
| `t` | Timestamp (Unix epoch) |
| `v` | Numeric value (moisture, temperature, water_liters) |
| `vs` | String value (valve_status: "OPEN"/"CLOSED") |

---

##  Smart Irrigation Logic

The Water Manager triggers irrigation when soil moisture falls below the configured threshold (default: 30%). Irrigation duration is determined by crop type:

**Decision Logic:**
1. If `moisture < threshold` AND no rain/frost alerts → trigger irrigation
2. Duration is based on crop type lookup table

**Crop-Based Durations:**
| Crop | Duration |
|------|----------|
| Tomato | 600s (10 min) |
| Corn | 480s (8 min) |
| Lettuce | 300s (5 min) |
| Wheat | 240s (4 min) |
| Default | 300s (5 min) |

**Weather-Aware:** Irrigation is skipped if rain is predicted (>5mm) or frost alert is active (T < 2°C).

---

##  Resource Tracking

When an actuator closes its valve, it publishes resource usage:

```json
[
    {"bn": "actuator_garden_1_field_1_001", "n": "water_liters", "t": 1735084800.0, "v": 10.5},
    {"bn": "actuator_garden_1_field_1_001", "n": "duration_sec", "t": 1735084800.0, "v": 120.0}
]
```

**Flow Rate:** Configured per field in `gardens.{garden_id}.fields.{field_id}.flow_rate_lpm`

**ThingSpeak Field Mapping (Field 1):**
| Metric | ThingSpeak Field |
|--------|------------------|
| Soil Moisture | field1 |
| Temperature | field2 |
| Water (L) | field3 |
| Water Needed (mm) | field4 |

---

##  Hardware Stack
| Device | Quantity | Function |
| :--- | :--- | :--- |
| **Raspberry Pi 5** | 1 | Central Gateway & Microservices Host |
| **Raspberry Pi Pico 2 W** | 22 | Edge Nodes (Sensors & Actuators) |
| **Adafruit STEMMA Soil** | 10 | Capacitive Soil Moisture Sensor |
| **MCP9808** | 10 | High Accuracy Temperature Sensor |
| **Solenoid Valve (12V)** | 10 | Directional Water Control |
| **Elevated Water Tank** | 1 | Gravity-Fed Water Source |

---

##  Installation & Setup

### Prerequisites
* Python 3.9 or higher
* An MQTT Broker (using public HiveMQ broker: `broker.hivemq.com`)
* Git

### 1. Clone the Repository
```bash
git clone https://github.com/aliivaezii/Smart-Precision-Irrigation.git
cd Smart-Precision-Irrigation
```

### 2. Set Up Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Start the System

####  Quick Start (Recommended)
Use the automated launcher scripts to start all services in separate terminals:

```
scripts/
├── macos/
│   ├── start.py    # Start all services
│   └── stop.py     # Stop all services
└── windows/
    ├── start.py    # Start all services
    └── stop.py     # Stop all services
```

**macOS:**
```bash
python scripts/macos/start.py              # Start all services + devices
python scripts/macos/start.py --no-devices # Start services only
```

**Windows:**
```bash
python scripts\windows\start.py              # Start all services + devices
python scripts\windows\start.py --no-devices # Start services only
python scripts\windows\start.py --powershell # Use PowerShell instead of cmd
```

**Launcher Script Features:**
| Feature | Description |
|---------|-------------|
| Auto-detect Python | Finds virtual environment or system Python |
| Ordered Startup | Services start in correct dependency order |
| Startup Delays | Waits between services for proper initialization |
| Named Windows | Each terminal has a descriptive title |

####  Stop the System
**macOS:**
```bash
python scripts/macos/stop.py         # Stop all services (with confirmation)
python scripts/macos/stop.py --force # Stop without confirmation
```

**Windows:**
```bash
python scripts\windows\stop.py         # Stop all services (with confirmation)
python scripts\windows\stop.py --force # Stop without confirmation
```

####  Manual Start (Alternative)
If you prefer to start services manually in separate terminals:

```bash
# Terminal 1: Catalogue (must start first)
python src/services/catalogue/service.py

# Terminal 2: Status Service
python src/services/status/service.py

# Terminal 3: Weather Check
python src/services/weather_check/service.py

# Terminal 4: Water Manager (auto-discovers devices)
python src/services/water_manager/service.py

# Terminal 5: Telegram Bot
python src/services/telegram_bot/service.py

# Terminal 6: ThingSpeak Adaptor
python src/services/thingspeak_adaptor/service.py

# Terminal 7: Sensor Node (specify garden_id and field_id)
python src/devices/sensor_node.py garden_1 field_1

# Terminal 8: Actuator Node (specify garden_id and field_id)
python src/devices/actuator_node.py garden_1 field_1

# Start additional sensors/actuators for other fields:
python src/devices/sensor_node.py garden_1 field_2
python src/devices/actuator_node.py garden_1 field_2
python src/devices/sensor_node.py garden_2 field_1
```

> **Note**: The Water Manager automatically discovers new devices every 60 seconds. No restart required when adding new sensors/actuators.

---

##  Configuration

The system uses `config/system_config.json` for centralized configuration:

```json
{
    "project_info": {
        "topic_prefix": "smart_irrigation"
    },
    "broker": {
        "address": "broker.hivemq.com",
        "port": 1883,
        "port_tls": 8883,
        "port_websocket": 8000
    },
    "services": {
        "catalogue": {"host": "localhost", "port": 8080},
        "status": {"host": "localhost", "port": 9090}
    },
    "settings": {
        "moisture_threshold": 30.0,
        "rain_threshold_mm": 5.0,
        "frost_threshold_c": 2.0
    },
    "topics": {
        "weather_alert": "smart_irrigation/weather/alert",
        "frost_alert": "smart_irrigation/weather/frost",
        "resource_usage": "smart_irrigation/irrigation/usage"
    },
    "gardens": {
        "garden_1": {
            "name": "Main Garden",
            "fields": {
                "field_1": {"crop_type": "tomato", "field_size_m2": 100, "flow_rate_lpm": 20.0},
                "field_2": {"crop_type": "lettuce", "field_size_m2": 50, "flow_rate_lpm": 15.0}
            }
        }
    },
    "device_counters": {},
    "devices": [],
    "thingspeak": {
        "field_map": {
            "soil_moisture": "field1",
            "temperature": "field2",
            "water_liters": "field3",
            "water_needed": "field4"
        }
    }
}
```

> **Note**: All MQTT topics are prefixed with `smart_irrigation/` to avoid collisions on the public HiveMQ broker. You can customize this prefix in `project_info.topic_prefix`.

> **Dynamic IDs**: The `devices` array is populated at runtime as devices self-register. The `device_counters` object tracks ID sequences per garden/field.

---

##  Services Port Reference

| Service | Port | Description |
|---------|------|-------------|
| Catalogue Service | 8080 | Configuration and device registry |
| Status Service | 9090 | Cached device status API |
| MQTT Broker | 1883 | HiveMQ public broker |

---

##  Documentation

* **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Complete technical documentation

---

##  Team Members
* **Ali Vaezi** (s336256) 
* **Nicolas Restrepo-Lopez** (s336477) 
* **Roderick Tossato Silva** (s336217) 
* **Ludovica Deriu** (s348173)

---

##  License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Last Updated: Jan 2026*  
*System Version: 2.2*
