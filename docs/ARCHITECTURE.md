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

---

## 1. System Overview

The **Smart Precision Irrigation System** is an IoT-based microservices platform for smart agriculture. It uses a combination of **REST APIs** and **MQTT messaging** to orchestrate sensor data collection, intelligent decision-making, and actuator control.

### Key Objectives:
- **Smart Water Management**: Irrigate based on crop type, field size, and moisture deficit
- **Weather-Aware**: Cancel irrigation if rain OR frost is predicted
- **Resource Tracking**: Monitor water (L) and energy (kWh) consumption per cycle
- **Real-time Monitoring**: Telegram notifications with interactive controls
- **Cloud Analytics**: ThingSpeak integration for sensor and usage data visualization
- **Dynamic Registration**: Devices register via REST POST (no hardcoding)

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLOUD LAYER                                        │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐              │
│  │   Open-Meteo    │    │   ThingSpeak    │    │    Telegram     │              │
│  │   Weather API   │    │   Cloud IoT     │    │    Bot API      │              │
│  └────────▲────────┘    └────────▲────────┘    └────────▲────────┘              │
│           │ REST                 │ REST                 │ REST                  │
└───────────┼──────────────────────┼──────────────────────┼───────────────────────┘
            │                      │                      │
┌───────────┼──────────────────────┼──────────────────────┼───────────────────────┐
│           │              SERVICE LAYER (Gateway)        │                        │
│  ┌────────┴────────┐    ┌────────┴────────┐    ┌───────┴─────────┐              │
│  │  Weather Check  │    │ThingSpeak Adaptor│   │   Telegram Bot  │              │
│  │    Service      │    │     Service      │    │     Service     │              │
│  └────────┬────────┘    └────────▲────────┘    └────────▲────────┘              │
│           │ MQTT                 │ MQTT                 │ MQTT                  │
│           ▼                      │                      │                       │
│  ┌─────────────────────────────────────────────────────────────────────┐        │
│  │                        MQTT BROKER                                   │        │
│  │                    (test.mosquitto.org:1883)                         │        │
│  └───────────────────────────────▲─────────────────────────────────────┘        │
│                                  │                                              │
│  ┌────────┬──────────────────────┼──────────────────────┬────────┐              │
│  │        │ MQTT                 │ MQTT                 │ MQTT   │              │
│  │        ▼                      ▼                      ▼        │              │
│  │  ┌───────────┐         ┌───────────────┐      ┌───────────┐   │              │
│  │  │Water      │◄────────│  Catalogue    │◄─────│  Sensor   │   │              │
│  │  │Manager    │  REST   │   Service     │ REST │   Node    │   │              │
│  │  │(Controller)│        │  (Registry)   │      │           │   │              │
│  │  └─────┬─────┘         └───────────────┘      └───────────┘   │              │
│  │        │ MQTT                   ▲                             │              │
│  │        ▼                        │ REST                        │              │
│  │  ┌───────────┐                  │                             │              │
│  │  │ Actuator  │◄─────────────────┘                             │              │
│  │  │ (Valve)   │                                                │              │
│  │  └───────────┘                                                │              │
│  └───────────────────────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────────┘
            │
┌───────────┴─────────────────────────────────────────────────────────────────────┐
│                              EDGE LAYER                                         │
│  ┌─────────────────┐                        ┌─────────────────┐                 │
│  │  Raspberry Pi   │                        │  Raspberry Pi   │                 │
│  │   Pico 2 W      │                        │   Pico 2 W      │                 │
│  │ (Sensor Node)   │                        │ (Actuator Node) │                 │
│  │                 │                        │                 │                 │
│  │ • Soil Moisture │                        │ • Solenoid Valve│                 │
│  │ • Temperature   │                        │ • Water Pump    │                 │
│  └─────────────────┘                        └─────────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

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

---

## 4. SenML Message Format

All MQTT messages in this system follow the **SenML (Sensor Markup Language)** format as per course standards.

### 4.1 Format Specification

