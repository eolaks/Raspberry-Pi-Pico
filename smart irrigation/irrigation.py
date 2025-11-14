# Smart Irrigation System - Complete MicroPython Code for Raspberry Pi Pico-W
# - OLED (SSD1306) SDA -> GP0, SCL -> GP1 (I2C)
# - Capacitive Soil Moisture ADC -> GP27
# - Relay (pump) -> GP18 (default active low)
# - Passive buzzer (PWM) -> GP19  <-- NOTE: moved to GP19 to avoid pin conflict
# - DHT22 -> GP2
#
# Features:
#  - Reads soil moisture, temperature, humidity continuously
#  - Displays readings on SSD1306 OLED
#  - Controls a relay-driven pump using soil + environment logic with hysteresis
#  - Produces short periodic beeps while pump is ON
#  - Produces multi-beep critical alerts when moisture or temperature is dangerous
#
# Requirements:
#  - MicroPython build for Pico/W with 'ssd1306.py' driver available on the device

from machine import Pin, I2C, ADC, PWM
import utime
import dht
import ssd1306

# ----------------------------
# CONFIGURABLE PARAMETERS
# ----------------------------

# Pin mapping
I2C_SDA_PIN = 0        # GP0
I2C_SCL_PIN = 1        # GP1
SOIL_ADC_PIN = 27      # GP27
DHT_PIN = 2           # GP2
RELAY_PIN = 13        # GP18
BUZZER_PIN = 18        # GP19 (use separate pin from relay)

# OLED settings
OLED_WIDTH = 128
OLED_HEIGHT = 64

# Soil calibration: change these after measuring your sensor wet/dry ADC values
SOIL_WET_ADC = 30000    # ADC reading when soil is very wet (example)
SOIL_DRY_ADC = 56000    # ADC reading when soil is very dry (example)

# Moisture thresholds (percent)
MOISTURE_THRESHOLD_LOW = 40        # below -> request irrigation
MOISTURE_THRESHOLD_OFF = 55        # above -> stop irrigation (hysteresis)
MOISTURE_CRITICAL = 20             # below -> critical alert (buzzer pattern)

# Temperature & humidity thresholds
TEMP_HIGH = 35.0            # above -> environment may request irrigation (if humidity low)
TEMP_HIGH_CRITICAL = 40.0   # dangerous high temperature -> critical alert
HUMIDITY_LOW = 25.0         # below -> considered low humidity

# Timing and behavior
IRRIGATION_MIN_ON_SECONDS = 10    # minimum pump on time to avoid rapid cycling
SENSOR_READ_INTERVAL = 5          # seconds between sensor reads
DISPLAY_REFRESH_INTERVAL = 2      # seconds between OLED updates
BUZZER_BEEP_DURATION = 0.05       # seconds, used for short beeps
BUZZER_BEEP_PAUSE = 0.2           # pause between beeps in patterns
BUZZER_PWM_FREQ = 2000            # PWM frequency for passive buzzer (Hz)

# Relay level (True if relay is active LOW)
RELAY_ACTIVE_LOW = True

# Buzzer enable (set False to disable buzzer)
ENABLE_BUZZER = True

# ----------------------------
# HARDWARE SETUP
# ----------------------------

# Setup I2C for OLED
i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=400000)
oled = ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)

# Soil moisture ADC
soil_adc = ADC(Pin(SOIL_ADC_PIN))

# DHT22 sensor
dht_sensor = dht.DHT22(Pin(DHT_PIN))

# Relay (pump) pin
relay_pin = Pin(RELAY_PIN, Pin.OUT)

# Buzzer (PWM)
buzzer_pwm = PWM(Pin(BUZZER_PIN))
buzzer_pwm.freq(BUZZER_PWM_FREQ)
buzzer_pwm.duty_u16(0)  # silent initially

# ----------------------------
# HELPER / UTILITY FUNCTIONS
# ----------------------------

def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x

def map_adc_to_percent(adc_value):
    """
    Map ADC read_u16 (0..65535) to 0..100% soil moisture using calibration.
    Assumes SOIL_WET_ADC corresponds to 100% and SOIL_DRY_ADC to 0%.
    """
    if SOIL_DRY_ADC == SOIL_WET_ADC:
        return 0.0
    percent = (SOIL_DRY_ADC - adc_value) * 100.0 / (SOIL_DRY_ADC - SOIL_WET_ADC)
    return clamp(percent, 0.0, 100.0)

def read_soil_moisture_percent():
    raw = soil_adc.read_u16()
    pct = map_adc_to_percent(raw)
    return pct, raw

def read_dht():
    """
    Return (temp_c, hum_percent) or (None, None) on read failure.
    """
    try:
        dht_sensor.measure()
        temp = float(dht_sensor.temperature())
        hum = float(dht_sensor.humidity())
        return temp, hum
    except Exception:
        return None, None

def relay_on():
    if RELAY_ACTIVE_LOW:
        relay_pin.value(0)
    else:
        relay_pin.value(1)

def relay_off():
    if RELAY_ACTIVE_LOW:
        relay_pin.value(1)
    else:
        relay_pin.value(0)

# ----------------------------
# BUZZER FUNCTIONS
# ----------------------------

