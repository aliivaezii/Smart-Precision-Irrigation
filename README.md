# Smart Precision Irrigation System 2.0 🌱💧

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi-red?style=for-the-badge&logo=raspberrypi)
![Architecture](https://img.shields.io/badge/Architecture-Microservices-orange?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

## 📖 Project Overview
The **Smart Precision Irrigation System** is an IoT-based platform designed to optimize agricultural water usage and prevent crop loss due to climate anomalies.

Unlike traditional timer-based systems, this platform employs a **Microservices Architecture** to make real-time decisions based on soil moisture data, local temperature, and external weather forecasts.

**Key Features:**
* **Smart Water Management:** Triggers irrigation only when soil moisture drops below specific thresholds.
* **Frost Prevention:** Monitors local temperature and forecasts to alert farmers of incoming freezing conditions.
* **Weather Integration:** Polls the **Open-Meteo API** to cancel scheduled irrigation if rain is predicted (>5mm).
* **Remote Monitoring:** Real-time alerts and system status via a **Telegram Bot**.
* **Data Analytics:** Uploads water and energy consumption data to **ThingSpeak** for visualization.

---

## 🏗 System Architecture
The software strictly follows **Object-Oriented Programming (OOP)** principles. The system is divided into two logical layers:

### 1. The Edge Layer (Sensors & Actuators)
Running on **Raspberry Pi Pico 2 W** microcontrollers:
* **Sensor Nodes:** Collect Soil Moisture (Capacitive) and Air Temperature (MCP9808).
* **Actuator Nodes:** Control Solenoid Valves (12V) and the Main Water Pump.

### 2. The Service Layer (Core Logic)
Running on a **Raspberry Pi 5** Gateway, communicating via **MQTT** and **REST**:
* **Resource Catalogue:** The central registry containing the system topology and device settings.
* **Water Manager:** The brain of the operation. Subscribes to sensors and publishes commands to valves.
* **Weather-Check:** Background service polling Open-Meteo for rain/frost forecasts.
* **Telegram Bot:** Interface for user alerts and status queries.
* **ThingSpeak Adaptor:** Uploads usage metrics to the cloud.

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
* An MQTT Broker (e.g., Mosquitto)
* Git

### 1. Clone the Repository
```bash
git clone [https://github.com/YOUR_USERNAME/Smart-Precision-Irrigation.git](https://github.com/aliivaezii/Smart-Precision-Irrigation.git)
cd Smart-Precision-Irrigation
```
### 2. Set Up Virtual Environment
**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```
**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## ⚙️ Configuration
The system uses a centralized configuration file located at `config/system_config.json`. This allows adding new fields or changing settings without modifying the source code.

**Key Settings:**
* `rain_threshold_mm`: Minimum predicted rain to cancel irrigation (default >5mm).
* `mqtt_broker`: Address of your local or cloud MQTT broker.
* `telegram`: API tokens (Do not hardcode these; use Environment Variables).

---

## 👥 Team Members
* **Ali Vaezi** (s336256) 
* **Nicolas Restrepo-Lopez** (s336477) 
* **Roderick Tossato Silva** (s336217) 
* **Ludovica Deriu** (s348173)

---

## 📄 License
This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
