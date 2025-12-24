# Smart Precision Irrigation System 2.0 🌱💧

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi-red?style=for-the-badge&logo=raspberrypi)
![Architecture](https://img.shields.io/badge/Architecture-Microservices-orange?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

## 📖 Project Overview
The **Smart Precision Irrigation System** is an IoT-based platform designed to optimize agricultural water usage and prevent crop loss due to climate anomalies.

Unlike traditional timer-based systems, this platform employs a **Microservices Architecture** to make real-time decisions based on soil moisture data, local temperature, and external weather forecasts.

**Key Features:**
* **Smart Water Management:** Triggers irrigation based on crop type, field size, and moisture deficit.
* **Frost Prevention:** Monitors temperature forecasts and publishes frost alerts when T < 2°C.
* **Rain-Aware:** Polls the **Open-Meteo API** to cancel scheduled irrigation if rain is predicted (>5mm).
* **Resource Tracking:** Monitors water consumption (L) and energy usage (kWh) per irrigation cycle.
* **Remote Monitoring:** Real-time alerts and interactive control via a **Telegram Bot**.
* **Data Analytics:** Uploads sensor data and resource usage to **ThingSpeak** for visualization.
* **Dynamic Registration:** Devices register with the Catalogue via REST POST (no hardcoding).

---

## 🏗 System Architecture
The software strictly follows **Object-Oriented Programming (OOP)** principles and uses **SenML** message format for all MQTT communications.

### 1. The Edge Layer (Sensors & Actuators)
Running on **Raspberry Pi Pico 2 W** microcontrollers:
* **Sensor Nodes:** Collect Soil Moisture (Capacitive) and Air Temperature (MCP9808).
* **Actuator Nodes:** Control Solenoid Valves (12V) and the Main Water Pump. Track water/energy usage.

### 2. The Service Layer (Core Logic)
Running on a **Raspberry Pi 5** Gateway, communicating via **MQTT** and **REST**:
* **Resource Catalogue:** The central registry with full CRUD (GET/POST/PUT/DELETE) for devices.
* **Water Manager:** The brain of the operation. Uses **smart irrigation logic** based on crop type and field size.
* **Weather-Check:** Background service polling Open-Meteo for rain AND frost forecasts.
* **Telegram Bot:** Interactive interface with inline keyboard buttons for status and control.
* **ThingSpeak Adaptor:** Uploads sensor metrics AND resource usage to the cloud.

---

## 📊 SenML Message Format

All MQTT messages follow the course-standard SenML format:

```json
[
    {"bn": "sensor_node_field_1", "n": "soil_moisture", "t": 1735084800.0, "v": 25.5},
    {"bn": "sensor_node_field_1", "n": "temperature", "t": 1735084800.0, "v": 22.1}
]
```

| Field | Description |
|-------|-------------|
| `bn` | Base name (device ID) |
| `n` | Measurement name |
| `t` | Timestamp (Unix epoch) |
| `v` | Value (single value, not nested) |

---

## 🧠 Smart Irrigation Logic

The Water Manager calculates irrigation duration dynamically:

```
water_needed_mm = (TARGET_MOISTURE - current_moisture) * crop_factor
total_liters = water_needed_mm * field_size_m2
duration_sec = total_liters / (flow_rate_lpm / 60)
```

**Crop Factors:**
| Crop | Factor | Typical Duration |
|------|--------|------------------|
| Tomato | 1.2 | 600s (10 min) |
| Corn | 1.0 | 480s (8 min) |
| Lettuce | 0.8 | 300s (5 min) |
| Wheat | 0.6 | 240s (4 min) |

---

## 💧 Resource Tracking

When an actuator closes its valve, it publishes resource usage:

```json
[
    {"bn": "actuator_valve_1", "n": "water_liters", "t": 1735084800.0, "v": 10.5},
    {"bn": "actuator_valve_1", "n": "energy_kwh", "t": 1735084800.0, "v": 0.05}
]
```

**Constants:**
* `FLOW_RATE_LPM = 20.0` (Liters per minute)
* `PUMP_POWER_KW = 0.75` (Kilowatts)

**ThingSpeak Field Mapping:**
| Metric | ThingSpeak Field |
|--------|------------------|
| Soil Moisture | field1 |
| Temperature | field2 |
| Water (L) | field3 |
| Energy (kWh) | field4 |

---

## 🛠 Hardware Stack
| Device | Quantity | Function |
| :--- | :--- | :--- |
| **Raspberry Pi 5** | 1 | Central Gateway & Microservices Host |
| **Raspberry Pi Pico 2 W** | 22 | Edge Nodes (Sensors & Actuators) |
| **Adafruit STEMMA Soil** | 10 | Capacitive Soil Moisture Sensor |
| **MCP9808** | 10 | High Accuracy Temperature Sensor |
| **Solenoid Valve (12V)** | 10 | Directional Water Control |
| **Water Pump** | 1 | Main System Pressure |

---

## 🚀 Installation & Setup

### Prerequisites
* Python 3.9 or higher
* An MQTT Broker (e.g., Mosquitto or test.mosquitto.org)
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

### 4. Start Services (in order)
```bash
# Terminal 1: Catalogue (must start first)
python src/services/catalogue/service.py

# Terminal 2: Weather Check
python src/services/weather_check/service.py

# Terminal 3: Water Manager
python src/services/water_manager/service.py

# Terminal 4: Telegram Bot
python src/services/telegram_bot/service.py

# Terminal 5: ThingSpeak Adaptor
python src/services/thingspeak_adaptor/service.py

# Terminal 6: Sensor Node
python src/devices/sensor_node.py

# Terminal 7: Actuator Node
python src/devices/actuator_node.py
```

---

## ⚙️ Configuration

The system uses `config/system_config.json` for centralized configuration:

```json
{
    "broker": {"address": "test.mosquitto.org", "port": 1883},
    "settings": {
        "moisture_threshold": 30.0,
        "rain_threshold_mm": 5.0,
        "frost_threshold_c": 2.0
    },
    "topics": {
        "weather_alert": "weather/alert",
        "frost_alert": "weather/frost",
        "resource_usage": "irrigation/usage"
    },
    "fields": {
        "field_1": {"crop_type": "tomato", "field_size_m2": 100, "flow_rate_lpm": 20.0},
        "field_2": {"crop_type": "wheat", "field_size_m2": 200, "flow_rate_lpm": 20.0}
    },
    "thingspeak": {
        "field_map": {
            "soil_moisture": "field1",
            "temperature": "field2",
            "water_liters": "field3",
            "energy_kwh": "field4"
        }
    }
}
```

---

## 📚 Documentation

* **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Complete technical documentation

---

## 👥 Team Members
* **Ali Vaezi** (s336256) 
* **Nicolas Restrepo-Lopez** (s336477) 
* **Roderick Tossato Silva** (s336217) 
* **Ludovica Deriu** (s348173)

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Last Updated: December 2024*  
*System Version: 2.0*

## 📄 License
This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
