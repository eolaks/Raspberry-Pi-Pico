# ==============================
# REQUIRED FOR WEBSOCKET
# ==============================


# ==============================
# IMPORTS
# ==============================
from flask import Flask, render_template
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
import threading
import json

# ==============================
# FLASK APP SETUP
# ==============================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'iot_secret_key'

# Force eventlet async mode
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ==============================
# MQTT CONFIGURATION
# ==============================
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

TOPIC_DATA = "pico/data"
TOPIC_CONTROL = "pico/control"

# ==============================
# MQTT CALLBACKS
# ==============================
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT Broker")
        client.subscribe(TOPIC_DATA)
        print(f"📡 Subscribed to {TOPIC_DATA}")
    else:
        print("❌ Failed to connect to MQTT Broker")


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)

        print("📥 Received:", data)

        # Emit data to all connected browsers
        socketio.emit("update_data", data)

    except Exception as e:
        print("⚠ Error parsing MQTT message:", e)


# ==============================
# START MQTT CLIENT IN BACKGROUND
# ==============================
def start_mqtt():
    mqtt_client.loop_forever()


mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

mqtt_thread = threading.Thread(target=start_mqtt)
mqtt_thread.daemon = True
mqtt_thread.start()

# ==============================
# FLASK ROUTE
# ==============================
@app.route('/')
def index():
    return render_template("index.html")


# ==============================
# HANDLE RELAY CONTROL FROM BROWSER
# ==============================
@socketio.on("relay_control")
def handle_relay_control(data):
    try:
        action = data.get("action")

        if action in ["ON", "OFF"]:
            mqtt_client.publish(TOPIC_CONTROL, action)
            print(f"📤 Sent relay command: {action}")

    except Exception as e:
        print("⚠ Error sending relay command:", e)


# ==============================
# RUN APPLICATION
# ==============================
if __name__ == "__main__":
    print("🚀 Starting Flask-SocketIO Server...")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
