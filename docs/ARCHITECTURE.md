# Smart Precision Irrigation System - Technical Documentation

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Communication Protocols](#3-communication-protocols)
4. [Component Analysis](#4-component-analysis)
5. [Service Roles (Provider/Consumer)](#5-service-roles-providerconsumer)
6. [Data Flow](#6-data-flow)
7. [Configuration](#7-configuration)
8. [MQTT Topics](#8-mqtt-topics)
9. [REST API Endpoints](#9-rest-api-endpoints)

---

## 1. System Overview

The **Smart Precision Irrigation System** is an IoT-based microservices platform for smart agriculture. It uses a combination of **REST APIs** and **MQTT messaging** to orchestrate sensor data collection, intelligent decision-making, and actuator control.

### Key Objectives:
- **Smart Water Management**: Irrigate only when soil moisture falls below threshold
- **Weather-Aware**: Cancel irrigation if rain is predicted
- **Real-time Monitoring**: Telegram notifications for system events
- **Cloud Analytics**: ThingSpeak integration for data visualization

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

## 4. Component Analysis

### 4.1 Common Module

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

### 4.2 Device Layer

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

**Data Format (SenML)**:
```json
{
    "bn": "sensor_node_field_1",
    "n": "soil_sensor",
    "t": 1703419200.0,
    "v": {
        "soil_moisture": 45.2,
        "temperature": 22.5
    }
}
```

**Communication**:
- **REST** → Catalogue (bootstrap, one-time)
- **MQTT Publish** → `farm/field_X/soil_moisture`, `farm/field_X/temperature`

---

### 4.3 Service Layer

#### `src/services/catalogue/service.py`

**Purpose**: Central service registry and configuration provider (Service Catalogue pattern).

**Technology**: CherryPy REST framework

**Endpoints**:

| Method | Endpoint | Response |
|--------|----------|----------|
| GET | `/` | Full system configuration |
| GET | `/broker` | MQTT broker details |
| GET | `/devices` | List of all registered devices |
| GET | `/settings` | System settings (thresholds, location) |

**Configuration Source**: Reads from `config/system_config.json`

**Role**: **SERVICE PROVIDER** — All other services consume this API at startup.

---

#### `src/services/water_manager/service.py`

**Purpose**: Core irrigation controller — the "brain" of the system.

**Responsibilities**:
1. Subscribe to all sensor data topics
2. Evaluate soil moisture against threshold
3. Check for active rain alerts
4. Publish valve open/close commands

**Decision Logic**:
```
IF moisture < threshold AND NOT rain_alert THEN
    OPEN valve for 300 seconds
ELSE IF moisture < threshold AND rain_alert THEN
    SKIP irrigation (rain expected)
ELSE
    No action needed
```

**Communication**:
- **REST** → Catalogue (bootstrap)
- **MQTT Subscribe** → `farm/field_X/soil_moisture`, `weather/alert`
- **MQTT Publish** → `farm/field_X/valve_cmd`

**Command Format**:
```json
{
    "command": "OPEN",
    "duration": 300
}
```

---

#### `src/services/weather_check/service.py`

**Purpose**: Weather monitoring service that polls external forecast API.

**External API**: Open-Meteo (https://api.open-meteo.com)

**Polling Mechanism**:
- Background thread polls weather API at configurable interval
- Default: every 3600 seconds (1 hour)
- For testing: every 60 seconds

**Alert Logic**:
```
IF precipitation >= 5mm (threshold) AND alert NOT active THEN
    Publish RAIN_ALERT with status=ACTIVE
ELSE IF precipitation < 5mm AND alert IS active THEN
    Publish RAIN_ALERT with status=CLEARED
```

**Communication**:
- **REST** → Catalogue (bootstrap)
- **REST** → Open-Meteo API (weather data)
- **MQTT Publish** → `weather/alert`

**Alert Format**:
```json
{
    "alert_type": "RAIN_ALERT",
    "status": "ACTIVE",
    "precipitation_mm": 8.5,
    "t": 1703419200.0
}
```

---

#### `src/services/telegram_bot/service.py`

**Purpose**: User notification service via Telegram messaging.

**Monitored Topics**:
- `weather/alert` — Rain/frost warnings
- `irrigation/+/command` — Valve activation events

**Notification Examples**:
- 🌧️ "RAIN ALERT! Expected: 8.5mm. Irrigation suspended."
- ☀️ "Rain alert cleared. Irrigation resumed."
- 💧 "Irrigation started! Duration: 300s"

**Communication**:
- **REST** → Catalogue (bootstrap)
- **REST** → Telegram Bot API (send messages)
- **MQTT Subscribe** → `weather/alert`, `irrigation/+/command`

---

#### `src/services/thingspeak_adaptor/service.py`

**Purpose**: Cloud data adaptor for IoT analytics visualization.

**Target Platform**: ThingSpeak (https://thingspeak.com)

**Features**:
- Subscribes to all sensor topics
- Buffers incoming data
- Rate-limited uploads (ThingSpeak requires 15s between updates)

**Field Mapping**:
```json
{
    "soil_moisture": "field1",
    "temperature": "field2"
}
```

**Communication**:
- **REST** → Catalogue (bootstrap)
- **REST** → ThingSpeak API (data upload)
- **MQTT Subscribe** → `farm/field_X/soil_moisture`, `farm/field_X/temperature`

---

## 5. Service Roles (Provider/Consumer)

### Service Provider vs Consumer Matrix

| Component | REST Provider | REST Consumer | MQTT Publisher | MQTT Subscriber |
|-----------|:-------------:|:-------------:|:--------------:|:---------------:|
| **Catalogue Service** | ✅ | ❌ | ❌ | ❌ |
| **Sensor Node** | ❌ | ✅ | ✅ | ❌ |
| **Water Manager** | ❌ | ✅ | ✅ | ✅ |
| **Weather Check** | ❌ | ✅ | ✅ | ❌ |
| **Telegram Bot** | ❌ | ✅ | ❌ | ✅ |
| **ThingSpeak Adaptor** | ❌ | ✅ | ❌ | ✅ |

### Detailed Role Analysis

#### Pure Service Providers:
- **Catalogue Service**: Provides configuration data to all other services via REST API

#### Pure Service Consumers:
- **Telegram Bot**: Only consumes data (MQTT) and forwards to external API
- **ThingSpeak Adaptor**: Only consumes data (MQTT) and forwards to cloud

#### Hybrid (Provider & Consumer):
- **Water Manager**: Consumes sensor data, provides valve commands
- **Weather Check**: Consumes external API, provides alerts
- **Sensor Node**: Consumes config, provides sensor readings

---

## 6. Data Flow

### 6.1 System Startup Sequence

```
1. Catalogue Service starts → Exposes REST API on port 8080
2. Other services start → Each fetches config via GET http://localhost:8080/
3. Services extract:
   - MQTT broker address/port
   - Device configurations
   - Thresholds and settings
4. Services connect to MQTT broker
5. Services subscribe to relevant topics
6. System enters operational mode
```

### 6.2 Irrigation Decision Flow

```
Sensor Node                  Water Manager              Actuator
    │                             │                        │
    │ MQTT: soil_moisture=25%     │                        │
    ├────────────────────────────►│                        │
    │                             │ Check: 25% < 30%?      │
    │                             │ Check: rain_alert?     │
    │                             │                        │
    │                             │ MQTT: valve_cmd=OPEN   │
    │                             ├───────────────────────►│
    │                             │                        │ Opens valve
```

### 6.3 Weather Alert Flow

```
Open-Meteo API           Weather Check           Water Manager          Telegram Bot
      │                       │                        │                      │
      │ REST: precipitation   │                        │                      │
      │◄──────────────────────│                        │                      │
      │ Response: 8.5mm       │                        │                      │
      ├──────────────────────►│                        │                      │
      │                       │ MQTT: RAIN_ALERT       │                      │
      │                       ├───────────────────────►│                      │
      │                       │                        │ Sets rain_alert=true │
      │                       │                        │                      │
      │                       │ MQTT: RAIN_ALERT       │                      │
      │                       ├────────────────────────┼─────────────────────►│
      │                       │                        │                      │ Sends notification
```

---

## 7. Configuration

### 7.1 System Configuration (`config/system_config.json`)

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
    "settings": {
        "lat": 45.06,
        "lon": 7.66,
        "rain_threshold_mm": 5.0,
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
            "temperature": "field2"
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
        }
    ]
}
```

### 7.2 Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `broker.address` | MQTT broker hostname | test.mosquitto.org |
| `broker.port` | MQTT broker port | 1883 |
| `settings.moisture_threshold` | Irrigation trigger level (%) | 30.0 |
| `settings.rain_threshold_mm` | Rain alert trigger (mm) | 5.0 |
| `settings.lat`, `settings.lon` | Location for weather API | 45.06, 7.66 |

---

## 8. MQTT Topics

### 8.1 Topic Hierarchy

```
farm/
├── field_1/
│   ├── soil_moisture    # Sensor data
│   ├── temperature      # Sensor data
│   ├── valve_cmd        # Commands to actuator
│   ├── valve_status     # Actuator feedback
│   └── config           # Configuration updates
├── field_2/
│   └── ...
│
weather/
└── alert                # Rain/frost alerts
│
irrigation/
└── +/command            # Wildcard subscription for valve commands
```

### 8.2 Topic Definitions

| Topic | Publisher | Subscriber | QoS |
|-------|-----------|------------|-----|
| `farm/field_X/soil_moisture` | Sensor Node | Water Manager, ThingSpeak | 0 |
| `farm/field_X/temperature` | Sensor Node | ThingSpeak | 0 |
| `farm/field_X/valve_cmd` | Water Manager | Actuator | 0 |
| `farm/field_X/valve_status` | Actuator | — | 0 |
| `weather/alert` | Weather Check | Water Manager, Telegram | 1 |
| `irrigation/+/command` | — | Telegram Bot | 0 |

---

## 9. REST API Endpoints

### 9.1 Catalogue Service API

**Base URL**: `http://localhost:8080`

#### GET /
Returns the complete system configuration.

**Response**:
```json
{
    "project_info": {...},
    "broker": {...},
    "settings": {...},
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

#### GET /settings
Returns system settings and thresholds.

**Response**:
```json
{
    "lat": 45.06,
    "lon": 7.66,
    "rain_threshold_mm": 5.0,
    "moisture_threshold": 30.0
}
```

### 9.2 External APIs Used

| API | Base URL | Purpose |
|-----|----------|---------|
| Open-Meteo | `https://api.open-meteo.com/v1/forecast` | Weather forecasts |
| ThingSpeak | `https://api.thingspeak.com/update` | Cloud data upload |
| Telegram | `https://api.telegram.org/bot{token}` | User notifications |

---

## 10. Dependencies

### Python Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `paho-mqtt` | ≥1.6.1 | MQTT client library |
| `requests` | ≥2.31.0 | HTTP client for REST APIs |
| `cherrypy` | — | REST API framework (Catalogue) |
| `python-telegram-bot` | ≥20.0 | Telegram Bot integration |
| `pandas` | ≥2.0.0 | Data processing (optional) |
| `numpy` | ≥1.24.0 | Numerical operations |

---

## 11. Running the System

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

---

## 12. Summary

The Smart Precision Irrigation System demonstrates a well-architected IoT platform that:

1. **Uses REST for Configuration**: The Catalogue Service provides a central source of truth
2. **Uses MQTT for Real-time Data**: Efficient pub/sub for sensor readings and commands
3. **Follows Microservices Pattern**: Each service has a single responsibility
4. **Implements Service Discovery**: All services bootstrap from the Catalogue
5. **Integrates External APIs**: Weather forecasting and cloud analytics
6. **Provides User Interface**: Telegram notifications for monitoring

The combination of REST and MQTT protocols provides the ideal balance between:
- **Reliability**: REST for critical configuration
- **Efficiency**: MQTT for high-frequency sensor data
- **Scalability**: Decoupled services via message broker

---

*Document Version: 1.0*  
*Last Updated: December 2024*  
*System Version: 2.0*