| Field | Description | Example |
|-------|-------------|---------|
| `bn` | Base Name (device ID) | `"sensor_node_field_1"` |
| `n` | Measurement Name | `"soil_moisture"` |
| `t` | Timestamp (Unix epoch) | `1703419200.0` |
| `v` | Value (single value, NOT nested) | `25.5` |

### 4.2 Important Rules

1. **Always a List**: Messages are wrapped in an array `[...]`, even for single measurements
2. **Single Value**: The `v` field contains a single value, NOT a nested dictionary
3. **Separate Objects**: Each measurement type is a separate object in the list

### 4.3 Example

```json
[
    {"bn": "sensor_node_field_1", "n": "soil_moisture", "t": 1703419200.0, "v": 25.5},
    {"bn": "sensor_node_field_1", "n": "temperature", "t": 1703419200.0, "v": 22.1}
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

### 5.2 Device Layer

#### `src/devices/base_device.py`

**Purpose**: Abstract base class for all IoT devices.

**Attributes**:
- `device_id`: Unique identifier
- `device_type`: Type classification (sensor/actuator)
- `is_running`: Operational status flag

**Methods**:
- `start()`: Activate the device
- `stop()`: Deactivate the device
- `get_status()`: Return current device state

---

#### `src/devices/sensor_node.py`

**Purpose**: Simulates a soil moisture and temperature sensor node.

**Initialization Flow**:
1. **Bootstrap via REST**: Fetches configuration from Catalogue Service
2. **Extract MQTT Broker**: Gets broker address and port
3. **Find Device Config**: Locates its own publish topics from device list
4. **Start MQTT Client**: Connects to broker for publishing

**Data Format (SenML List)**:
```json
[
    {"bn": "sensor_node_field_1", "n": "soil_moisture", "t": 1703419200.0, "v": 45.2},
    {"bn": "sensor_node_field_1", "n": "temperature", "t": 1703419200.0, "v": 22.5}
]
```

> **Note**: Each measurement is a separate object in the list with a single `v` value (not nested dict).

**Communication**:
- **REST** → Catalogue (bootstrap, one-time)
- **MQTT Publish** → `farm/field_X/soil_moisture`, `farm/field_X/temperature`

---

### 5.3 Actuator Layer

#### `src/devices/actuator_node.py`

**Purpose**: Controls solenoid valves and water pump. Tracks resource consumption.

**Initialization Flow**:
1. **Bootstrap via REST**: Fetches configuration from Catalogue Service
2. **Register via POST**: Registers itself with the Catalogue dynamically
3. **Extract Field Config**: Gets flow rate from field configuration
4. **Start MQTT Client**: Connects to broker for command subscription

**Key Constants**:
```python
FLOW_RATE_LPM = 20.0      # Liters per minute
PUMP_POWER_KW = 0.75      # Pump power in kilowatts
```

**Command Handling**:
```python
def notify(self, topic, payload):
    # Receives: {"command": "OPEN", "duration": 300}
    if command == 'OPEN':
        self.open_valve(duration)
    elif command == 'CLOSE':
        self.close_valve()
```

**Resource Calculation (on valve close)**:
```python
water_liters = (flow_rate * duration_sec) / 60.0
energy_kwh = (PUMP_POWER_KW * duration_sec) / 3600.0
```

**Published Data (SenML List)**:
```json
[
    {"bn": "actuator_valve_1", "n": "water_liters", "t": 1703419200.0, "v": 10.5},
    {"bn": "actuator_valve_1", "n": "energy_kwh", "t": 1703419200.0, "v": 0.05},
    {"bn": "actuator_valve_1", "n": "duration_sec", "t": 1703419200.0, "v": 120.0}
]
```

**Communication**:
- **REST GET** → Catalogue (bootstrap)
- **REST POST** → Catalogue (registration + heartbeat)
- **MQTT Subscribe** → `farm/field_X/valve_cmd`
- **MQTT Publish** → `farm/field_X/valve_status`, `irrigation/usage`

---

### 5.4 Service Layer

#### `src/services/catalogue/service.py`

**Purpose**: Central service registry and configuration provider (Service Catalogue pattern).

**Technology**: CherryPy REST framework

**Endpoints**:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Full system configuration |
| GET | `/broker` | MQTT broker details |
| GET | `/devices` | List of all registered devices |
| GET | `/devices/{id}` | Specific device by ID |
| GET | `/settings` | System settings (thresholds, location) |
| GET | `/services` | List of registered services |
| **POST** | `/devices` | Register new device or heartbeat |
| **PUT** | `/devices/{id}` | Update existing device |
| **DELETE** | `/devices/{id}` | Remove device |

**Dynamic Registration (POST /devices)**:
```python
# Request body:
{
    "id": "actuator_valve_1",
    "name": "Field 1 Valve",
    "type": "actuator",
    "topics": {
        "subscribe": ["farm/field_1/valve_cmd"],
        "publish": ["farm/field_1/valve_status"]
    }
}

