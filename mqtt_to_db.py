import os
import json
import logging
import psycopg2
from psycopg2 import sql
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from datetime import datetime

# Load Environment Variables
load_dotenv()

# Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER_HOST")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC")

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

# Setup Logging (Crucial for debugging)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# DatabaseHandler encapsulates all PostgreSQL interactions.
class DatabaseHandler:
    """Handles PostgreSQL connections and insertions."""
    
    def __init__(self, config):
        self.config = config
        self.conn = None
        self.cursor = None
        self.connect()

    def connect(self):
        try:
            self.conn = psycopg2.connect(**self.config)
            self.cursor = self.conn.cursor()
            logger.info("Connected to PostgreSQL database.")

            # Check if table exists
            if not self.check_table_exists():
                # Pause and ask the user
                print("\n⚠️  Table 'sensors_data' was not found.")
                choice = input("Do you want to create it now? (y/n): ").strip().lower()
                
                if choice == 'y':
                    self.create_table()
                    print("✅ Table created.")
                else:
                    logger.warning("Table not created. Future insertions will fail.")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def check_table_exists(self):
        """Queries the database schema to see if the table exists."""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'sensors_data'
            );
        """
        self.cursor.execute(query)
        return self.cursor.fetchone()[0]

    def create_table(self):
        """Creates a structured table for sensor data if not exists."""
        query = """
        CREATE TABLE IF NOT EXISTS sensors_data (
            id SERIAL PRIMARY KEY,
            recorded_at TIMESTAMP,
            light INTEGER,
            humidity REAL,
            temperature REAL,
            pressure REAL
        );
        """
        try:
            self.cursor.execute(query)
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            self.conn.rollback()

    def insert_record(self, json_data):
        """Extracts fields and inserts them into specific columns."""
        query = sql.SQL("""
            INSERT INTO sensors_data (recorded_at, light, humidity, temperature, pressure) 
            VALUES (%s, %s, %s, %s, %s)
        """)
        
        try:
            # Check connection
            if self.conn.closed:
                self.connect()
            
            # Convert Unix timestamp (1770913500) to Python Datetime
            # This makes it readable in the database (e.g., 2026-02-12 10:30:00)
            dt_object = datetime.fromtimestamp(json_data['timestamp'])

            # Map JSON keys to our columns
            values = (
                dt_object, 
                json_data['light'], 
                json_data['humidity'], 
                json_data['t'],        # Mapping 't' from JSON to 'temperature' column
                json_data['pressure']
            )

            self.cursor.execute(query, values)
            self.conn.commit()
            logger.info(f"Data inserted: {json_data}")
            
        except KeyError as e:
            logger.error(f"Missing key in JSON data: {e}")
        except Exception as e:
            logger.error(f"Failed to insert data: {e}")
            self.conn.rollback()

    def close(self):
        if self.cursor: self.cursor.close()
        if self.conn: self.conn.close()


# MQTT Callbacks:
# on_connect is called when the client connects to the broker.
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"Connected to MQTT Broker! Subscribing to {MQTT_TOPIC}")
        client.subscribe(MQTT_TOPIC)
    else:
        logger.error(f"Failed to connect, return code {rc}")

# on_message is called when a message is received from the broker.
def on_message(client, userdata, msg):
    """Triggered when a message is received."""
    try:
        payload_str = msg.payload.decode('utf-8')
        data = json.loads(payload_str)
        
        # Access the database handler from userdata we passed when initializing the client (see main execution below)
        db_handler = userdata['db_handler']
        db_handler.insert_record(data)
        
    except json.JSONDecodeError:
        logger.error(f"Received invalid JSON: {msg.payload}")
    except Exception as e:
        logger.error(f"Error processing message: {e}")

# Main Execution
if __name__ == "__main__":
    # Initialize Database
    db = DatabaseHandler(DB_CONFIG)

    # Initialize MQTT Client
    # We pass the db handler to the client as 'userdata' so callbacks can access it
    client = mqtt.Client(userdata={'db_handler': db})
    
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        logger.info(f"Connecting to MQTT Broker at {MQTT_BROKER}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # Blocking call that processes network traffic, dispatches callbacks and handles reconnecting.
        client.loop_forever()
        
    except KeyboardInterrupt:
        logger.info("Stopping script...")
        db.close()
        client.disconnect()