import json
import os
from datetime import datetime
from itertools import count

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

class MQTTCLIENT:
    def __init__(self,on_sensor_data_callback=None):
        self.broker = os.getenv('MQTT_BROKER','localhost')
        self.port = int(os.getenv('MQTT_PORT',1883))
        self.username = os.getenv('MQTT_USERNAME','')
        self.password = os.getenv('MQTT_PASSWORD','')
        self.topic_sensor = os.getenv('MQTT_TOPIC_SENSOR', 'auralink/sensor/data')
        self.topic_backend = os.getenv('MQTT_TOPIC_BACKEND', 'auralink/backend/message')

        self.client = mqtt.Client(client_id="auralink_backend")

        if self.username and self.password:
            self.client.username_pw_set(self.username,self.password)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.on_sensor_data_callback = on_sensor_data_callback
        self.is_connected = False

    def on_connect(self, client, userdata, flags, rc):
        """callback when connected to MQTT broker"""
        if rc == 0:
            print("connected to the broker!!")
            self.is_connected = True
            # now we're subscribing to sensor data topic
            self.client.subscribe(self.topic_sensor)
            print(f" subscribed to {self.topic_sensor}")
        else:
            error_messages = {
                1: "connection refused - incorrect protocol",
                2: "connection refused - invalid client identifier",
                3: "connection refused - server unavailable",
                4: "connection refused - bad credentials",
                5: "connection refused - not authorized"
            }
            print(f" connection failed: {error_messages.get(rc, f'unknown error {rc}')}")
            self.is_connected = False

    def on_disconnect(self, client, userdata, rc):
        """callback when disconnected from MQTT broker"""
        if rc != 0:
            print(f" unexpected disconnection (code:{rc}")
        else:
            print(f" disconnected from MQTT broker")
        self.is_connected = False

    def on_message(self, client, userdata, msg):
        """callback when message received"""
        try:
            payload = json.loads(msg.payload.decode())
            print(f" received on {msg.topic}: {payload}")

            if self.on_sensor_data_callback:
                self.on_sensor_data_callback(payload)

        except json.JSONDecodeError as e:
            print(f" error decoding JSON: {e}")
            print(f" raw message: {msg.payload.decode()}")
        except Exception as e:
            print(f" error processing message: {e}")

    def connect(self):
        """connect to MQTT broker"""
        try:
            print(f" connecting to MQTT broker: {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()

            import time
            time.sleep(3)

            return self.is_connected

        except ConnectionRefusedError:
            print(f" connection refused. Mosquitto may not running")
            return False
        except Exception as e:
            print(f"connection error: {e}")
            return False

    def disconnect(self):
        """disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        print("disconnected from MQTT broker")

    def publish_message(self, message_data):
        """publish message to iot device"""
        if not self.is_connected:
            print("not connected to MQTT broker")
            return False

        try:
            payload = json.dumps(message_data)
            result = self.client.publish(self.topic_backend, payload, qos = 1)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f" published to {self.topic_backend}")
                return True
            else:
                print(f" failed to publish (code: {result.rc}")
                return False

        except Exception as e:
            print(f" error publishing message: {e}")
            return False

    def is_mqtt_connected(self):
        """check if connected to MQTT broker"""
        return self.is_connected


if __name__ == "__main__":
    import time

    def handle_sensor_data(data):
        """test callback for sensor data"""
        print(f" temperature: {data.get('temperature')}°C")
        print(f" humidity: {data.get('humidity')}%")
        if 'pressure' in data:
            print(f" pressure: {data.get('pressure')} hPa")
        print(f" timestamp: {data.get('timestamp')}")

    # create client with callback
    mqtt_client = MQTTCLIENT(on_sensor_data_callback=handle_sensor_data)

    #connect
    if mqtt_client.connect():
        print("\n connected successfully!!")

        try:
            counter = 0
            while True:
                time.sleep(1)
                counter +=1

                #testing publish every 10 sec
                if counter % 10 == 0:
                    test_message = {
                        "quote": "The comfortable air whispers of balance.",
                        "email_summary": "2 new emails from team",
                        "priority": "medium",
                        "timestamp": datetime.now().isoformat()
                    }
                    mqtt_client.publish_message(test_message)
                    print(f"\n published message at {counter}s")

        except KeyboardInterrupt:
            mqtt_client.disconnect()

    else:
        print("\n failed to connect to MQTT broker!!")