# Response:
{"status": "registered", "id": "actuator_valve_1"}
# or if exists:
{"status": "heartbeat", "id": "actuator_valve_1"}
```

**Configuration Source**: Reads from `config/system_config.json`

**Role**: **SERVICE PROVIDER** — All other services consume this API at startup.

---

#### `src/services/water_manager/service.py`

**Purpose**: Core irrigation controller — the "brain" of the system with smart irrigation logic.

**Responsibilities**:
1. Subscribe to all sensor data topics
2. Evaluate soil moisture against threshold
3. Check for active rain AND frost alerts
4. Calculate irrigation duration based on crop type and field size
5. Publish valve open/close commands with calculated duration

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
- **REST** → Catalogue (bootstrap + field config)
- **MQTT Subscribe** → `farm/field_X/soil_moisture`, `weather/alert`, `weather/frost`
- **MQTT Publish** → `farm/field_X/valve_cmd`

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
        "weather_alert": "weather/alert",
        "frost_alert": "weather/frost"
    }
}
```

**Communication**:
- **REST** → Catalogue (bootstrap)
- **REST** → Open-Meteo API (weather data)
- **MQTT Publish** → `weather/alert`, `weather/frost`

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

**Purpose**: User notification and control service via Telegram messaging with interactive UI.

**Interactive Features**:
| Feature | Implementation |
|---------|----------------|
| Inline Keyboard Buttons | `InlineKeyboardMarkup` with buttons |
| Callback Query Handler | `on_callback_query()` method |
| View Sensors | `menu_sensors` → `show_sensor_detail()` |
| Control Actuators | `menu_actuators` → `send_actuator_command()` |
| Main Menu Navigation | `main_menu`, `Back` buttons |
| MQTT Command Publishing | Sends `OPEN`/`CLOSE` commands |

**SenML Display**:
```python
# Parses list format for display
if isinstance(data, list):
    for measurement in data:
        name = measurement.get('n', 'unknown')
        val = measurement.get('v', 'N/A')
        lines.append(f"  {name}: **{val}**")
```

**Monitored Topics**:
- `weather/alert` — Rain warnings
- `weather/frost` — Frost warnings
- `farm/field_X/soil_moisture` — Sensor data caching

**Notification Examples**:
- 🌧️ "RAIN ALERT! Expected: 8.5mm. Irrigation suspended."
- ❄️ "FROST ALERT! Temperature: -2°C. Irrigation suspended."
- ☀️ "Rain alert cleared. Irrigation resumed."

**Communication**:
- **REST** → Catalogue (bootstrap)
- **REST** → Telegram Bot API (send messages)
- **MQTT Subscribe** → `weather/alert`, `weather/frost`, `farm/+/soil_moisture`
- **MQTT Publish** → `farm/field_X/valve_cmd`

---

#### `src/services/thingspeak_adaptor/service.py`

**Purpose**: Cloud data adaptor for IoT analytics visualization. Uploads sensor data AND resource usage.

