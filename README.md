# AuraLink - IOT Project

---

```markdown
<h1 align="center">🌐 AuraLink – AI-Powered Smart IoT System</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/ESP32-Arduino-orange.svg" alt="ESP32">
  <img src="https://img.shields.io/badge/MQTT-Message%20Broker-green.svg" alt="MQTT">
  <img src="https://img.shields.io/badge/AI-Llama3%20(Groq)-purple.svg" alt="Llama3 Groq">
  <img src="https://img.shields.io/badge/Gmail%20API-Integration-red.svg" alt="Gmail API">
  <img src="https://img.shields.io/github/license/dondilini/AuraLink.svg" alt="License">
</p>

---

### 🧠 Overview

**AuraLink** is an advanced **AI-integrated IoT ecosystem** that bridges the gap between **environmental sensing** and **intelligent communication**.  
It uses an **ESP32 IoT device** with **sensors (DHT22, MQ135)** and **OLED display**, connected to a **Python-based backend** that integrates:

- **LLM (Llama 3.3 – via Groq API)** for real-time poetic quote generation.  
- **Gmail API** to summarize unread or urgent emails.  
- **MQTT communication** between the backend and IoT device.  
- A **Textual-based TUI (Terminal User Interface)** for live monitoring and management.

---

### 🧩 System Architecture

```

┌────────────────────────────┐
│         ESP32 DEVICE       │
│ ─ Reads Temp, Humidity     │
│ ─ Sends to MQTT Broker     │
│ ─ Displays LLM Messages    │
└──────────────┬─────────────┘
│ MQTT
┌──────────────▼─────────────┐
│        MQTT BROKER         │
│ (e.g., Mosquitto)          │
└──────────────┬─────────────┘
│
┌──────────────▼─────────────┐
│     AURALINK BACKEND       │
│  ├ LLM Agent (Groq API)    │
│  ├ Gmail Email Handler     │
│  ├ MQTT Client             │
│  └ Textual TUI Dashboard   │
└──────────────┬─────────────┘
│
┌──────────────▼─────────────┐
│         USER VIEW          │
│  ├ OLED Display (ESP32)    │
│  ├ Live Quotes & Emails    │
│  └ RGB LED Priority Alert  │
└────────────────────────────┘

```

---

### ⚙️ Core Components

#### 🔹 1. **ESP32 Firmware (Arduino C++)**
- Sensors: `DHT22`, `MQ135`  
- Display: `Adafruit_SSD1306` OLED  
- MQTT Client: Publishes environmental data & receives AI-generated messages  
- RGB LED & Buzzer indicate **priority levels**:
  - 🟢 Low = Normal  
  - 🟡 Medium = Attention  
  - 🔴 High = Urgent  

#### 🔹 2. **Backend (Python 3.11+)**
- **Textual TUI** for real-time logs, sensor readings, system stats  
- **MQTT client** connects to ESP32 device  
- **LLM Agent** (Groq API – Llama 3.3) generates poetic, metaphorical quotes  
- **Email Handler** fetches, parses, and summarizes unread/important Gmail messages  
- Combines both sensor and email data into a unified contextual response  

#### 🔹 3. **Mock ESP32 Simulator (Python)**
- Simulates temperature, humidity, and pressure data  
- Publishes mock sensor readings and displays backend responses  
- Useful for testing without a physical ESP32 board  

---

### 🚀 Features

✅ Real-time IoT sensor data collection  
✅ AI-generated environmental quotes (Llama 3.3)  
✅ Gmail API integration for smart summaries  
✅ MQTT-based message synchronization  
✅ RGB + buzzer alerts for message priority  
✅ Beautiful live terminal dashboard (Textual TUI)  
✅ ESP32 OLED scrolling quotes and email previews  
✅ Mock simulator for development and CI pipelines  

---

### 🖥️ TUI Interface

| Section | Description |
|----------|-------------|
| **System Status** | Shows LLM, MQTT, Email connection health |
| **Sensor Data** | Displays latest temperature, humidity, air quality |
| **Message Panel** | Shows LLM quote + summarized emails |
| **Logs Panel** | Live system logs from all components |
| **Stats Footer** | Real-time metrics: uptime, messages, readings, emails |

Run shortcuts:
```

p - Force manual message process
l - Toggle log view
q - Quit gracefully

````

---

### 🧪 Tech Stack

| Category | Technologies |
|-----------|---------------|
| **IoT Firmware** | ESP32, Arduino, DHT22, MQ135, OLED, PubSubClient |
| **Backend** | Python 3.11, Paho MQTT, Textual, dotenv, Rich |
| **AI/LLM** | Groq Llama 3.3 (via LangChain-Groq) |
| **Email Integration** | Gmail API (OAuth2) |
| **Communication** | MQTT Protocol |
| **Visualization** | Terminal UI (Textual Framework) |

---

### 🔧 Setup Instructions

#### 1. Clone Repository
```bash
git clone https://github.com/<your-username>/AuraLink.git
cd AuraLink
````

#### 2. Create and Configure `.env`

```env
# MQTT
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_TOPIC_SENSOR=auralink/sensor/data
MQTT_TOPIC_BACKEND=auralink/backend/message

# Groq LLM API
GROQ_API_KEY=your_groq_api_key_here

# Gmail API
GOOGLE_CLIENT_ID=xxxx
GOOGLE_CLIENT_SECRET=xxxx
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 4. Run Backend (TUI)

```bash
python backend/app.py
```

#### 5. Run Mock ESP32 (Optional)

```bash
python mock_esp32.py
```

#### 6. Upload Firmware to Real ESP32

Use **Arduino IDE** or **PlatformIO**, configure Wi-Fi & MQTT IP in code, and flash the firmware.

---

### 🧭 Example Output

**Backend Console (Textual TUI):**

```
LLM Agent... ✓
Gmail API... ✓
MQTT Broker... ✓
System Initialized Successfully

Quote: The warm air hums with quiet wisdom.
Emails: 2 new urgent messages from boss & HR.
Priority: HIGH
```

**ESP32 OLED Display:**

```
*** AuraLink ***
Temp: 27.5°C
Hum: 61%
Air Quality: 378
---------------------
“The air hums like a secret breeze.”
---------------------
Emails: 2 urgent from work
```

---

### 🛠️ Folder Structure

```
AuraLink/
│
├── backend/
│   ├── app.py               # Main TUI + coordinator
│   ├── llm_agent.py         # AI Quote & Email summarization
│   ├── email_handler.py     # Gmail API integration
│   ├── mqtt_client.py       # MQTT client connection
│   └── app.tcss             # Textual UI styling
│
├── firmware/
│   └── aurahub.ino          # ESP32 firmware (Arduino)
│
├── mock/
│   └── mock_esp32.py        # Virtual ESP32 simulator
│
├── .env                     # Environment variables
└── README.md
```

---

### 🧩 Future Improvements

* Add mobile dashboard with live MQTT visualization
* Integrate voice-based alerts using Google TTS
* Store environmental history in a cloud database
* Add camera-based visual sensing for advanced insights

---
---

> 💡 *AuraLink brings together IoT, AI, and emotion — turning data into poetic intelligence.*

```
