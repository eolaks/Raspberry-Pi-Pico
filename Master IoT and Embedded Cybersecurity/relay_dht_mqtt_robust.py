"""
Date: 16-2-2026
Description:
    Master IoT and Embedded Cybersecurity -
    #6 IoT Integration: Custom App using MQTT IoT Protocol
Author: OES
+234(0)8136394461
Contact us for AioT kits, training and skills acqusition
"""

#imported library

import network
import time
import machine
import ubinascii
import dht
import ujson
import ssd1306
from umqtt.robust import MQTTClient

# =====================================
# CONFIGURATION
# =====================================
WIFI_SSID = "xxxxxxx"  # add your SSID of your Wi-Fi
WIFI_PASSWORD = "xxxxxxxx"		 # add your password 

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

MQTT_SUBSCRIPTION = b"pico/control"  # topic to subscribe to
MQTT_PUBLISH = b"pico/data"			 # topic to publish 

PUBLISH_INTERVAL = 5000  # milliseconds

# =====================================
# OLED SETUP (SSD1306 128x64 I2C)
# SDA = GP0, SCL = GP1
# =====================================
i2c = machine.I2C(0, scl=machine.Pin(1), sda=machine.Pin(0))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# =====================================
# HARDWARE SETUP
# =====================================
relay = machine.Pin(6, machine.Pin.OUT)
relay.value(1)  # OFF initially (active LOW)
relay_state = "OFF"

sensor = dht.DHT11(machine.Pin(2))

# =====================================
# WIFI SETUP
# =====================================
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# =====================================
# OLED FUNCTIONS
# =====================================

def oled_show_startup():
    oled.fill(0)
    oled.text("System", 30, 20)
    oled.text("Starting...", 20, 35)
    oled.show()


def draw_wifi_bars(rssi):

    if rssi >= -50:
        bars = 4
    elif rssi >= -60:
        bars = 3
    elif rssi >= -70:
        bars = 2
    elif rssi >= -80:
        bars = 1
    else:
        bars = 0

    x = 100
    y = 0

    for i in range(4):

        height = (i + 1) * 3

        if i < bars:
            oled.fill_rect(x + i*6, y + 12 - height, 4, height, 1)
        else:
            oled.rect(x + i*6, y + 12 - height, 4, height, 1)


def oled_dashboard(temp=None, hum=None):

    oled.fill(0)

    oled.text("Pico Monitor", 0, 0)

    # Relay Status
    oled.text("Relay: {}".format(relay_state), 0, 12)

    # Temperature & Humidity
    if temp is not None and hum is not None:
        oled.text("Temp: {}C".format(temp), 0, 26)
        oled.text("Hum : {}%".format(hum), 0, 38)

    # WiFi signal
    if wlan.isconnected():
        try:
            rssi = wlan.status('rssi')
            oled.text("{} dBm".format(rssi), 0, 52)
            draw_wifi_bars(rssi)
        except:
            oled.text("WiFi OK", 0, 52)
    else:
        oled.text("WiFi Lost", 0, 52)

    oled.show()


# =====================================
# WIFI CONNECT FUNCTION
# =====================================
def wifi_connect():

    if wlan.isconnected():
        return

    oled.fill(0)
    oled.text("Connecting WiFi", 0, 20)
    oled.show()

    print("Connecting to WiFi...")

    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    while not wlan.isconnected():
        time.sleep(1)

    ip = wlan.ifconfig()[0]

    print("WiFi Connected:", ip)

    oled.fill(0)
    oled.text("WiFi Connected", 0, 20)
    oled.text(ip, 0, 35)
    oled.show()

    time.sleep(2)


# =====================================
# MQTT CALLBACK
# =====================================
def mqtt_callback(topic, msg):

    global relay_state

    message = msg.decode().strip().upper()

    print("MQTT Message:", message)

    if message == "ON":

        relay.value(0)
        relay_state = "ON"

    elif message == "OFF":

        relay.value(1)
        relay_state = "OFF"

    oled_dashboard()


# =====================================
# MQTT SETUP
# =====================================
client_id = ubinascii.hexlify(machine.unique_id())

client = MQTTClient(
    client_id,
    MQTT_BROKER,
    port=MQTT_PORT,
    keepalive=60
)

client.set_callback(mqtt_callback)


def mqtt_connect():

    while True:

        try:

            oled.fill(0)
            oled.text("Connecting MQTT", 0, 20)
            oled.show()

            print("Connecting to MQTT...")

            client.connect()

            client.subscribe(MQTT_SUBSCRIPTION)

            print("MQTT Connected")

            oled.fill(0)
            oled.text("MQTT Connected", 0, 25)
            oled.show()

            time.sleep(2)

            break

        except Exception as e:

            print("MQTT failed:", e)

            time.sleep(5)


# =====================================
# SENSOR PUBLISH FUNCTION
# =====================================
def publish_sensor_data():

    try:

        sensor.measure()

        temp = sensor.temperature()
        hum = sensor.humidity()

        payload = ujson.dumps({

            "temperature": temp,
            "humidity": hum,
            "relay": relay_state

        })

        client.publish(MQTT_PUBLISH, payload)

        print("Published:", payload)

        oled_dashboard(temp, hum)

    except Exception as e:

        print("Sensor error:", e)


# =====================================
# MAIN PROGRAM
# =====================================
oled_show_startup()

time.sleep(2)

wifi_connect()

mqtt_connect()

last_publish = time.ticks_ms()

while True:

    # Reconnect WiFi if lost
    if not wlan.isconnected():

        print("WiFi lost. Reconnecting...")

        wifi_connect()

        mqtt_connect()

    # Check MQTT messages
    try:

        client.check_msg()

    except Exception as e:

        print("MQTT error:", e)

        mqtt_connect()

    # Publish periodically
    if time.ticks_diff(time.ticks_ms(), last_publish) > PUBLISH_INTERVAL:

        publish_sensor_data()

        last_publish = time.ticks_ms()

    time.sleep(0.1)

