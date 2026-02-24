# ===========================
# STEP 1 - IMPORT LIBRARIES
# ===========================
from machine import Pin, I2C, PWM
import time
import dht
import ssd1306
import network
import urequests

# ===========================
# STEP 2 - INITIALIZE HARDWARE
# ===========================

# ---- WiFi Credentials ----
WIFI_SSID = "xxxxxxx" # repalce with your SSID 
WIFI_PASSWORD = "xxxxxxx"		# replace with your password

# SSID = "Galaxy A73 5GA010"
# PASSWORD = "step0000"  # replace with your Wi-Fi password
# 

# ---- ThingSpeak Details ----
THINGSPEAK_API_KEY = "xxxxxxxxx" # repalce with your API write key
THINGSPEAK_URL = "https://api.thingspeak.com/update"

# ---- OLED (I2C) ----
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# ---- DHT11 ----
sensor = dht.DHT11(Pin(2))

# ---- Relay ----
relay = Pin(6, Pin.OUT)
relay.on()   # Relay OFF initially

# ---- Passive Buzzer ----
buzzer = PWM(Pin(18))
buzzer.duty_u16(0)

# ===========================
# STEP 3 - THRESHOLD VALUE
# ===========================
TEMP_THRESHOLD = 30

# ===========================
# STEP 4 - FUNCTIONS
# ===========================

# Connect to WiFi
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    oled.fill(0)
    oled.text("Connecting WiFi", 0, 20)
    oled.show()

    timeout = 10
    while not wlan.isconnected() and timeout > 0:
        time.sleep(1)
        timeout -= 1

    if wlan.isconnected():
        oled.fill(0)
        oled.text("WiFi Connected", 0, 20)
        oled.show()
        time.sleep(1)
        print("Connected:", wlan.ifconfig())
    else:
        oled.fill(0)
        oled.text("WiFi Failed", 0, 20)
        oled.show()
        print("WiFi connection failed")

# Read DHT11 Sensor
def read_dht11():
    try:
        sensor.measure()
        temp = sensor.temperature()
        hum = sensor.humidity()
        return temp, hum
    except:
        return None, None

# Update OLED Display
def update_oled(temp, hum, relay_state):
    oled.fill(0)
    oled.text("Temp & Humidity", 0, 0)
    oled.text("Temp: {} C".format(temp), 0, 20)
    oled.text("Hum : {} %".format(hum), 0, 35)
    oled.text("Relay: {}".format(relay_state), 0, 50)
    oled.show()

# Relay Control Logic
def control_relay(temp):
    if temp >= TEMP_THRESHOLD:
        relay.off()  # Active Low
        return 1   # ON (for ThingSpeak)
    else:
        relay.on()
        return 0   # OFF (for ThingSpeak)

# Buzzer Alarm Logic
def buzzer_alert(temp):
    if temp >= TEMP_THRESHOLD:
        buzzer.freq(2000)
        buzzer.duty_u16(30000)
        time.sleep(0.2)
        buzzer.duty_u16(0)
    else:
        buzzer.duty_u16(0)

# Send Data to ThingSpeak
def send_to_thingspeak(temp, hum, relay_status):
    try:
        url = "{}?api_key={}&field1={}&field2={}&field3={}".format(
            THINGSPEAK_URL,
            THINGSPEAK_API_KEY,
            temp,
            hum,
            relay_status
        )
        response = urequests.get(url)
        response.close()
        print("Data sent to ThingSpeak")
    except Exception as e:
        print("ThingSpeak Error:", e)

# ===========================
# STEP 5 - MAIN PROGRAM
# ===========================

# Connect to WiFi
connect_wifi()

oled.fill(0)
oled.text("System Starting", 0, 20)
oled.show()
time.sleep(2)

last_update = time.time()

while True:
    temp, hum = read_dht11()

    if temp is not None:
        relay_status = control_relay(temp)   # 1 = ON, 0 = OFF
        buzzer_alert(temp)
        update_oled(temp, hum, "ON" if relay_status == 1 else "OFF")

        # Send data every 15 seconds (ThingSpeak rule)
        if time.time() - last_update >= 15:
            send_to_thingspeak(temp, hum, relay_status)
            last_update = time.time()

    else:
        oled.fill(0)
        oled.text("Sensor Error", 0, 20)
        oled.show()

    time.sleep(2)

