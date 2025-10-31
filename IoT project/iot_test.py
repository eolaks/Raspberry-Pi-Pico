import network
import socket
from machine import Pin
import time

# --- Configure LED pin ---
led = Pin(0, Pin.OUT)

# --- Configure Wi-Fi credentials ---
SSID = "YOUR_WIFI_SSID"
PASSWORD = "YOUR_WIFI_PASSWORD"

# --- Connect to Wi-Fi ---
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

print("Connecting to Wi-Fi...", end="")
while not wlan.isconnected():
    print(".", end="")
    time.sleep(0.5)
print("\nConnected to Wi-Fi!")
print("Network config:", wlan.ifconfig())

# --- HTML Page with Buttons ---
def webpage(state):
    html = f"""<!DOCTYPE html>
<html>
<head>
<title>Pico W LED Control</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{ font-family: Arial; text-align: center; background-color: #f2f2f2; }}
h1 {{ color: #333; }}
button {{
  width: 120px; height: 50px; margin: 10px;
  font-size: 18px; border: none; border-radius: 8px;
}}
.on {{ background-color: green; color: white; }}
.off {{ background-color: red; color: white; }}
</style>
</head>
<body>
<h1>Pico W LED Control</h1>
<p>LED is currently <strong>{state}</strong></p>
<p>
<a href="/?led=on"><button class="on">ON</button></a>
<a href="/?led=off"><button class="off">OFF</button></a>
</p>
</body>
</html>"""
    return html

# --- Create a socket server ---
addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
s = socket.socket()
s.bind(addr)
s.listen(1)

print("Web server running at:", wlan.ifconfig()[0])

# --- Main loop ---
while True:
    try:
        cl, addr = s.accept()
        print("Client connected from", addr)
        request = cl.recv(1024)
        request = str(request)
        print("Request:", request)

        led_on = request.find("/?led=on")
        led_off = request.find("/?led=off")

        if led_on == 6:
            print("Turning LED ON")
            led.value(1)
        if led_off == 6:
            print("Turning LED OFF")
            led.value(0)

        state = "ON" if led.value() == 1 else "OFF"
        response = webpage(state)
        cl.send("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n")
        cl.sendall(response)
        cl.close()

    except OSError as e:
        cl.close()
        print("Connection closed")