**Target Platform**: ThingSpeak (https://thingspeak.com)

**Features**:
- Subscribes to all sensor topics AND resource usage topic
- Parses SenML list format
- Buffers incoming data
- Rate-limited uploads (ThingSpeak requires 15s between updates)

**SenML Parsing**:
```python
# Handles list format from sensors and actuators
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
    "energy_kwh": "field4"
}
```

**Communication**:
- **REST** → Catalogue (bootstrap)
- **REST** → ThingSpeak API (data upload)
- **MQTT Subscribe** → `farm/field_X/soil_moisture`, `farm/field_X/temperature`, `irrigation/usage`

---

## 6. Service Roles (Provider/Consumer)

### Service Provider vs Consumer Matrix

| Component | REST Provider | REST Consumer | MQTT Publisher | MQTT Subscriber |
|-----------|:-------------:|:-------------:|:--------------:|:---------------:|
| **Catalogue Service** | ✅ | ❌ | ❌ | ❌ |
| **Sensor Node** | ❌ | ✅ | ✅ | ❌ |
| **Actuator Node** | ❌ | ✅ (POST) | ✅ | ✅ |
| **Water Manager** | ❌ | ✅ | ✅ | ✅ |
| **Weather Check** | ❌ | ✅ | ✅ | ❌ |
| **Telegram Bot** | ❌ | ✅ | ✅ | ✅ |
| **ThingSpeak Adaptor** | ❌ | ✅ | ❌ | ✅ |

### Detailed Role Analysis

#### Pure Service Providers:
- **Catalogue Service**: Provides configuration data and device registration via REST API

#### Pure Service Consumers:
- **ThingSpeak Adaptor**: Only consumes data (MQTT) and forwards to cloud

#### Hybrid (Provider & Consumer):
- **Water Manager**: Consumes sensor data, provides valve commands
- **Weather Check**: Consumes external API, provides alerts (rain + frost)
- **Sensor Node**: Consumes config, provides sensor readings
- **Actuator Node**: Consumes commands, provides status + resource usage
- **Telegram Bot**: Consumes alerts + sensor data, provides user commands

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

The Actuator Node tracks water consumption and energy usage when the valve closes.

### 8.2 Constants

```python
FLOW_RATE_LPM = 20.0      # Liters per minute
PUMP_POWER_KW = 0.75      # Pump power in kilowatts
```

### 8.3 Calculation

```python
def close_valve(self):
    actual_duration = time.time() - self.last_command_time
    
    # Water usage: flow_rate (L/min) * duration (min)
    water_liters = (self.flow_rate * actual_duration) / 60.0
    
    # Energy usage: power (kW) * duration (hours)
    energy_kwh = (PUMP_POWER_KW * actual_duration) / 3600.0
    
    # Publish resource usage
    self.publish_resource_usage(water_liters, energy_kwh, actual_duration)
```

### 8.4 Published Data

```json
[
    {"bn": "actuator_valve_1", "n": "water_liters", "t": 1703419200.0, "v": 10.5},
    {"bn": "actuator_valve_1", "n": "energy_kwh", "t": 1703419200.0, "v": 0.05},
    {"bn": "actuator_valve_1", "n": "duration_sec", "t": 1703419200.0, "v": 120.0}
]
```

### 8.5 ThingSpeak Integration

| Metric | ThingSpeak Field |
|--------|------------------|
| Soil Moisture | field1 |
| Temperature | field2 |
| Water (L) | field3 |
| Energy (kWh) | field4 |

---

## 9. Data Flow

### 9.1 System Startup Sequence

```
1. Catalogue Service starts → Exposes REST API on port 8080
2. Other services start → Each fetches config via GET http://localhost:8080/
3. Actuator Nodes register → POST to http://localhost:8080/devices
4. Services extract:
   - MQTT broker address/port
   - Device configurations
   - Field configurations (crop type, size)
   - Thresholds and settings
5. Services connect to MQTT broker
6. Services subscribe to relevant topics
7. System enters operational mode
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
    │  {'n':'energy_kwh','v':0.17}]│                            │
    ├────────────────────────────►│                             │
    │                             │ Parse SenML list            │
    │                             │ Buffer: water=270, energy=0.17
    │                             │                             │
    │                             │ REST: ThingSpeak API        │
    │                             │ ?field3=270&field4=0.17     │
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
        "version": "2.0"
    },
    "broker": {
        "address": "test.mosquitto.org",
        "port": 1883
    },
    "topics": {
        "weather_alert": "weather/alert",
        "frost_alert": "weather/frost",
        "irrigation_command": "irrigation/+/command",
        "resource_usage": "irrigation/usage"
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
            "energy_kwh": "field4"
        }
    },
    "fields": {
        "field_1": {
            "crop_type": "tomato",
            "field_size_m2": 100,
            "water_need_mm_per_day": 5.0,
            "flow_rate_lpm": 20.0
        },
        "field_2": {
            "crop_type": "wheat",
            "field_size_m2": 200,
            "water_need_mm_per_day": 3.0,
            "flow_rate_lpm": 20.0
        }
    },
    "devices": [
        {
            "id": "sensor_node_field_1",
            "name": "Field 1 Soil Moisture Sensor",
            "type": "sensor",
            "topics": {
                "publish": ["farm/field_1/soil_moisture", "farm/field_1/temperature"],
                "subscribe": ["farm/field_1/config"]
            }
        },
        {
            "id": "actuator_valve_1",
            "name": "Field 1 Irrigation Valve",
            "type": "actuator",
            "topics": {
                "publish": ["farm/field_1/valve_status"],
                "subscribe": ["farm/field_1/valve_cmd"]
            }
        }
    ]
}
```

### 10.2 Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `broker.address` | MQTT broker hostname | test.mosquitto.org |
| `broker.port` | MQTT broker port | 1883 |
| `settings.moisture_threshold` | Irrigation trigger level (%) | 30.0 |
| `settings.rain_threshold_mm` | Rain alert trigger (mm) | 5.0 |
| `settings.frost_threshold_c` | Frost alert trigger (°C) | 2.0 |
| `settings.lat`, `settings.lon` | Location for weather API | 45.06, 7.66 |
| `fields.*.crop_type` | Crop type for smart irrigation | tomato, wheat, etc. |
| `fields.*.field_size_m2` | Field size in square meters | 100 |
| `fields.*.flow_rate_lpm` | Water flow rate (L/min) | 20.0 |

---

## 11. MQTT Topics

### 11.1 Topic Hierarchy

```
farm/
├── field_1/
│   ├── soil_moisture    # Sensor data (SenML list)
│   ├── temperature      # Sensor data (SenML list)
│   ├── valve_cmd        # Commands to actuator
│   ├── valve_status     # Actuator feedback (SenML list)
│   └── config           # Configuration updates
├── field_2/
│   └── ...
│
weather/
├── alert                # Rain alerts
└── frost                # Frost alerts
│
irrigation/
└── usage                # Resource usage (water/energy)
```

### 11.2 Topic Definitions

| Topic | Publisher | Subscriber | Payload Format | QoS |
|-------|-----------|------------|----------------|-----|
| `farm/field_X/soil_moisture` | Sensor Node | Water Manager, ThingSpeak | SenML list | 0 |
| `farm/field_X/temperature` | Sensor Node | ThingSpeak | SenML list | 0 |
| `farm/field_X/valve_cmd` | Water Manager, Telegram | Actuator | Command JSON | 0 |
| `farm/field_X/valve_status` | Actuator | — | SenML list | 0 |
| `weather/alert` | Weather Check | Water Manager, Telegram | Alert JSON | 1 |
| `weather/frost` | Weather Check | Water Manager, Telegram | Alert JSON | 1 |
| `irrigation/usage` | Actuator | ThingSpeak | SenML list | 0 |

### 11.3 Message Formats

**Sensor Data (SenML List)**:
```json
[
    {"bn": "sensor_node_field_1", "n": "soil_moisture", "t": 1703419200.0, "v": 25.5},
    {"bn": "sensor_node_field_1", "n": "temperature", "t": 1703419200.0, "v": 22.1}
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
    {"bn": "actuator_valve_1", "n": "water_liters", "t": 1703419200.0, "v": 10.5},
    {"bn": "actuator_valve_1", "n": "energy_kwh", "t": 1703419200.0, "v": 0.05}
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
    "fields": {...},
    "telegram": {...},
    "thingspeak": {...},
    "devices": [...]
}
```

#### GET /broker
Returns MQTT broker connection details.

**Response**:
```json
{
    "address": "test.mosquitto.org",
    "port": 1883
}
```

#### GET /devices
Returns list of registered devices.

**Response**:
```json
[
    {
        "id": "sensor_node_field_1",
        "name": "Field 1 Soil Moisture Sensor",
        "type": "sensor",
        "topics": {...}
    }
]
```

#### GET /devices/{id}
Returns a specific device by ID.

**Response**:
```json
{
    "id": "actuator_valve_1",
    "name": "Field 1 Irrigation Valve",
    "type": "actuator",
    "topics": {...}
}
```

#### POST /devices
Register a new device or send heartbeat.

**Request Body**:
```json
{
    "id": "actuator_valve_1",
    "name": "Field 1 Valve",
    "type": "actuator",
    "topics": {
        "subscribe": ["farm/field_1/valve_cmd"],
        "publish": ["farm/field_1/valve_status"]
    }
}
```

**Response**:
```json
{"status": "registered", "id": "actuator_valve_1"}
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

### 12.2 External APIs Used

| API | Base URL | Purpose |
|-----|----------|---------|
| Open-Meteo | `https://api.open-meteo.com/v1/forecast` | Weather forecasts (rain + frost) |
| ThingSpeak | `https://api.thingspeak.com/update` | Cloud data upload |
| Telegram | `https://api.telegram.org/bot{token}` | User notifications |

---

## 13. Dependencies

### Python Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `paho-mqtt` | ≥1.6.1 | MQTT client library |
| `requests` | ≥2.31.0 | HTTP client for REST APIs |
| `cherrypy` | — | REST API framework (Catalogue) |
| `telepot` | — | Telegram Bot integration |
| `pandas` | ≥2.0.0 | Data processing (optional) |
| `numpy` | ≥1.24.0 | Numerical operations |

---

## 14. Running the System

### Startup Order

1. **Catalogue Service** (must start first)
   ```bash
   python src/services/catalogue/service.py
   ```

2. **Weather Check Service**
   ```bash
   python src/services/weather_check/service.py
   ```

3. **Water Manager Service**
   ```bash
   python src/services/water_manager/service.py
   ```

4. **Telegram Bot Service**
   ```bash
   python src/services/telegram_bot/service.py
   ```

5. **ThingSpeak Adaptor**
   ```bash
   python src/services/thingspeak_adaptor/service.py
   ```

6. **Sensor Nodes**
   ```bash
   python src/devices/sensor_node.py
   ```

7. **Actuator Nodes**
   ```bash
   python src/devices/actuator_node.py
   ```

---

## 15. Summary

The Smart Precision Irrigation System demonstrates a well-architected IoT platform that:

1. **Uses REST for Configuration**: The Catalogue Service provides a central source of truth with full CRUD operations
2. **Uses MQTT for Real-time Data**: Efficient pub/sub for sensor readings and commands using SenML format
3. **Follows Microservices Pattern**: Each service has a single responsibility
4. **Implements Service Discovery**: All services bootstrap from the Catalogue
5. **Implements Dynamic Registration**: Devices register via POST (not hardcoded)
6. **Integrates External APIs**: Weather forecasting (rain + frost) and cloud analytics
7. **Provides Smart Irrigation**: Crop-type and field-size based duration calculation
8. **Tracks Resources**: Water consumption (L) and energy usage (kWh)
9. **Provides Interactive UI**: Telegram bot with inline keyboard buttons

The combination of REST and MQTT protocols provides the ideal balance between:
- **Reliability**: REST for critical configuration and registration
- **Efficiency**: MQTT for high-frequency sensor data
- **Scalability**: Decoupled services via message broker
- **Intelligence**: Smart irrigation logic based on agricultural needs

---

*Document Version: 2.0*  
*Last Updated: December 2024*  
*System Version: 2.0*
