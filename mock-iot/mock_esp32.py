"""
mock ESP32 Device
"""

import json
import time
import random
from datetime import datetime
import paho.mqtt.client as mqtt

class MockESP32:
    def __init__(self, broker='localhost', port=1883):
        self.broker = broker
        self.port = port
        self.topic_sensor = 'auralink/sensor/data'
        self.topic_backend = 'auralink/backend/message'

        self.client = mqtt.Client(client_id="mock_esp32")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.temperature = 25.0
        self.humidity = 55.0
        self.pressure = 1023.25

        self.connected = False

    def on_connect(self, client, userdata, flags, rc):
        """callback when connected"""
        if rc == 0:
            print("mock ESP32 connected to MQTT broker")
            self.connected = True

            #subscribe to backend messages
            self.client.subscribe(self.topic_backend)
            print(f" subscribed to {self.topic_backend}")

        else:
            print(f" connection failed with code: {rc}")


    def on_message(self, client, userdata,msg):
        """callback when receive message from backend"""
        try:
            payload = json.loads(msg.payload.decode())
            self.display_message(payload)

        except Exception as e:
            print(f" error processing message: {e}")

    def display_message(self, message):
        """simulate OLED display output"""

        print("\n" + "="*50)
        print("\n" + "="*50)

        if 'quote' in message and message['quote']:
            print(f" quote: ")
            print(f" {message['quote']}")

        if 'email_summary' in message and message['email_summary']:
            print(f" emails: ")
            print(f" {message['email_summary']}")

        priority = message.get('priority', 'low')
        led_colors = {
            'high': 'RED (URGENT!)',
            'medium': 'YELLOW',
            'low': 'GREEN'
        }
        print(f"\n LED: {led_colors.get(priority,'OFF')}")

        if 'sensor_data' in message:
            sensor = message['sensor_data']
            print(f"   Temp: {sensor.get('temperature')}°C")
            print(f"   Humidity: {sensor.get('humidity')}%")
            if 'pressure' in sensor:
                print(f"   Pressure: {sensor.get('pressure')} hPa")

        print("\n" + "="*50 + "\n")


    def simulate_sensor_drift(self):
        """simulate sensor value changes"""

        self.temperature += random.uniform(-0.5, 0.5)
        self.temperature = max(18, min(35, self.temperature))

        self.humidity += random.uniform(-2, 2)
        self.humidity = max(30, min(80, self.humidity))

        self.pressure += random.uniform(-0.5, 0.5)
        self.pressure = max(990, min(1030, self.pressure))

    def read_sensors(self):
        """simulate sensor reading"""
        self.simulate_sensor_drift()

        return {
            "temperature": round(self.temperature, 2),
            "humidity": round(self.humidity, 2),
            "pressure": round(self.pressure, 2),
            "timestamp": datetime.now().isoformat()
        }

    def publish_sensor_data(self):
        """publish simulated sensor data"""
        if not self.connected:
            print(" not connected, skipping publish")
            return False

        sensor_data = self.read_sensors()

        try:
            payload = json.dumps(sensor_data)
            result = self.client.publish(self.topic_sensor, payload, qos=1)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f" published sensor data: Temp={sensor_data['temperature']}°C, "
                      f"Humidity={sensor_data['humidity']}%")
                return True
            else:
                print(f" publish failed")
                return False
        except Exception as e:
            print(f" error publishing: {e}")
            return False

    def connect(self):
        """connect to MQTT broker"""
        try:
            print(f"connecting to MQTT broker: {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            time.sleep(3)
            return self.connected
        except Exception as e:
            print(f" connection error: {e}")
            return False

    def disconnect(self):
        """disconnect from broker"""
        self.client.loop_stop()
        self.client.disconnect()
        print(" disconnected")

    def run(self, interval=30):
        """run the mock device"""
        if not self.connect():
            print(" failed to connect")
            return

        print(f"\n mock ESP32 is running")

        try:
            while True:
                self.publish_sensor_data()
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\nshutting down mock device...")
            self.disconnect()


class MockESP32Interactive(MockESP32):
    """interactive version for manual testing"""

    def run_interactive(self):
        """Run in interactive mode"""
        if not self.connect():
            print(" failed to connect")
            return

        print("\n" + "="*50)
        print("     MOCK ESP32 - INTERACTIVE MODE")
        print("="*50)
        print("\nCommands:")
        print("  's' - Send sensor data")
        print("  't' - Change temperature")
        print("  'h' - Change humidity")
        print("  'a' - Auto mode (send every 30s)")
        print("  'q' - Quit")
        print("="*50 + "\n")

        try:
            while True:
                cmd = input("enter command: ").strip().lower()

                if cmd == 's':
                    self.publish_sensor_data()

                elif cmd == 't':
                    try:
                        temp = float(input("enter temperature (18-35°C): "))
                        self.temperature = max(18, min(35, temp))
                        print(f" temperature set to {self.temperature}°C")
                        self.publish_sensor_data()
                    except ValueError:
                        print(" invalid number")

                elif cmd == 'h':
                    try:
                        hum = float(input("enter humidity (30-80%): "))
                        self.humidity = max(30, min(80, hum))
                        print(f" humidity set to {self.humidity}%")
                        self.publish_sensor_data()
                    except ValueError:
                        print(" invalid number")

                elif cmd == 'a':
                    print("entering auto mode...")
                    self.run(interval=30)

                elif cmd == 'q':
                    break

                else:
                    print(" unknown command")

        except KeyboardInterrupt:
            pass

        finally:
            print("\n\nShutting down...")
            self.disconnect()

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        print("starting in INTERACTIVE mode...\n")
        device = MockESP32Interactive()
        device.run_interactive()
    else:
        print("starting in AUTO mode...")
        device = MockESP32()
        device.run(interval=30)