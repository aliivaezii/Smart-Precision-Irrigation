# Smart Precision Irrigation System - Technical Documentation

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Communication Protocols](#3-communication-protocols)
4. [SenML Message Format](#4-senml-message-format)
5. [Component Analysis](#5-component-analysis)
6. [Service Roles (Provider/Consumer)](#6-service-roles-providerconsumer)
7. [Smart Irrigation Logic](#7-smart-irrigation-logic)
8. [Resource Tracking](#8-resource-tracking)
9. [Data Flow](#9-data-flow)
10. [Configuration](#10-configuration)
11. [MQTT Topics](#11-mqtt-topics)
12. [REST API Endpoints](#12-rest-api-endpoints)
13. [Services Port Reference](#13-services-port-reference)

---

## 1. System Overview

The **Smart Precision Irrigation System** is an IoT-based microservices platform for smart agriculture. It uses a combination of **REST APIs** and **MQTT messaging** to orchestrate sensor data collection, intelligent decision-making, and actuator control.

### Key Objectives:
- **Smart Water Management**: Irrigate based on crop type, field size, and moisture deficit
- **Gravity-Fed Irrigation**: Utilizes elevated water tanks for energy-efficient water delivery
- **Weather-Aware**: Cancel irrigation if rain OR frost is predicted
- **Resource Tracking**: Monitor water consumption (L) per irrigation cycle
- **Real-time Monitoring**: Telegram notifications with system status viewing
- **Cloud Analytics**: ThingSpeak integration for sensor data visualization
- **Dynamic Registration**: Devices self-register via REST POST and receive auto-assigned IDs
- **Multi-Garden Support**: Manage multiple gardens with independent fields
- **Auto-Discovery**: Water Manager automatically discovers new devices

### Multi-Garden Architecture

The system supports **multiple gardens**, each with **multiple fields**. This enables:
- Independent irrigation control per field
- Different crop types per field with appropriate water calculations
- Scalable deployment across large agricultural operations

**Garden/Field Hierarchy**:
```
System
├── garden_1 (Main Garden)
│   ├── field_1 (tomato, 100m², 20 LPM)
│   └── field_2 (lettuce, 50m², 15 LPM)
│
└── garden_2 (Secondary Garden)
    └── field_1 (wheat, 200m², 25 LPM)
```

**Device ID Format**: `{type}_{garden_id}_{field_id}_{counter:03d}`
- Example: `sensor_garden_1_field_1_001`, `actuator_garden_2_field_1_002`

**Topic Format**: `{topic_prefix}/farm/{garden_id}/{field_id}/{data_type}`
- Example: `smart_irrigation/farm/garden_1/field_1/soil_moisture`

---

## 2. Architecture Diagram

### 2.1 System Architecture

![Smart Precision Irrigation System Architecture](ARCHITECTURE.pdf)

### 2.2 Legend

| Symbol | Meaning |
|--------|---------|
| **●───** | REST Web Services (Provider) - Component exposes a REST API |
| **───➝** | REST Web Services (Consumer) - Component calls a REST API |
| **- - -** (orange dashed) | MQTT Communication |
| **(1)** | MQTT Publisher |
| **(2)** | MQTT Subscriber |
| **(1,2)** | Both MQTT Publisher and Subscriber |

### 2.3 Component Overview

| Component | Type | Role |
|-----------|------|------|
| **Device, Service & Resource Catalogue** | REST Provider (●) | Central registry for all devices, services, and configuration |
| **Water Manager (1,2)** | MQTT Pub/Sub + REST Consumer | Control strategy - decides when to irrigate based on sensor data and weather |
| **Device Connector for RPi - Sensors (1)** | MQTT Publisher + REST Consumer | Publishes soil moisture and temperature readings |
| **Device Connector for RPi - Actuators (1,2)** | MQTT Pub/Sub + REST Consumer | Receives valve commands, publishes status and resource usage |
| **Status Service (buffer) (2)** | REST Provider + MQTT Sub | Caches device status, provides REST API for queries |
| **Weather Check (1)** | MQTT Publisher + REST Consumer | Publishes rain and frost alerts from Open-Meteo API |
| **ThingSpeak Adaptor (2)** | MQTT Subscriber + REST Consumer | Uploads sensor data to ThingSpeak cloud platform |
| **Telegram Bot (2)** | MQTT Subscriber + REST Consumer | Subscribes to alerts, queries Status Service and Catalogue |
| **Message Broker** | MQTT Broker | HiveMQ public broker (broker.hivemq.com:1883) |
| **Open-Meteo API** | External REST API | Weather forecast data provider |
| **ThingSpeak Platform** | External REST API | Cloud IoT analytics platform |

### 2.4 Communication Flow Summary

Based on the architecture diagram, the following connections exist:

| From | To | Protocol | Line Type | Description |
|------|----|----------|-----------|-------------|
| Catalogue | All Services | REST | Solid (●) | Bootstrap configuration provider |
| Sensors | Catalogue | REST | Solid (➝) | Device registration |
| Actuators | Catalogue | REST | Solid (➝) | Device registration |
| Water Manager | Catalogue | REST | Solid (➝) | Configuration & device discovery |
| Status Service | Catalogue | REST | Solid (➝) | Device list for subscriptions |
| Weather Check | Catalogue | REST | Solid (➝) | Bootstrap configuration |
| ThingSpeak Adaptor | Catalogue | REST | Solid (➝) | Bootstrap configuration |
| Telegram Bot | Catalogue | REST | Solid (➝) | Bootstrap configuration |
| Telegram Bot | Status Service | REST | Solid (➝) | Query device status |
| Weather Check | Open-Meteo API | REST | Solid (➝) | Weather forecast data |
| ThingSpeak Adaptor | ThingSpeak Platform | REST | Solid (➝) | Cloud data upload |
| Sensors (1) | Message Broker | MQTT Pub | Dashed | Soil moisture & temperature |
| Actuators (1,2) | Message Broker | MQTT Pub/Sub | Dashed | Receive commands, publish status & usage |
| Water Manager (1,2) | Message Broker | MQTT Pub/Sub | Dashed | Commands out, sensor data & alerts in |
| Status Service (2) | Message Broker | MQTT Sub | Dashed | Cache all device data |
| Weather Check (1) | Message Broker | MQTT Pub | Dashed | Rain/Frost alerts |
| ThingSpeak Adaptor (2) | Message Broker | MQTT Sub | Dashed | Sensor data for cloud upload |
| Telegram Bot (2) | Message Broker | MQTT Sub | Dashed | Weather/Frost alerts for notifications |

---

## 3. Communication Protocols

The system uses **two primary communication methods**:

### 3.1 REST (Representational State Transfer)

| Usage | Description |
|-------|-------------|
| **Service Discovery** | All services fetch configuration from Catalogue at startup |
| **External APIs** | Weather data from Open-Meteo, cloud uploads to ThingSpeak |
| **User Notifications** | Telegram Bot API for sending messages |

### 3.2 MQTT (Message Queuing Telemetry Transport)

| Usage | Description |
|-------|-------------|
| **Sensor Data** | Sensor nodes publish soil moisture & temperature readings |
| **Actuator Commands** | Water Manager publishes valve open/close commands |
| **Weather Alerts** | Weather Check broadcasts rain/frost alerts |
| **Event Notifications** | Services subscribe to events they need to react to |

### Protocol Selection Rationale:

| Criterion | REST | MQTT |
|-----------|------|------|
| **Configuration/Bootstrap** | ✅ Request-Response pattern | ❌ Not suitable |
| **Real-time Sensor Data** | ❌ Polling overhead | ✅ Pub/Sub efficiency |
| **Commands to Actuators** | ❌ Requires polling | ✅ Instant delivery |
| **External Cloud APIs** | ✅ Standard HTTP | ❌ Not supported |

### 3.3 MQTT Quality of Service (QoS)

This system uses different QoS levels based on message importance:

| Message Type | QoS | Reason |
|--------------|-----|--------|
| **Weather Alerts** | QoS 1 | Critical - must be delivered at least once |
| **Frost Alerts** | QoS 1 | Critical - crop protection depends on it |
| **Actuator Commands** | QoS 1 | Important - valve must receive command |
| **Sensor Data** | QoS 0 | High frequency - occasional loss acceptable |

**QoS Levels Explained:**

- **QoS 0 (At most once)**: Fire and forget. No acknowledgment. Used for frequent sensor readings where losing one reading is not critical.

- **QoS 1 (At least once)**: Guaranteed delivery with acknowledgment. Message may be delivered multiple times. Used for alerts and commands.

**Implementation in Code:**

```python
# Weather Check - publishes alerts with QoS 1
self.client.publish(self.topic_weather_alert, json.dumps(msg), qos=1)
self.client.publish(self.topic_frost_alert, json.dumps(msg), qos=1)

# Water Manager - subscribes to alerts with QoS 1
self.client.subscribe(self.topic_weather_alert, qos=1)
self.client.subscribe(self.topic_frost_alert, qos=1)

# Actuator - subscribes to commands with QoS 1
self.client.subscribe(topic, qos=1)

# Sensor data - uses QoS 0 (high frequency, loss acceptable)
self.client.publish(topic, json.dumps(msg), qos=0)
```

---

## 4. SenML Message Format

All MQTT messages in this system follow the **SenML (Sensor Markup Language)** format as per course standards.

### 4.1 Format Specification

| Field | Description | Example |
|-------|-------------|---------|
| `bn` | Base Name (device ID) | `"sensor_node_field_1"` |
| `n` | Measurement Name | `"soil_moisture"` |
| `t` | Timestamp (Unix epoch) | `1703419200.0` |
| `v` | Numeric Value | `25.5` |
| `vs` | String Value | `"OPEN"` |
| `vb` | Boolean Value | `true` |

### 4.2 Value Field Types

SenML supports different value fields depending on the data type:

| Field | Type | Used For | Example |
|-------|------|----------|---------|
| `v` | Numeric | Sensor readings (moisture, temperature, water_liters) | `"v": 25.5` |
| `vs` | String | Status values (valve_status) | `"vs": "OPEN"` |
| `vb` | Boolean | On/off states | `"vb": true` |

**Important**: Only ONE value field should be present per measurement object.

### 4.3 Important Rules

1. **Always a List**: Messages are wrapped in an array `[...]`, even for single measurements
2. **Single Value**: Each object contains only ONE value field (`v`, `vs`, or `vb`)
3. **Separate Objects**: Each measurement type is a separate object in the list

### 4.4 Examples

**Sensor Data (numeric values using `v`):**
```json
[
    {"bn": "sensor_garden_1_field_1_001", "n": "soil_moisture", "t": 1703419200.0, "v": 25.5},
    {"bn": "sensor_garden_1_field_1_001", "n": "temperature", "t": 1703419200.0, "v": 22.1}
]
```

**Actuator Status (string value using `vs`):**
```json
[
    {"bn": "actuator_garden_1_field_1_001", "n": "valve_status", "t": 1703419200.0, "vs": "OPEN"}
]
```

---

## 5. Component Analysis

### 5.1 Common Module

#### `src/common/MyMQTT.py`

**Purpose**: Reusable MQTT client wrapper based on the Paho MQTT library.

**Key Features**:
- Encapsulates MQTT connection, publishing, and subscription
- Supports callback notification via `notifier` interface
- Handles both old and new Paho MQTT API versions

```python
class MyMQTT:
    def __init__(self, client_id, broker, port, notifier=None)
    def start()          # Connect and start event loop
    def stop()           # Disconnect and stop event loop
    def publish(topic, message, qos=0)
    def subscribe(topic, qos=0)
```

**Callback Interface**: Services implement a `notify(topic, payload)` method to receive messages.

---

### 5.2 Base Device Classes

#### `src/devices/base_device.py`

**Purpose**: Provides reusable base classes for all IoT devices. Uses inheritance to avoid code duplication between sensors and actuators.

**Class Hierarchy**:
```
BaseDevice (parent class)
    ├── BaseSensor (for sensor devices)
    │       └── SensorNode (soil moisture + temperature)
    │
    └── BaseActuator (for actuator devices)
            └── ActuatorNode (solenoid valve)
```

#### BaseDevice Class

**Purpose**: Common functionality for all devices (self-registration with dynamic ID, bootstrap, heartbeat, MQTT).

**Key Features**:
- **Dynamic ID Assignment**: Devices register without an ID; the Catalogue assigns one
- **Multi-Garden Support**: Devices specify `garden_id` and `field_id`
- **Topics from Catalogue**: MQTT topics are generated by the Catalogue, not hardcoded

**Key Methods**:
```python
class BaseDevice:
    def __init__(self, catalogue_url, garden_id='garden_1', field_id='field_1', device_type='sensor'):
        # Step 1: Self-register with Catalogue (gets assigned ID)
        # Step 2: Bootstrap - fetch full config from Catalogue
        # Step 3: Get broker info and field config from gardens

    def _self_register(self):
        # REST POST to Catalogue WITHOUT ID
        # Catalogue generates unique ID and returns it with topics
        # Example response: {"id": "sensor_garden_1_field_1_001", "topics": {...}}

    def heartbeat(self):
        # REST POST to Catalogue with device ID (keep-alive)

    def start_mqtt(self, notifier=None):
        # Creates MyMQTT client and connects to broker

    def stop(self):
        # Stops MQTT client gracefully
```

**Self-Registration Flow**:
```
Device                              Catalogue
   │                                    │
   │  POST /devices                     │
   │  {"type": "sensor",                │
   │   "garden_id": "garden_1",         │
   │   "field_id": "field_1"}           │
   │ ─────────────────────────────────► │
   │                                    │ Generate ID
   │                                    │ Generate Topics
   │  {"status": "registered",          │
   │   "id": "sensor_garden_1_field_1_001",
   │   "topics": {"publish": [...], ...}}
   │ ◄───────────────────────────────── │
   │                                    │
```

**Registration Payload (sent by device)**:
```json
{
    "type": "sensor",
    "garden_id": "garden_1",
    "field_id": "field_1",
    "name": "Sensor garden_1 field_1"
}
```

**Registration Response (from Catalogue)**:
```json
{
    "status": "registered",
    "id": "sensor_garden_1_field_1_001",
    "topics": {
        "publish": [
            "smart_irrigation/farm/garden_1/field_1/soil_moisture",
            "smart_irrigation/farm/garden_1/field_1/temperature"
        ],
        "subscribe": []
    },
    "garden_id": "garden_1",
    "field_id": "field_1"
}
```
```

#### BaseSensor Class

**Purpose**: Base class for sensor devices. Extends BaseDevice with sensing and publishing logic.

**Key Methods**:
```python
class BaseSensor(BaseDevice):
    def __init__(self, catalogue_url, garden_id='garden_1', field_id='field_1'):
        # Calls parent __init__ which self-registers
        # Gets publish topics from registration response
        # Starts MQTT client

    def sense(self):
        # Abstract method - subclass must implement
        # Returns dict like {"soil_moisture": 45.2, "temperature": 22.5}
        raise NotImplementedError()

    def publish_reading(self, readings):
        # Creates SenML list from readings dict
        # Publishes to each topic from Catalogue response

    def run(self, interval=10, heartbeat_interval=6):
        # Main loop: sense → publish → sleep → repeat
        # Sends heartbeat every N cycles
```

#### BaseActuator Class

**Purpose**: Base class for actuator devices. Extends BaseDevice with command handling.

**Key Methods**:
```python
class BaseActuator(BaseDevice):
    def __init__(self, catalogue_url, garden_id='garden_1', field_id='field_1'):
        # Calls parent __init__ which self-registers
        # Gets subscribe/publish topics from registration response
        # Starts MQTT client with self as notifier

    def notify(self, topic, payload):
        # MQTT callback - receives commands
        # Parses JSON and calls execute_command()

    def execute_command(self, command, params):
        # Abstract method - subclass must implement
        # Example: command="OPEN", params={"duration": 300}
        raise NotImplementedError()

    def publish_status(self, status_data):
        # Creates SenML list from status dict
        # Publishes to valve_status topic

    def run(self, heartbeat_interval=60):
        # Subscribes to command topics
        # Main loop: just heartbeat (commands via MQTT callback)
```

---

### 5.3 Sensor Layer

#### `src/devices/sensor_node.py`

**Purpose**: Soil moisture and temperature sensor. Extends `BaseSensor` class.

**Inheritance**: `SensorNode` → `BaseSensor` → `BaseDevice`

**What SensorNode Implements**:
Only the `sense()` method - all other logic (self-registration, heartbeat, MQTT, publish) is inherited from base classes.

```python
class SensorNode(BaseSensor):
    def sense(self):
        # Simulates reading from soil moisture and temperature sensors
        # Returns: {"soil_moisture": 45.2, "temperature": 22.5}
        return {
            "soil_moisture": random.uniform(20.0, 80.0),
            "temperature": random.uniform(15.0, 35.0)
        }
```

**Running the Sensor**:
```bash
# Start sensor for garden_1/field_1
python src/devices/sensor_node.py garden_1 field_1

# Start sensor for garden_2/field_1
python src/devices/sensor_node.py garden_2 field_1
```

**Why Inheritance Works**:
- `BaseSensor.run()` calls `self.sense()` which runs `SensorNode.sense()`
- ID is assigned by Catalogue at startup (not hardcoded)
- Topics are received from Catalogue response
- SensorNode is only ~50 lines instead of ~150 lines

**Data Format (SenML List)**:
```json
[
    {"bn": "sensor_garden_1_field_1_001", "n": "soil_moisture", "t": 1703419200.0, "v": 45.2},
    {"bn": "sensor_garden_1_field_1_001", "n": "temperature", "t": 1703419200.0, "v": 22.5}
]
```

**Communication** (inherited from BaseDevice/BaseSensor):
- **REST POST** → Catalogue (self-registration, receives ID)
- **REST GET** → Catalogue (bootstrap config)
- **REST POST** → Catalogue (heartbeat)
- **MQTT Publish** → `smart_irrigation/farm/{garden_id}/{field_id}/soil_moisture`

---

### 5.4 Actuator Layer

#### `src/devices/actuator_node.py`

**Purpose**: Controls solenoid valves for gravity-fed irrigation. Extends `BaseActuator` class.

**Inheritance**: `ActuatorNode` → `BaseActuator` → `BaseDevice`

**System Design**: The system uses gravity-fed irrigation from elevated water tanks. This design eliminates the need for electric pumps, reducing energy consumption and hardware complexity.

**What ActuatorNode Implements**:
Only the `execute_command()` method and valve-specific logic - all other logic (self-registration, heartbeat, MQTT, notify) is inherited from base classes.

```python
class ActuatorNode(BaseActuator):
    def execute_command(self, command, params):
        # Handles OPEN and CLOSE commands for valve
        if command == 'OPEN':
            duration = params.get('duration', 60)
            self.open_valve(duration)
        elif command == 'CLOSE':
            self.close_valve()

    def open_valve(self, duration):
        # Opens valve, starts timer thread for auto-close

    def close_valve(self):
        # Closes valve, calculates water used, publishes usage

    def publish_resource_usage(self, water_liters, duration_sec):
        # Publishes water consumption to irrigation/usage topic
```

**Running the Actuator**:
```bash
# Start actuator for garden_1/field_1
python src/devices/actuator_node.py garden_1 field_1

# Start actuator for garden_2/field_1
python src/devices/actuator_node.py garden_2 field_1
```

**Why Inheritance Works**:
- `BaseActuator.notify()` parses MQTT message and calls `self.execute_command()`
- `ActuatorNode.execute_command()` handles the specific valve logic
- ID is assigned by Catalogue at startup (not hardcoded)
- Flow rate is read from garden/field configuration
- ActuatorNode is only ~160 lines instead of ~270 lines

**Flow Rate Configuration** (from Catalogue garden/field config):
```json
{
    "gardens": {
        "garden_1": {
            "fields": {
                "field_1": {
                    "flow_rate_lpm": 20.0
                }
            }
        }
    }
}
```

**Resource Calculation (on valve close)**:
```python
water_liters = (flow_rate_lpm * duration_sec) / 60.0
```

**Published Data (SenML List)**:
```json
[
    {"bn": "actuator_garden_1_field_1_001", "n": "water_liters", "t": 1703419200.0, "v": 10.5},
    {"bn": "actuator_garden_1_field_1_001", "n": "duration_sec", "t": 1703419200.0, "v": 120.0}
]
```

**Communication** (inherited from BaseDevice/BaseActuator):
- **REST POST** → Catalogue (self-registration, receives ID)
- **REST GET** → Catalogue (bootstrap config)
- **REST POST** → Catalogue (heartbeat)
- **MQTT Subscribe** → `smart_irrigation/farm/{garden_id}/{field_id}/valve_cmd`
- **MQTT Publish** → `smart_irrigation/farm/{garden_id}/{field_id}/valve_status`, `smart_irrigation/irrigation/usage`

---

### 5.5 Device Simulator

#### `src/devices/device_simulator.py`

**Purpose**: Automatically discovers and simulates ALL registered devices from the Catalogue.

**Why This Exists**:
When you register a device via POST (e.g., from Postman), the Catalogue creates the record and the Water Manager starts subscribing - but no actual data gets published because there's no physical device running. The Device Simulator solves this by:
1. Auto-registering default devices if none exist
2. Polling the Catalogue every 60 seconds
3. Discovering all registered sensors and actuators
4. Starting simulators for each device automatically

**Key Features**:
- **Auto-Registration**: If no devices exist, registers default sensor + actuator for garden_1/field_1
- **Auto-Discovery**: Finds new devices without restart
- **Parallel Simulation**: Runs multiple sensors/actuators in parallel threads
- **Simple Code**: Uses basic Python constructs for educational purposes

**Auto-Registration Logic**:
```python
def register_default_devices():
    """Register default devices if none exist."""
    devices = get_devices()
    if len(devices) > 0:
        return  # Devices exist, skip
    
    # Register default sensor and actuator
    default_devices = [
        {"type": "sensor", "garden_id": "garden_1", "field_id": "field_1"},
        {"type": "actuator", "garden_id": "garden_1", "field_id": "field_1"},
    ]
    for device in default_devices:
        requests.post(CATALOGUE_URL + "devices", json=device)
```

**How It Works**:
```
Device Simulator                    Catalogue
       │                               │
       │  GET /devices                 │
       │ ─────────────────────────────►│
       │                               │
       │  [] (empty list)              │
       │ ◄─────────────────────────────│
       │                               │
       │  POST /devices (sensor)       │
       │ ─────────────────────────────►│
       │  POST /devices (actuator)     │
       │ ─────────────────────────────►│
       │                               │
       │  GET /devices                 │
       │ ─────────────────────────────►│
       │                               │
       │  [{"id": "sensor_garden_1_field_1_001", ...}, ...]
       │ ◄─────────────────────────────│
       │                               │
       │  For each device:             │
       │  - Start SensorSimulator thread
       │  - Or ActuatorSimulator thread │
       │                               │
       │  Wait 60 seconds              │
       │  Check for new devices...     │
```

**Classes**:
```python
class SensorSimulator:
    """Simulates a sensor - publishes fake readings every 10 seconds."""
    def __init__(self, device_id, topics, broker, port)
    def publish_readings()  # Publishes soil_moisture + temperature
    def stop()

class ActuatorSimulator:
    """Simulates an actuator - listens for commands, publishes status."""
    def __init__(self, device_id, subscribe_topics, publish_topics, broker, port)
    def notify(topic, payload)  # MQTT callback for commands
    def open_valve(duration)    # Opens valve, schedules auto-close
    def close_valve()           # Closes valve, publishes water usage
    def stop()
```

**Running the Device Simulator**:
```bash
python src/devices/device_simulator.py
```

**Integration with Launcher Scripts**:
The `start.py` launcher script starts the Device Simulator by default:
```bash
python scripts/macos/start.py              # Starts all services + Device Simulator
python scripts/macos/start.py --no-devices # Services only, no Device Simulator
```

**Published Data (SenML format)**:
```json
[
    {"bn": "sensor_garden_1_field_1_001", "n": "soil_moisture", "t": 1703419200.0, "v": 45.2},
    {"bn": "sensor_garden_1_field_1_001", "n": "temperature", "t": 1703419200.0, "v": 22.5}
]
```

---

### 5.6 Service Layer

#### `src/services/catalogue/service.py`

**Purpose**: Central service registry and configuration provider (Service Catalogue pattern).

**Technology**: CherryPy REST framework

**Key Features**:
- **Multi-Garden Support**: Manages multiple gardens with their own fields
- **Dynamic ID Generation**: Automatically assigns unique IDs to new devices
- **Topic Generation**: Creates MQTT topics based on project_info.topic_prefix

**Endpoints**:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Full system configuration |
| GET | `/broker` | MQTT broker details |
| GET | `/devices` | List of all registered devices |
| GET | `/devices/{id}` | Specific device by ID |
| GET | `/settings` | System settings (thresholds, location) |
| GET | `/services` | List of registered services |
| GET | `/gardens` | List all gardens with their fields |
| GET | `/gardens/{garden_id}` | Specific garden config |
| **POST** | `/devices` | Register new device (auto-assigns ID) |
| **POST** | `/gardens` | Add a new garden |
| **PUT** | `/devices/{id}` | Update existing device |
| **DELETE** | `/devices/{id}` | Remove device |

**Dynamic ID Generation**:
```python
def generate_device_id(device_type, garden_id, field_id):
    # Format: {type}_{garden_id}_{field_id}_{counter:03d}
    # Example: "sensor_garden_1_field_1_001"
    
    counter_key = f"{device_type}_{garden_id}_{field_id}"
    counters = config.get('device_counters', {})
    count = counters.get(counter_key, 0) + 1
    return f"{device_type}_{garden_id}_{field_id}_{count:03d}"
```

**Dynamic Registration (POST /devices)**:
```python
# Request body (ID is NOT required - auto-generated):
{
    "type": "sensor",
    "garden_id": "garden_1",
    "field_id": "field_1",
    "name": "Sensor garden_1 field_1"
}

# Response (ID and topics generated by Catalogue):
{
    "status": "registered",
    "id": "sensor_garden_1_field_1_001",
    "topics": {
        "publish": [
            "smart_irrigation/farm/garden_1/field_1/soil_moisture",
            "smart_irrigation/farm/garden_1/field_1/temperature"
        ],
        "subscribe": []
    },
    "garden_id": "garden_1",
    "field_id": "field_1"
}
```

**Topic Generation** (from project_info.topic_prefix):
```python
topic_prefix = config['project_info']['topic_prefix']  # "smart_irrigation"

# For sensors:
topics = {
    "publish": [
        f"{topic_prefix}/farm/{garden_id}/{field_id}/soil_moisture",
        f"{topic_prefix}/farm/{garden_id}/{field_id}/temperature"
    ],
    "subscribe": []
}

# For actuators:
topics = {
    "publish": [
        f"{topic_prefix}/farm/{garden_id}/{field_id}/valve_status",
        f"{topic_prefix}/irrigation/usage"
    ],
    "subscribe": [
        f"{topic_prefix}/farm/{garden_id}/{field_id}/valve_cmd"
    ]
}
```

> **⚠️ Important**: POST registration only creates the device configuration in the Catalogue. To actually run the device (publish sensor data or respond to commands), you must start a Python process:
> ```bash
> # After POST registration for garden_1/field_3:
> python src/devices/sensor_node.py garden_1 field_3
> python src/devices/actuator_node.py garden_1 field_3
> ```
> In a real deployment, each device is a physical microcontroller. The Python scripts simulate these devices.

**Multi-Garden Structure** (in system_config.json):
```json
{
    "gardens": {
        "garden_1": {
            "name": "Main Garden",
            "location": "North Section",
            "fields": {
                "field_1": {
                    "crop_type": "tomato",
                    "field_size_m2": 100.0,
                    "flow_rate_lpm": 20.0
                }
            }
        },
        "garden_2": {
            "name": "Secondary Garden",
            "fields": {
                "field_1": {
                    "crop_type": "lettuce",
                    "field_size_m2": 50.0,
                    "flow_rate_lpm": 15.0
                }
            }
        }
    },
    "device_counters": {}
}
```

**Configuration Source**: Reads from `config/system_config.json`

**Role**: **SERVICE PROVIDER** — All other services consume this API at startup.

---

#### `src/services/water_manager/service.py`

**Purpose**: Core irrigation controller — the "brain" of the system with smart irrigation logic.

**Key Features**:
- **Auto-Discovery**: Automatically discovers new devices from Catalogue
- **Multi-Garden Support**: Manages irrigation across multiple gardens/fields
- **Dynamic Subscriptions**: Subscribes to new sensors as they register

**Responsibilities**:
1. Poll Catalogue for registered devices (every 60 seconds)
2. Auto-subscribe to all sensor data topics
3. Evaluate soil moisture against threshold
4. Check for active rain AND frost alerts
5. Calculate irrigation duration based on crop type and field size
6. Publish valve open/close commands with calculated duration

**Auto-Discovery Logic**:
```python
def _refresh_devices(self):
    """Polls Catalogue every 60 seconds for new devices"""
    while self.running:
        try:
            response = requests.get(f"{self.catalogue_url}/devices")
            new_devices = response.json()
            
            # Find newly registered sensors
            new_sensor_ids = set(d['id'] for d in new_devices if d['type'] == 'sensor')
            current_sensor_ids = set(d['id'] for d in self.devices if d['type'] == 'sensor')
            
            if new_sensor_ids != current_sensor_ids:
                self.devices = new_devices
                self._subscribe_to_sensors()  # Subscribe to new topics
                
        except Exception as e:
            print(f"Device refresh error: {e}")
        
        time.sleep(60)  # Check every 60 seconds
```

**Smart Irrigation Logic**:
```python
# Crop factors (water demand multipliers)
CROP_FACTORS = {
    'tomato': 1.2,    # High water demand
    'lettuce': 0.8,   # Low water demand
    'wheat': 0.6,     # Lower water demand
    'corn': 1.0       # Medium water demand
}

# Calculation formula
water_needed_mm = (TARGET_MOISTURE - current_moisture) * crop_factor
total_liters = water_needed_mm * field_size_m2
duration_sec = total_liters / (flow_rate_lpm / 60)
```

**Decision Logic**:
```
IF moisture < threshold AND NOT rain_alert AND NOT frost_alert THEN
    duration = calculate_irrigation_duration(field_id, moisture)
    OPEN valve for {duration} seconds
ELSE IF moisture < threshold AND (rain_alert OR frost_alert) THEN
    SKIP irrigation (weather alert active)
ELSE
    No action needed
```

**SenML Parsing**:
```python
# Handles list format: [{'bn': '...', 'n': 'soil_moisture', 'v': 25}, ...]
for measurement in data:
    if measurement.get('n') == 'soil_moisture':
        moisture = measurement['v']
```

**Communication**:
- **REST GET** → Catalogue (bootstrap + gardens config + devices)
- **MQTT Subscribe** → `smart_irrigation/farm/{garden_id}/{field_id}/soil_moisture`, `smart_irrigation/weather/alert`, `smart_irrigation/weather/frost`
- **MQTT Publish** → `smart_irrigation/farm/{garden_id}/{field_id}/valve_cmd`

**Command Format**:
```json
{
    "command": "OPEN",
    "duration": 480
}
```

---

#### `src/services/weather_check/service.py`

**Purpose**: Weather monitoring service that polls external forecast API for rain AND frost alerts.

**External API**: Open-Meteo (https://api.open-meteo.com)

**Polling Mechanism**:
- Background thread polls weather API at configurable interval
- Default: every 3600 seconds (1 hour)
- For testing: every 60 seconds

**Rain Alert Logic**:
```
IF precipitation >= rain_threshold_mm AND rain_alert NOT active THEN
    Publish to weather/alert with status=ACTIVE
ELSE IF precipitation < rain_threshold_mm AND rain_alert IS active THEN
    Publish to weather/alert with status=CLEARED
```

**Frost Alert Logic**:
```
IF temperature < frost_threshold_c AND frost_alert NOT active THEN
    Publish to weather/frost with status=ACTIVE
ELSE IF temperature >= frost_threshold_c AND frost_alert IS active THEN
    Publish to weather/frost with status=CLEARED
```

**Configuration**:
```json
{
    "settings": {
        "rain_threshold_mm": 5.0,
        "frost_threshold_c": 2.0
    },
    "topics": {
        "weather_alert": "smart_irrigation/weather/alert",
        "frost_alert": "smart_irrigation/weather/frost"
    }
}
```

**Communication**:
- **REST** → Catalogue (bootstrap)
- **REST** → Open-Meteo API (weather data)
- **MQTT Publish** → `smart_irrigation/weather/alert`, `smart_irrigation/weather/frost`

**Alert Formats**:
```json
// Rain Alert
{
    "alert_type": "RAIN_ALERT",
    "status": "ACTIVE",
    "precipitation_mm": 8.5,
    "t": 1703419200.0
}

// Frost Alert
{
    "alert_type": "FROST_ALERT",
    "status": "ACTIVE",
    "value": -2.5,
    "t": 1703419200.0
}
```

---

#### `src/services/telegram_bot/service.py`

**Purpose**: User notification service via Telegram messaging for weather alerts and system status monitoring.

**Features**:
| Feature | Implementation |
|---------|----------------|
| Weather Alerts | Receives rain/frost alerts via MQTT |
| System Status | Queries Status Service via REST |
| Interactive Menu | Inline keyboard with `/start` command |

**Status Retrieval**:
The Telegram Bot queries the Status Service (port 9090) to display current device states, rather than maintaining its own MQTT subscriptions for all devices.

```python
def show_system_status(self, chat_id):
    res = requests.get(f"{self.status_service_url}")
    status_data = res.json()
    # Format and send to user
```

**Monitored Topics**:
- `weather/alert` — Rain warnings
- `weather/frost` — Frost warnings

**Notification Examples**:
- 🌧️ "RAIN ALERT! Expected: 8.5mm. Irrigation suspended."
- ❄️ "FROST ALERT! Temperature: -2°C. Irrigation suspended."
- ☀️ "Rain alert cleared. Irrigation resumed."

**Communication**:
- **REST** → Catalogue (bootstrap)
- **REST** → Status Service (device status retrieval)
- **REST** → Telegram Bot API (send messages)
- **MQTT Subscribe** → `weather/alert`, `weather/frost`

---

#### `src/services/status/service.py`

**Purpose**: Centralized device status cache with REST API. Subscribes to all device topics and provides unified access to current device states.

**Technology**: CherryPy REST framework (port 9090)

**Features**:
- Subscribes to all device publish topics from Catalogue
- Caches the latest message for each device
- Exposes cached data via REST API
- Periodically checks for new devices (every 60 seconds)

**Initialization Flow**:
1. **Bootstrap via REST GET**: Fetches configuration from Catalogue Service
2. **Subscribe to Device Topics**: Gets all device publish topics from Catalogue
3. **Start Background Thread**: Periodically checks for new device registrations
4. **Expose REST API**: Provides GET endpoint for status retrieval

**REST API**:
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Returns all cached device statuses |

**Response Format**:
```json
{
    "sensor_node_field_1": {
        "topic": "smart_irrigation/farm/field_1/soil_moisture",
        "timestamp": 1703419200.0,
        "received_at": "2026-01-06 10:00:00",
        "payload": [{"bn": "sensor_node_field_1", "n": "soil_moisture", "v": 45.2}]
    }
}
```

**Benefits**:
- Other services can query device status without subscribing to all topics
- Reduces MQTT subscription overhead across services
- Provides a single source of truth for device states
- Enables stateless clients (like Telegram Bot) to access device data

**Communication**:
- **REST GET** → Catalogue (bootstrap + device list)
- **MQTT Subscribe** → All device publish topics
- **REST Provider** → Serves device status to other services

---

#### `src/services/thingspeak_adaptor/service.py`

**Purpose**: Cloud data adaptor for IoT analytics visualization. Uploads sensor data from Field 1 to ThingSpeak.

**Target Platform**: ThingSpeak (https://thingspeak.com)

**Features**:
- Uses **wildcard MQTT subscription** to catch all field_1 data
- Works even when devices register AFTER the adaptor starts
- Parses SenML list format
- Buffers incoming data
- Rate-limited uploads (ThingSpeak requires 15s between updates)

**Wildcard Subscription**: Instead of subscribing to specific device topics (which requires knowing device IDs at startup), the adaptor uses a wildcard topic:
```python
# Subscribes to ALL messages under garden_1/field_1
self.wildcard_topic = "smart_irrigation/farm/garden_1/field_1/#"
```

This ensures data is received even when:
- Devices are registered via POST after the adaptor starts
- New sensors are added dynamically during operation

**Field Scope**: The adaptor focuses on Field 1 data to work within ThingSpeak's free tier limitations (8 fields per channel).

**SenML Parsing**:
```python
# Handles list format from sensors
if isinstance(data, list):
    for measurement in data:
        name = measurement['n']     # e.g., 'soil_moisture', 'water_liters'
        value = measurement['v']    # e.g., 25.5, 10.5
        if name in self.field_map:
            self.buffer[name] = value
```

**Field Mapping**:
```json
{
    "soil_moisture": "field1",
    "temperature": "field2",
    "water_liters": "field3",
    "water_needed": "field4"
}
```

**Communication**:
- **REST** → Catalogue (bootstrap)
- **REST** → ThingSpeak API (data upload)
- **MQTT Subscribe** → `smart_irrigation/farm/garden_1/field_1/#` (wildcard), `smart_irrigation/irrigation/usage`

---

## 6. Service Roles (Provider/Consumer)

This section documents the communication roles of each component based on the architecture diagram.

### 6.1 Legend

| Symbol | Meaning |
|--------|---------|
| **●** | REST Web Services (Provider) - Exposes REST API |
| **➝** | REST Web Services (Consumer) - Calls REST API |
| **(1)** | MQTT Publisher - Publishes messages to broker |
| **(2)** | MQTT Subscriber - Subscribes to messages from broker |
| **- - -** | MQTT Communication (dashed line in diagram) |
| **───** | REST Communication (solid line in diagram) |

### 6.2 Service Provider vs Consumer Matrix

| Component | REST Provider ● | REST Consumer ➝ | MQTT Pub (1) | MQTT Sub (2) |
|-----------|:---------------:|:---------------:|:------------:|:------------:|
| **Catalogue** | ✅ | ❌ | ❌ | ❌ |
| **Water Manager (1,2)** | ❌ | ✅ | ✅ | ✅ |
| **Sensors (1)** | ❌ | ✅ | ✅ | ❌ |
| **Actuators (1,2)** | ❌ | ✅ | ✅ | ✅ |
| **Status Service (2)** | ✅ | ✅ | ❌ | ✅ |
| **Weather Check (1)** | ❌ | ✅ | ✅ | ❌ |
| **ThingSpeak Adaptor (2)** | ❌ | ✅ | ❌ | ✅ |
| **Telegram Bot (2)** | ❌ | ✅ | ❌ | ✅ |

### 6.3 Detailed Role Analysis

#### Pure REST Providers:
- **Catalogue Service**: Central registry providing configuration data and device registration via REST API. All other services bootstrap from this.

#### REST Provider + MQTT Subscriber:
- **Status Service (buffer) (2)**: Provides cached device status via REST (port 9090), subscribes to all device topics via MQTT to maintain the cache.

#### MQTT Publisher Only:
- **Sensors (1)**: Publish sensor readings (soil_moisture, temperature) via MQTT. Consume REST only for registration.
- **Weather Check (1)**: Publishes weather alerts (rain/frost) via MQTT. Consumes REST from Catalogue and Open-Meteo API.

#### MQTT Subscriber Only:
- **ThingSpeak Adaptor (2)**: Subscribes to sensor data via MQTT, uploads to ThingSpeak cloud via REST.
- **Telegram Bot (2)**: Subscribes to weather/frost alerts via MQTT, queries Status Service via REST for device status.

#### Hybrid (Publisher & Subscriber):
- **Water Manager (1,2)**: The "brain" of the system with Control Strategy. Subscribes to sensor data and weather alerts, publishes valve commands.
- **Actuators (1,2)**: Subscribe to valve commands via MQTT, publish valve_status and resource_usage (water_liters) data.

### 6.4 Control Strategy

As shown in the diagram, the **Control Strategy** is integrated within the **Water Manager** service. It:
1. Receives sensor data (MQTT subscriber)
2. Receives weather alerts (MQTT subscriber)
3. Makes irrigation decisions based on:
   - Soil moisture vs threshold
   - Weather conditions (rain/frost)
   - Crop type and field configuration
4. Sends valve commands (MQTT publisher)

### 6.5 Design vs Implementation Verification

The architecture diagram has been updated and now **fully matches the implementation**:

| Component | Diagram | Implementation | Status |
|-----------|---------|----------------|--------|
| **Telegram Bot (2)** | MQTT Sub (2) + REST Consumer | ✅ Same | ✅ Match |
| **Actuators (1,2)** | MQTT Pub/Sub (1,2) + REST Consumer | ✅ Same | ✅ Match |
| **Sensors (1)** | MQTT Publisher (1) + REST Consumer | ✅ Same | ✅ Match |
| **Status Service (2)** | REST Provider (●) + MQTT Sub (2) | ✅ Same | ✅ Match |
| **Weather Check (1)** | MQTT Publisher (1) + REST Consumer | ✅ Same | ✅ Match |
| **ThingSpeak Adaptor (2)** | MQTT Subscriber (2) + REST Consumer | ✅ Same | ✅ Match |
| **Water Manager (1,2)** | MQTT Pub/Sub (1,2) + REST Consumer | ✅ Same | ✅ Match |
| **Catalogue** | REST Provider (●) only | ✅ Same | ✅ Match |

**All components verified ✅** - The diagram accurately represents the system architecture.

---

## 7. Smart Irrigation Logic

### 7.1 Overview

The Water Manager implements smart irrigation based on crop type and field configuration, replacing the previous hardcoded 5-minute duration.

### 7.2 Crop Factors

| Crop | Factor | Water Demand |
|------|--------|--------------|
| Tomato | 1.2 | High |
| Corn | 1.0 | Medium |
| Lettuce | 0.8 | Low |
| Wheat | 0.6 | Lower |

### 7.3 Calculation Formula

```python
TARGET_MOISTURE = 70.0  # Target soil moisture percentage

def calculate_irrigation_duration(field_id, current_moisture):
    # Get field config from Catalogue
    crop_type = field_config.get('crop_type', 'default')
    field_size = field_config.get('field_size_m2', 100)
    flow_rate_lpm = field_config.get('flow_rate_lpm', 20.0)
    
    # Get crop factor
    crop_factor = CROP_FACTORS.get(crop_type, 1.0)
    
    # Calculate moisture deficit
    moisture_deficit = max(0, TARGET_MOISTURE - current_moisture)
    
    # Calculate water needed (mm * m² = liters)
    water_needed_mm = moisture_deficit * crop_factor
    total_liters = water_needed_mm * field_size
    
    # Calculate duration (liters / flow rate)
    flow_rate_lps = flow_rate_lpm / 60.0
    duration_seconds = total_liters / flow_rate_lps
    
    # Clamp to range (min 60s, max 30 min)
    return max(60, min(1800, duration_seconds))
```

### 7.4 Fallback Lookup Table

If field configuration is missing, a simple lookup table is used:

| Crop | Duration |
|------|----------|
| Tomato | 600s (10 min) |
| Corn | 480s (8 min) |
| Lettuce | 300s (5 min) |
| Wheat | 240s (4 min) |

---

## 8. Resource Tracking

### 8.1 Overview

The Actuator Node tracks water consumption when the valve closes. The system uses gravity-fed irrigation from elevated water tanks, eliminating the need for electric pumps.

### 8.2 Constants

```python
FLOW_RATE_LPM = 20.0      # Liters per minute (gravity-fed flow rate)
```

### 8.3 Calculation

```python
def close_valve(self):
    actual_duration = time.time() - self.last_command_time
    
    # Water usage: flow_rate (L/min) * duration (min)
    water_liters = (self.flow_rate * actual_duration) / 60.0
    
    # Publish resource usage
    self.publish_resource_usage(water_liters, actual_duration)
```

### 8.4 Published Data

```json
[
    {"bn": "actuator_valve_1", "n": "water_liters", "t": 1703419200.0, "v": 10.5},
    {"bn": "actuator_valve_1", "n": "duration_sec", "t": 1703419200.0, "v": 120.0}
]
```

### 8.5 ThingSpeak Integration

| Metric | ThingSpeak Field |
|--------|------------------|
| Soil Moisture | field1 |
| Temperature | field2 |
| Water (L) | field3 |
| Water Needed (mm) | field4 |

---

## 9. Data Flow

### 9.1 System Startup Sequence

```
1. Catalogue Service starts → Exposes REST API on port 8080
2. Status Service starts → Exposes REST API on port 9090, subscribes to all device topics
3. Other services start → Each fetches config via GET http://localhost:8080/
4. Actuator Nodes register → POST to http://localhost:8080/devices
5. Services extract:
   - MQTT broker address/port
   - Device configurations
   - Field configurations (crop type, size)
   - Thresholds and settings
6. Services connect to MQTT broker
7. Services subscribe to relevant topics
8. System enters operational mode
```

### 9.2 Smart Irrigation Decision Flow

```
Sensor Node                  Water Manager              Actuator Node
    │                             │                        │
    │ MQTT: [{'n':'soil_moisture',│                        │
    │        'v': 25}]            │                        │
    ├────────────────────────────►│                        │
    │                             │ Check: 25% < 30%?      │
    │                             │ Check: rain_alert?     │
    │                             │ Check: frost_alert?    │
    │                             │                        │
    │                             │ Calculate duration:    │
    │                             │ - crop=tomato (1.2)    │
    │                             │ - deficit=45%          │
    │                             │ - field=100m²          │
    │                             │ - duration=810s        │
    │                             │                        │
    │                             │ MQTT: valve_cmd        │
    │                             │ {"command":"OPEN",     │
    │                             │  "duration":810}       │
    │                             ├───────────────────────►│
    │                             │                        │ Opens valve
    │                             │                        │ ...810 seconds...
    │                             │                        │ Closes valve
    │                             │                        │
    │                             │       MQTT: irrigation/usage
    │                             │◄───────────────────────┤
    │                             │ [{'n':'water_liters',  │
    │                             │   'v':270}]            │
```

### 9.3 Resource Tracking Flow

```
Actuator Node                ThingSpeak Adaptor            ThingSpeak Cloud
    │                             │                             │
    │ Valve closes after 810s     │                             │
    │                             │                             │
    │ MQTT: irrigation/usage      │                             │
    │ [{'n':'water_liters','v':270},                            │
    │  {'n':'duration_sec','v':810}]                            │
    ├────────────────────────────►│                             │
    │                             │ Parse SenML list            │
    │                             │ Buffer: water=270           │
    │                             │                             │
    │                             │ REST: ThingSpeak API        │
    │                             │ ?field3=270                 │
    │                             ├────────────────────────────►│
    │                             │                             │ Stores data
```

### 9.4 Weather Alert Flow (Rain + Frost)

```
Open-Meteo API           Weather Check           Water Manager          Telegram Bot
      │                       │                        │                      │
      │ REST: forecast        │                        │                      │
      │◄──────────────────────│                        │                      │
      │ precipitation=8.5mm   │                        │                      │
      │ temperature=-2°C      │                        │                      │
      ├──────────────────────►│                        │                      │
      │                       │                        │                      │
      │                       │ MQTT: weather/alert    │                      │
      │                       │ {status:ACTIVE,        │                      │
      │                       │  precipitation:8.5}    │                      │
      │                       ├───────────────────────►│                      │
      │                       │                        │ rain_alert=true      │
      │                       │                        │                      │
      │                       │ MQTT: weather/frost    │                      │
      │                       │ {status:ACTIVE,        │                      │
      │                       │  value:-2}             │                      │
      │                       ├───────────────────────►│                      │
      │                       │                        │ frost_alert=true     │
      │                       │                        │                      │
      │                       │ MQTT: weather/alert    │                      │
      │                       ├────────────────────────┼─────────────────────►│
      │                       │                        │                      │ 🌧️ notification
      │                       │                        │                      │
      │                       │ MQTT: weather/frost    │                      │
      │                       ├────────────────────────┼─────────────────────►│
      │                       │                        │                      │ ❄️ notification
```

---

## 10. Configuration

### 10.1 System Configuration (`config/system_config.json`)

```json
{
    "project_info": {
        "name": "Smart Precision Irrigation System",
        "version": "2.0",
        "topic_prefix": "smart_irrigation"
    },
    "broker": {
        "address": "broker.hivemq.com",
        "port": 1883,
        "port_tls": 8883,
        "port_websocket": 8000,
        "port_websocket_tls": 8884
    },
    "topics": {
        "weather_alert": "smart_irrigation/weather/alert",
        "frost_alert": "smart_irrigation/weather/frost",
        "irrigation_command": "smart_irrigation/irrigation/+/command",
        "valve_status": "smart_irrigation/irrigation/+/status",
        "resource_usage": "smart_irrigation/irrigation/usage"
    },
    "settings": {
        "lat": 45.06,
        "lon": 7.66,
        "rain_threshold_mm": 5.0,
        "frost_threshold_c": 2.0,
        "moisture_threshold": 30.0
    },
    "telegram": {
        "token": "YOUR_BOT_TOKEN_HERE",
        "chat_ids": []
    },
    "thingspeak": {
        "channel_id": "YOUR_CHANNEL_ID",
        "write_api_key": "YOUR_WRITE_API_KEY",
        "field_map": {
            "soil_moisture": "field1",
            "temperature": "field2",
            "water_liters": "field3",
            "water_needed": "field4"
        }
    },
    "gardens": {
        "garden_1": {
            "name": "Main Garden",
            "location": "North Section",
            "fields": {
                "field_1": {
                    "crop_type": "tomato",
                    "field_size_m2": 100.0,
                    "water_need_mm_per_day": 5.0,
                    "flow_rate_lpm": 20.0
                },
                "field_2": {
                    "crop_type": "lettuce",
                    "field_size_m2": 50.0,
                    "water_need_mm_per_day": 4.0,
                    "flow_rate_lpm": 15.0
                }
            }
        },
        "garden_2": {
            "name": "Secondary Garden",
            "location": "South Section",
            "fields": {
                "field_1": {
                    "crop_type": "wheat",
                    "field_size_m2": 200.0,
                    "water_need_mm_per_day": 3.0,
                    "flow_rate_lpm": 25.0
                }
            }
        }
    },
    "device_counters": {},
    "devices": []
}
```

### 10.2 Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `project_info.topic_prefix` | Base prefix for all MQTT topics | smart_irrigation |
| `broker.address` | MQTT broker hostname | broker.hivemq.com |
| `broker.port` | MQTT broker port | 1883 |
| `broker.port_tls` | MQTT TLS port | 8883 |
| `settings.moisture_threshold` | Irrigation trigger level (%) | 30.0 |
| `settings.rain_threshold_mm` | Rain alert trigger (mm) | 5.0 |
| `settings.frost_threshold_c` | Frost alert trigger (°C) | 2.0 |
| `settings.lat`, `settings.lon` | Location for weather API | 45.06, 7.66 |
| `gardens.*.name` | Human-readable garden name | "Main Garden" |
| `gardens.*.fields.*.crop_type` | Crop type for smart irrigation | tomato, wheat, etc. |
| `gardens.*.fields.*.field_size_m2` | Field size in square meters | 100 |
| `gardens.*.fields.*.flow_rate_lpm` | Water flow rate (L/min) | 20.0 |
| `device_counters` | Auto-generated counters for device IDs | {} (managed by Catalogue) |
| `devices` | List of registered devices | [] (populated at runtime) |

### 10.3 Multi-Garden Structure

The `gardens` object provides a hierarchical structure for managing multiple gardens:

```
gardens
├── garden_1
│   ├── name: "Main Garden"
│   ├── location: "North Section"
│   └── fields
│       ├── field_1 (tomato, 100m², 20 LPM)
│       └── field_2 (lettuce, 50m², 15 LPM)
│
└── garden_2
    ├── name: "Secondary Garden"
    ├── location: "South Section"
    └── fields
        └── field_1 (wheat, 200m², 25 LPM)
```

**Device ID Assignment**:
- IDs are auto-generated when devices register via POST
- Format: `{type}_{garden_id}_{field_id}_{counter:03d}`
- Example: `sensor_garden_1_field_1_001`, `actuator_garden_2_field_1_001`

**Topic Generation**:
- Topics are auto-generated using `project_info.topic_prefix`
- Format: `{topic_prefix}/farm/{garden_id}/{field_id}/{data_type}`
- Example: `smart_irrigation/farm/garden_1/field_1/soil_moisture`

---

## 11. MQTT Topics

### 11.1 Topic Hierarchy

Topics are dynamically generated using `project_info.topic_prefix` from configuration.

```
{topic_prefix}/
├── farm/
│   ├── {garden_id}/
│   │   ├── {field_id}/
│   │   │   ├── soil_moisture    # Sensor data (SenML list)
│   │   │   ├── temperature      # Sensor data (SenML list)
│   │   │   ├── valve_cmd        # Commands to actuator
│   │   │   ├── valve_status     # Actuator feedback (SenML list)
│   │   │   └── config           # Configuration updates
│   │   └── ...
│   └── ...
│
├── weather/
│   ├── alert                    # Rain alerts
│   └── frost                    # Frost alerts
│
└── irrigation/
    └── usage                    # Resource usage (water consumption)
```

**Example Topics** (with `topic_prefix: "smart_irrigation"`):
```
smart_irrigation/farm/garden_1/field_1/soil_moisture
smart_irrigation/farm/garden_1/field_1/valve_cmd
smart_irrigation/farm/garden_2/field_1/valve_status
smart_irrigation/weather/alert
smart_irrigation/irrigation/usage
```

### 11.2 Topic Definitions

| Topic Pattern | Publisher | Subscriber | Payload Format | QoS |
|-------|-----------|------------|----------------|-----|
| `{prefix}/farm/{garden}/{field}/soil_moisture` | Sensor Node | Water Manager, Status Service, ThingSpeak | SenML list | 0 |
| `{prefix}/farm/{garden}/{field}/temperature` | Sensor Node | Status Service, ThingSpeak | SenML list | 0 |
| `{prefix}/farm/{garden}/{field}/valve_cmd` | Water Manager | Actuator | Command JSON | 0 |
| `{prefix}/farm/{garden}/{field}/valve_status` | Actuator | Status Service | SenML list | 0 |
| `{prefix}/weather/alert` | Weather Check | Water Manager, Telegram | Alert JSON | 1 |
| `{prefix}/weather/frost` | Weather Check | Water Manager, Telegram | Alert JSON | 1 |
| `{prefix}/irrigation/usage` | Actuator | Status Service, ThingSpeak | SenML list | 0 |

### 11.3 Message Formats

**Sensor Data (SenML List)**:
```json
[
    {"bn": "sensor_garden_1_field_1_001", "n": "soil_moisture", "t": 1703419200.0, "v": 25.5},
    {"bn": "sensor_garden_1_field_1_001", "n": "temperature", "t": 1703419200.0, "v": 22.1}
]
```

**Valve Command**:
```json
{"command": "OPEN", "duration": 480}
```

**Weather Alert**:
```json
{"alert_type": "RAIN_ALERT", "status": "ACTIVE", "precipitation_mm": 8.5, "t": 1703419200.0}
```

**Frost Alert**:
```json
{"alert_type": "FROST_ALERT", "status": "ACTIVE", "value": -2.5, "t": 1703419200.0}
```

**Resource Usage (SenML List)**:
```json
[
    {"bn": "actuator_garden_1_field_1_001", "n": "water_liters", "t": 1703419200.0, "v": 10.5},
    {"bn": "actuator_garden_1_field_1_001", "n": "duration_sec", "t": 1703419200.0, "v": 120.0}
]
```

---

## 12. REST API Endpoints

### 12.1 Catalogue Service API

**Base URL**: `http://localhost:8080`

#### GET /
Returns the complete system configuration.

**Response**:
```json
{
    "project_info": {...},
    "broker": {...},
    "topics": {...},
    "settings": {...},
    "gardens": {...},
    "telegram": {...},
    "thingspeak": {...},
    "device_counters": {...},
    "devices": [...]
}
```

#### GET /broker
Returns MQTT broker connection details.

**Response**:
```json
{
    "address": "broker.hivemq.com",
    "port": 1883,
    "port_tls": 8883,
    "port_websocket": 8000,
    "port_websocket_tls": 8884
}
```

#### GET /gardens
Returns all gardens with their fields.

**Response**:
```json
{
    "garden_1": {
        "name": "Main Garden",
        "location": "North Section",
        "fields": {
            "field_1": {
                "crop_type": "tomato",
                "field_size_m2": 100.0,
                "flow_rate_lpm": 20.0
            }
        }
    },
    "garden_2": {...}
}
```

#### GET /gardens/{garden_id}
Returns a specific garden configuration.

**Response**:
```json
{
    "name": "Main Garden",
    "location": "North Section",
    "fields": {
        "field_1": {...},
        "field_2": {...}
    }
}
```

#### POST /gardens
Add a new garden.

**Request Body**:
```json
{
    "garden_id": "garden_3",
    "name": "New Garden",
    "location": "East Section",
    "fields": {
        "field_1": {
            "crop_type": "corn",
            "field_size_m2": 150.0,
            "flow_rate_lpm": 18.0
        }
    }
}
```

#### GET /devices
Returns list of registered devices.

**Response**:
```json
[
    {
        "id": "sensor_garden_1_field_1_001",
        "name": "Sensor garden_1 field_1",
        "type": "sensor",
        "garden_id": "garden_1",
        "field_id": "field_1",
        "topics": {...}
    }
]
```

#### GET /devices/{id}
Returns a specific device by ID.

**Response**:
```json
{
    "id": "actuator_garden_1_field_1_001",
    "name": "Actuator garden_1 field_1",
    "type": "actuator",
    "garden_id": "garden_1",
    "field_id": "field_1",
    "topics": {...}
}
```

#### POST /devices
Register a new device (ID auto-generated).

**Request Body** (ID NOT required):
```json
{
    "type": "sensor",
    "garden_id": "garden_1",
    "field_id": "field_1",
    "name": "Sensor garden_1 field_1"
}
```

**Response** (ID and topics auto-generated):
```json
{
    "status": "registered",
    "id": "sensor_garden_1_field_1_001",
    "topics": {
        "publish": [
            "smart_irrigation/farm/garden_1/field_1/soil_moisture",
            "smart_irrigation/farm/garden_1/field_1/temperature"
        ],
        "subscribe": []
    },
    "garden_id": "garden_1",
    "field_id": "field_1"
}
```

#### PUT /devices/{id}
Update an existing device.

**Request Body**:
```json
{
    "name": "Updated Valve Name",
    "topics": {...}
}
```

**Response**:
```json
{"status": "updated", "id": "actuator_valve_1"}
```

#### DELETE /devices/{id}
Remove a device from the registry.

**Response**:
```json
{"status": "deleted", "id": "actuator_valve_1"}
```

#### GET /settings
Returns system settings and thresholds.

**Response**:
```json
{
    "lat": 45.06,
    "lon": 7.66,
    "rain_threshold_mm": 5.0,
    "frost_threshold_c": 2.0,
    "moisture_threshold": 30.0
}
```

#### GET /fields
Returns field configurations for smart irrigation.

**Response**:
```json
{
    "field_1": {
        "crop_type": "tomato",
        "field_size_m2": 100,
        "flow_rate_lpm": 20.0
    }
}
```

### 12.2 Status Service API

**Base URL**: `http://localhost:9090`

**Key Feature**: **Smart Payload Merging** - When multiple measurements from the same device arrive (e.g., soil_moisture and temperature from the same sensor), the Status Service merges them into a single payload instead of overwriting. This ensures the Telegram Bot can display all measurements for a device.

#### GET /
Returns all cached device statuses.

**Response** (with merged payloads):
```json
{
    "sensor_garden_1_field_1_001": {
        "topic": "smart_irrigation/farm/garden_1/field_1/temperature",
        "timestamp": 1703419200.0,
        "received_at": "2026-01-06 10:00:00",
        "payload": [
            {"bn": "sensor_garden_1_field_1_001", "n": "soil_moisture", "t": 1703419200.0, "v": 45.2},
            {"bn": "sensor_garden_1_field_1_001", "n": "temperature", "t": 1703419200.0, "v": 22.5}
        ]
    },
    "actuator_garden_1_field_1_001": {
        "topic": "smart_irrigation/farm/garden_1/field_1/valve_status",
        "timestamp": 1703419210.0,
        "received_at": "2026-01-06 10:00:10",
        "payload": [{"bn": "actuator_garden_1_field_1_001", "n": "valve_status", "vs": "OPEN"}]
    }
}
```

**Payload Merging Logic**:
```python
# When new measurement arrives for existing device:
# 1. Get existing payload (if any)
# 2. Create dict of measurements by name
# 3. Update with new measurement (overwrites same name)
# 4. Convert back to list
```

### 12.3 External APIs Used

| API | Base URL | Purpose |
|-----|----------|---------|
| Open-Meteo | `https://api.open-meteo.com/v1/forecast` | Weather forecasts (rain + frost) |
| ThingSpeak | `https://api.thingspeak.com/update` | Cloud data upload |
| Telegram | `https://api.telegram.org/bot{token}` | User notifications |

---

## 13. Services Port Reference

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| Catalogue Service | 8080 | HTTP/REST | Configuration and device registry |
| Status Service | 9090 | HTTP/REST | Cached device status API |
| MQTT Broker | 1883 | MQTT | Message broker (HiveMQ) |
| MQTT TLS | 8883 | MQTT/TLS | Secure MQTT connection |
| MQTT WebSocket | 8000 | WebSocket | WebSocket MQTT connection |

---

## 14. Dependencies

### Python Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `paho-mqtt` | ≥1.6.1 | MQTT client library |
| `requests` | ≥2.31.0 | HTTP client for REST APIs |
| `cherrypy` | — | REST API framework (Catalogue, Status Service) |
| `telepot` | — | Telegram Bot integration |
| `pandas` | ≥2.0.0 | Data processing (optional) |
| `numpy` | ≥1.24.0 | Numerical operations |

---

## 15. Running the System

### Automated Launcher Scripts

The system includes Python launcher scripts located in the `scripts/` directory that automatically open each service in a separate terminal window.

```
scripts/
├── README.md           # Launcher documentation
├── macos/
│   ├── start.py        # Start all services (macOS)
│   └── stop.py         # Stop all services (macOS)
└── windows/
    ├── start.py        # Start all services (Windows)
    └── stop.py         # Stop all services (Windows)
```

#### macOS

```bash
# Start all services and devices
python scripts/macos/start.py

# Start services only (no sensors/actuators)
python scripts/macos/start.py --no-devices

# Stop all services
python scripts/macos/stop.py
python scripts/macos/stop.py --force  # Without confirmation
```

#### Windows

```bash
# Start all services and devices (Command Prompt)
python scripts\windows\start.py

# Start services only
python scripts\windows\start.py --no-devices

# Use PowerShell instead of Command Prompt
python scripts\windows\start.py --powershell

# Stop all services
python scripts\windows\stop.py
python scripts\windows\stop.py --force  # Without confirmation
```

#### Launcher Script Features

| Feature | Description |
|---------|-------------|
| Auto-detect Python | Finds virtual environment or system Python |
| Ordered Startup | Services start in correct dependency order |
| Startup Delays | Waits between services for proper initialization |
| Named Windows | Each terminal window has a descriptive title |
| Service URLs | Displays useful URLs after startup |

### Manual Startup Order

If you prefer to start services manually:

1. **Catalogue Service** (must start first)
   ```bash
   python src/services/catalogue/service.py
   ```

2. **Status Service**
   ```bash
   python src/services/status/service.py
   ```

3. **Weather Check Service**
   ```bash
   python src/services/weather_check/service.py
   ```

4. **Water Manager Service**
   ```bash
   python src/services/water_manager/service.py
   ```

5. **Telegram Bot Service**
   ```bash
   python src/services/telegram_bot/service.py
   ```

6. **ThingSpeak Adaptor**
   ```bash
   python src/services/thingspeak_adaptor/service.py
   ```

7. **Sensor Nodes** (specify garden_id and field_id)
   ```bash
   python src/devices/sensor_node.py garden_1 field_1
   ```

8. **Actuator Nodes** (specify garden_id and field_id)
   ```bash
   python src/devices/actuator_node.py garden_1 field_1
   ```

---

## 16. Summary

The Smart Precision Irrigation System demonstrates a well-architected IoT platform that:

1. **Uses REST for Configuration**: The Catalogue Service provides a central source of truth with full CRUD operations
2. **Uses MQTT for Real-time Data**: Efficient pub/sub for sensor readings and commands using SenML format
3. **Follows Microservices Pattern**: Each service has a single responsibility
4. **Implements Service Discovery**: All services bootstrap from the Catalogue
5. **Implements Dynamic Registration**: Devices self-register via POST and receive auto-generated IDs
6. **Supports Multi-Garden Architecture**: Multiple gardens with independent field configurations
7. **Implements Auto-Discovery**: Water Manager automatically discovers new devices every 60 seconds
8. **Integrates External APIs**: Weather forecasting (rain + frost) and cloud analytics
9. **Provides Smart Irrigation**: Crop-type and field-size based duration calculation
10. **Tracks Resources**: Water consumption (L) per irrigation cycle
11. **Provides Weather Alerts**: Telegram bot notifications for rain and frost alerts

### Design Highlights

- **Gravity-Fed Irrigation**: Uses elevated water tanks for energy-efficient water delivery
- **Multi-Garden Support**: Scalable architecture for multiple gardens and fields
- **Dynamic IDs**: Format: `{type}_{garden_id}_{field_id}_{counter:03d}`
- **Auto-Discovery**: Water Manager polls Catalogue every 60s for new devices
- **Automated Launcher**: Python scripts to start/stop all services automatically
- **Weather-Aware Control**: Automatic irrigation suspension during rain or frost conditions

The combination of REST and MQTT protocols provides the ideal balance between:
- **Reliability**: REST for critical configuration and registration
- **Efficiency**: MQTT for high-frequency sensor data
- **Scalability**: Decoupled services via message broker
- **Intelligence**: Smart irrigation logic based on agricultural needs

---

*Document Version: 2.2*  
*Last Updated: January 2026*  
*System Version: 2.2*

