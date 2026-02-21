# 🌦️ Weather Station Pipeline

A real-time **IoT data pipeline** that ingests weather sensor readings over **MQTT**, persists them to a **PostgreSQL** database, and serves a live **Streamlit dashboard** with interactive visualizations.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Latest-336791?logo=postgresql&logoColor=white)
![MQTT](https://img.shields.io/badge/MQTT-Paho-660066?logo=eclipse-mosquitto&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?logo=streamlit&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-Visualization-3F4F75?logo=plotly&logoColor=white)

## Architecture

```
Weather Sensors
      │
      │  
      ▼
 MQTT Broker  ──────►  mqtt_to_db.py  ──────►  PostgreSQL
(topic: weather/data)    (subscriber)       (weather_station_db)
                                                       │
                                                       ▼
                                               dashboard.py
                                              (Streamlit UI)
```

## Features

- **Real-time ingestion** — subscribes to an MQTT topic and writes every incoming measurement to PostgreSQL
- **Persistent storage** — structured SQL schema keeps a full historical record of all sensor readings
- **Live dashboard** — Streamlit + Plotly charts to display the latest data trends
- **Cross-platform** — instructions provided for both Linux and Windows

## Prerequisites

This pipeline is a continuation of the [weather station project](https://github.com/aboodAJ/weather-station)

| Requirement | Notes |
|---|---|
| Python 3.10+ | |
| MQTT Broker | Where data is published from the weather station. |

## Installation

### 1 — PostgreSQL Setup

#### Linux
```bash
sudo apt update
sudo apt install postgresql
sudo systemctl status postgresql # to check if it is running
```

```bash
sudo systemctl start postgresql # to start the service if it is not running
sudo systemctl enable postgresql # to start the service on boot
```


#### Windows
Download and run the official installer from [postgresql.org/download/windows](https://www.postgresql.org/download/windows/).

### 2 — Database & User

Switch to the postgres superuser first:

Linux: 
```bash
sudo -i -u postgres && psql
```

Windows: open "SQL Shell (psql)"

```sql
CREATE DATABASE weather_station_db;
CREATE USER weather_station_user WITH PASSWORD 'your_secure_password';

\c weather_station_db

GRANT CONNECT ON DATABASE weather_station_db TO weather_station_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO weather_station_user;
```

### 3 — Python Environment

#### Linux / macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Windows
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 4 — Environment Variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

```dotenv
# .env
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_TOPIC=weather/data

DB_NAME=weather_station_db
DB_USER=weather_station_user
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432
```

## Running the Pipeline

Start the MQTT subscriber (keeps running, ingests data continuously):
```bash
python mqtt_to_db.py
```

In a separate terminal, launch the dashboard:
```bash
streamlit run dashboard.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

## Project Structure

```
weather_station_pipeline/
├── mqtt_to_db.py       # MQTT subscriber → PostgreSQL writer
├── dashboard.py        # Streamlit + Plotly live dashboard
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── .gitignore
```

## Dependencies

| Package | Purpose |
|---|---|
| `paho-mqtt` | MQTT client |
| `psycopg2-binary` | PostgreSQL adapter |
| `python-dotenv` | `.env` file loader |
| `streamlit` | Dashboard framework |
| `plotly` | Interactive charts |
| `pandas` | Data manipulation |
