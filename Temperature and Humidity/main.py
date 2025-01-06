"""
Project: Measure environmental temp and hum.
Components: DHT11 and OLED
Microcontroller: Raspberry Pi Pico-w
OES Comapany, Kaduna Nigeria 
+234 8136394461
"""
# import libary

from machine import Pin, I2C
import time
import dht
from ssd1306 import SSD1306_I2C

# OLED dimensions
WIDTH = 128
HEIGHT = 64

# Initialize I2C for OLED
i2c = I2C(0, scl=Pin(1), sda=Pin(0))
oled = SSD1306_I2C(WIDTH, HEIGHT, i2c)

# Initialize DHT11 sensor
dht_sensor = dht.DHT11(Pin(8))

def display_data(temp, hum):
    oled.fill(0)  # Clear the display
    oled.text("DHT11 Sensor", 0, 0)
    oled.text(f"Temp: {temp}C", 0, 20)
    oled.text(f"Humidity: {hum}%", 0, 40)
    oled.show()

while True:
    try:
        dht_sensor.measure()
        temperature = dht_sensor.temperature()
        humidity = dht_sensor.humidity()
        
        # Display on OLED
        display_data(temperature, humidity)
        
        time.sleep(2)  # Delay before the next reading
    except Exception as e:
        print("Error reading sensor:", e)
        time.sleep(2)