def buzzer_beep(duration=BUZZER_BEEP_DURATION, duty=32768, freq=None):
    """
    Play a single beep using PWM for a passive buzzer.
    - duration: seconds
    - duty: 0..65535 (use smaller value for softer beep)
    - freq: optional frequency override
    """
    if not ENABLE_BUZZER:
        return
    if freq is not None:
        buzzer_pwm.freq(freq)
    buzzer_pwm.duty_u16(int(duty))
    utime.sleep(duration)
    buzzer_pwm.duty_u16(0)

def buzzer_alert_pattern(times=4):
    """
    Critical alert pattern (multiple beeps). Blocks while playing the pattern.
    This is used for critical low moisture or dangerously high temp.
    """
    if not ENABLE_BUZZER:
        return
    for _ in range(times):
        buzzer_beep(duration=0.12, duty=40000)
        utime.sleep(BUZZER_BEEP_PAUSE)

def buzzer_pump_beep():
    """
    Short gentle beep while pump is ON to indicate pump activity.
    Non-blocking aside from a very short sleep; intended to be called once per loop.
    """
    if not ENABLE_BUZZER:
        return
    # Softer, very short beep
    buzzer_beep(duration=0.04, duty=15000)

# ----------------------------
# DISPLAY
# ----------------------------

def display_values(soil_pct, soil_raw, temp, hum, pump_state):
    oled.fill(0)
    oled.text("Smart Irrigation", 0, 0)
    oled.text("Soil: {:>3.0f}%".format(soil_pct), 0, 16)
    oled.text("ADC: {:5d}".format(int(soil_raw)), 76, 16)
    if temp is None or hum is None:
        oled.text("DHT: read error", 0, 32)
    else:
        oled.text("T:{:>5.1f}C H:{:>3.0f}%".format(temp, hum), 0, 32)
    oled.text("Pump: {}".format("ON" if pump_state else "OFF"), 0, 48)
    oled.show()

# ----------------------------
# CONTROL LOGIC
# ----------------------------

def needs_irrigation(soil_pct, temp, hum):
    """
    Return True if irrigation should be started:
      - soil below MOISTURE_THRESHOLD_LOW
      OR
      - (temperature high AND humidity low)
    """
    soil_condition = soil_pct < MOISTURE_THRESHOLD_LOW
    env_condition = False
    if temp is not None and hum is not None:
        env_condition = (temp > TEMP_HIGH and hum < HUMIDITY_LOW)
    return soil_condition or env_condition

def safe_to_turn_off(soil_pct, temp, hum):
    """
    Return True when it's safe to turn pump OFF:
      - soil above MOISTURE_THRESHOLD_OFF (hysteresis)
      AND
      - environment not demanding (temp/humidity not requiring irrigation)
    """
    soil_ok = soil_pct > MOISTURE_THRESHOLD_OFF
    env_ok = True
    if temp is not None and hum is not None:
        env_ok = not (temp > TEMP_HIGH and hum < HUMIDITY_LOW)
    return soil_ok and env_ok

# ----------------------------
# MAIN LOOP
# ----------------------------

def main():
    # Initialize hardware states
    relay_off()
    buzzer_pwm.duty_u16(0)

    pump_is_on = False
    last_pump_change_ts = 0
    last_display_ts = 0

    while True:
        loop_start = utime.time()

        # Read sensors
        soil_pct, soil_raw = read_soil_moisture_percent()
        temp, hum = read_dht()

        # Check critical conditions (take immediate precedence)
        critical_moisture = soil_pct < MOISTURE_CRITICAL
        critical_temp = (temp is not None and temp >= TEMP_HIGH_CRITICAL)

        if critical_moisture or critical_temp:
            # Play critical alert pattern (blocks while playing)
            buzzer_alert_pattern(times=4)

        # Decide pump action
        if pump_is_on:
            # While pump ON produce short periodic beep (non-critical)
            # But do not produce pump beep if we just played critical pattern (pattern already made audible noise)
            # We simply still call the pump beep; the device will play a short beep after pattern
            buzzer_pump_beep()

            # Check if it's safe to turn off, respecting minimum ON time
            if safe_to_turn_off(soil_pct, temp, hum):
                elapsed_on = utime.time() - last_pump_change_ts
                if elapsed_on >= IRRIGATION_MIN_ON_SECONDS:
                    relay_off()
                    pump_is_on = False
                    last_pump_change_ts = utime.time()
                    # single short confirmation beep
                    buzzer_beep(duration=0.08, duty=30000)
        else:
            # Pump currently OFF: determine whether to start it
            if needs_irrigation(soil_pct, temp, hum):
                relay_on()
                pump_is_on = True
                last_pump_change_ts = utime.time()
                # single short confirmation beep
                buzzer_beep(duration=0.05, duty=30000)

        # Update OLED at a separate (shorter) cadence to avoid flicker
        if utime.time() - last_display_ts >= DISPLAY_REFRESH_INTERVAL:
            display_values(soil_pct, soil_raw, temp, hum, pump_is_on)
            last_display_ts = utime.time()

        # Sleep until next cycle (try to keep SENSOR_READ_INTERVAL cadence)
        elapsed = utime.time() - loop_start
        sleep_time = SENSOR_READ_INTERVAL - elapsed
        if sleep_time > 0:
            utime.sleep(sleep_time)
        else:
            # if the loop took longer than interval, yield briefly
            utime.sleep(0.05)

# ----------------------------
# ENTRY
# ----------------------------

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Safe shutdown on manual interrupt
        relay_off()
        buzzer_pwm.duty_u16(0)
        print("Smart irrigation stopped by user")
