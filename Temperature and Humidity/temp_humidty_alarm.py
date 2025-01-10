"""
Project: Measure environmental temp and hum.
Components: DHT11 and OLED
Microcontroller: Raspberry Pi Pico-w
jan 11, 2025
OES 
"""
# import libary
from machine import Pin, I2C, PWM
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

# Initialize PWM for buzzer
buzzer = PWM(Pin(18))

# threshold value
temp_threshold = 35
hum_threshold = 30

def sound_buzzer(frequency=1000, duration=0.5):
    """
    Sound the buzzer with the specified frequency and duration.
    """
    buzzer.freq(frequency)  # Set the frequency
    buzzer.duty_u16(32768)  # Set duty cycle to 50% (max is 65535)
    update_alarm_status("Alarm ON")  # Show alarm status on OLED
    time.sleep(duration)    # Duration of the sound
    buzzer.duty_u16(0)      # Turn off the buzzer
    update_alarm_status("Alarm OFF")  # Update alarm status on OLED

def update_alarm_status(status):
    """
    Clear the alarm status area and update it with the given status.
    """
    oled.fill_rect(0, 50, WIDTH, 14, 0)  # Clear the area for the alarm status
    oled.text(status, 0, 50)  # Display the new alarm status
    oled.show()

def display_data(temp, hum):
    """
    Display temperature and humidity on the OLED.
    """
    oled.fill(0)  # Clear the display
    oled.text("DHT11 Sensor", 0, 0)
    oled.text(f"Temp: {temp}C", 0, 20)
    oled.text(f"Humidity: {hum}%", 0, 35)
    update_alarm_status("Alarm OFF")  # Default alarm status
    oled.show()


while True:
    try:
        dht_sensor.measure()
        temperature = dht_sensor.temperature()
        humidity = dht_sensor.humidity()
        
        # Display temperature and humidity on OLED
        display_data(temperature, humidity)
        
        # Check conditions and sound buzzer if necessary
        if temperature > temp_threshold or humidity > hum_threshold:
            # Use different frequencies for temperature and humidity warnings
            if temperature > temp_threshold:
                sound_buzzer(frequency=1500, duration=0.5)
            if humidity > hum_threshold:
                sound_buzzer(frequency=1000, duration=0.5)
        
        time.sleep(2)  # Delay before the next reading
    except Exception as e:
        print("Error reading sensor:", e)
        time.sleep(2)
