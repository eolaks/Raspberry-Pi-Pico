"""
Date: 4-2-2026
Description:
    Master IoT and Embedded Cybersecurity -
    #4 IoT Integration: Pico 2-w as a Server
Author: OES
+234(0)8136394461
Contact us for AioT kits, training and skills acqusition
"""

#imported library
import network
import time
from umqtt.robust import MQTTClient
import machine
import ubinascii
import dht

# ---------------------------
# WIFI SETTINGS
# ---------------------------
WIFI_SSID = "xxxxxx" # add your SSID of your Wi-Fi
WIFI_PASSWORD = "xxxxxx"		# add your password  

# ---------------------------
# MQTT SETTINGS
# ---------------------------
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_CONTROL_TOPIC = b"pico/control"
MQTT_DATA_TOPIC = b"pico/data"

# ---------------------------
# RELAY SETUP (GP6)
# ---------------------------
relay = machine.Pin(6, machine.Pin.OUT)
relay.value(1)  # OFF initially

# ---------------------------
# DHT11 SETUP (GP2)
# ---------------------------
sensor = dht.DHT11(machine.Pin(2))

# ---------------------------
# CONNECT TO WIFI
# ---------------------------
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

def wifi_connect():
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            time.sleep(1)
    print("WiFi Connected, IP:", wlan.ifconfig()[0])

wifi_connect()

# ---------------------------
# MQTT CALLBACK FUNCTION (Relay Control)
# ---------------------------
def mqtt_callback(topic, msg):
    print("\n--- MQTT MESSAGE RECEIVED ---")
    print("Topic:", topic.decode())
    print("Message:", msg.decode())

    message = msg.decode().strip().upper()
    if message == "ON":
        relay.value(0)  # Relay ON (active LOW)
        print("Relay ON")
    elif message == "OFF":
        relay.value(1)  # Relay OFF
        print("Relay OFF")
    else:
        print("Unknown command")

# ---------------------------
# MQTT CLIENT SETUP (Robust)
# ---------------------------
client_id = ubinascii.hexlify(machine.unique_id())
client = MQTTClient(client_id, MQTT_BROKER, port=MQTT_PORT, keepalive=60)
client.set_callback(mqtt_callback)

# ---------------------------
# CONNECT AND SUBSCRIBE
# ---------------------------
def mqtt_connect():
    try:
        client.connect()
        client.subscribe(MQTT_CONTROL_TOPIC)
        print("Connected to MQTT Broker and Subscribed to pico/control")
    except Exception as e:
        print("MQTT connection failed:", e)
        time.sleep(5)
        mqtt_connect()  # retry until connected

mqtt_connect()

# ---------------------------
# PUBLISH TIMER
# ---------------------------
PUBLISH_INTERVAL = 5000  # milliseconds
last_publish = time.ticks_ms()

# ---------------------------
# MAIN LOOP
# ---------------------------
while True:
    try:
        client.check_msg()  # non-blocking
    except Exception as e:
        print("MQTT check_msg error:", e)
        try:
            client.reconnect()
            client.subscribe(MQTT_CONTROL_TOPIC)
            print("Reconnected to MQTT Broker")
        except Exception as e:
            print("Reconnection failed:", e)
            time.sleep(5)

    # Publish DHT11 data every interval
    if time.ticks_diff(time.ticks_ms(), last_publish) > PUBLISH_INTERVAL:
        try:
            sensor.measure()
            temp = sensor.temperature()
            hum = sensor.humidity()
            data_msg = "Temperature: {}°C, Humidity: {}%".format(temp, hum)
            client.publish(MQTT_DATA_TOPIC, data_msg)
            print("Publishing:", data_msg)
        except Exception as e:
            print("Sensor/Publish error:", e)
        last_publish = time.ticks_ms()

    time.sleep(0.1)

