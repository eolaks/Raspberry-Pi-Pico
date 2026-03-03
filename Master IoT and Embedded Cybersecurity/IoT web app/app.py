import os
import logging
import time
import json
import threading
from collections import deque

from flask import Flask, redirect, url_for, render_template, request, session, send_from_directory
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import paho.mqtt.client as mqtt

# ======================================
# LOGGER
# ======================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ======================================
# MQTT CONFIG
# ======================================
MQTT_BROKER = os.environ.get("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_SUBSCRIBE_TOPIC = os.environ.get("MQTT_SUBSCRIBE_TOPIC", "pico/data")
MQTT_CONTROL_TOPIC = os.environ.get("MQTT_CONTROL_TOPIC", "pico/control")

# ======================================
# FLASK CONFIG
# ======================================
server = Flask(__name__)
server.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")
USER_CREDENTIALS = {"admin": "password123"}

# ======================================
# LOGIN SECURITY CONFIG
# ======================================
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME = 300  # 5 minutes (in seconds)

failed_attempts = {}  # {username: {"count": int, "lock_time": timestamp}}



# Serve static images (like logo)
@server.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@server.route('/')
def home():
    return redirect(url_for('login'))

@server.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('username'):
        return redirect('/dashboard/')
    
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user_record = failed_attempts.get(username, {"count": 0, "lock_time": None})

        # Check if user is locked
        if user_record["lock_time"]:
            elapsed = time.time() - user_record["lock_time"]
            if elapsed < LOCKOUT_TIME:
                remaining = int(LOCKOUT_TIME - elapsed)
                error = f"Account locked. Try again in {remaining} seconds."
                return render_template("login.html", error=error)
            else:
                # Reset after lock period
                failed_attempts[username] = {"count": 0, "lock_time": None}

        # Validate credentials
        if USER_CREDENTIALS.get(username) == password:
            session['username'] = username
            failed_attempts[username] = {"count": 0, "lock_time": None}
            return redirect('/dashboard/')
        else:
            # Increment failed attempts
            user_record["count"] += 1

            if user_record["count"] >= MAX_LOGIN_ATTEMPTS:
                user_record["lock_time"] = time.time()
                error = f"Too many failed attempts. Account locked for {LOCKOUT_TIME // 60} minutes."
            else:
                remaining_attempts = MAX_LOGIN_ATTEMPTS - user_record["count"]
                error = f"Incorrect username or password. {remaining_attempts} attempts remaining."

            failed_attempts[username] = user_record

    return render_template("login.html", error=error)

@server.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@server.before_request
def protect_dashboard():
    if request.path.startswith('/dashboard') and not session.get('username'):
        return redirect(url_for('login'))

# ======================================
# GLOBAL DATA
# ======================================
MAX_LEN = 50
temperature_history = deque(maxlen=MAX_LEN)
humidity_history = deque(maxlen=MAX_LEN)

current_temp = 0
current_humidity = 0
relay_status = "OFF"
last_mqtt_update = time.time()
mqtt_connected = False
data_lock = threading.Lock()  # Thread-safe updates

# ======================================
# MQTT HANDLERS
# ======================================
def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        logging.info("Connected to MQTT Broker")
        client.subscribe(MQTT_SUBSCRIBE_TOPIC)
        mqtt_connected = True
    else:
        logging.error(f"Failed to connect to MQTT Broker, return code {rc}")
        mqtt_connected = False

def on_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False
    logging.warning("MQTT Broker disconnected!")

def on_message(client, userdata, msg):
    global current_temp, current_humidity, relay_status, last_mqtt_update
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        with data_lock:
            current_temp = payload.get("temperature", 0)
            current_humidity = payload.get("humidity", 0)
            relay_status = payload.get("relay", "OFF")
            temperature_history.append(current_temp)
            humidity_history.append(current_humidity)
            last_mqtt_update = time.time()
    except Exception as e:
        logging.error(f"MQTT message error: {e}")

# Persistent MQTT client
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message

def mqtt_loop():
    while True:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            mqtt_client.loop_forever()
        except Exception as e:
            logging.error(f"MQTT connection failed: {e}")
            time.sleep(5)

threading.Thread(target=mqtt_loop, daemon=True).start()

# ======================================
# DASH SETUP
# ======================================
app = dash.Dash(
    __name__,
    server=server,
    url_base_pathname='/dashboard/',
    external_stylesheets=[dbc.themes.CYBORG]
)

# ======================================
# GAUGE GENERATOR
# ======================================
def generate_gauge(value, title, unit, max_val):
    color = "#FF4136" if value > 40 else "#2ECC40"
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        delta={'reference': 25, 'relative': True},
        number={'suffix': f" {unit}"},
        gauge={'axis': {'range': [0, max_val]},
               'bar': {'color': color},
               'steps': [{'range': [0, max_val*0.7], 'color': "#3D9970"},
                         {'range': [max_val*0.7, max_val], 'color': "#FF4136"}],
               'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': max_val*0.9}}
    ))
    fig.update_layout(title={'text': title, 'x': 0.5})
    return fig

# ======================================
# DASH LAYOUT
# ======================================
app.layout = dbc.Container([
    # Header with logo
    dbc.Row([
        dbc.Col(html.Img(src='/static/maaun_logo.jpg', height='60px'), width=2),
        dbc.Col(html.H3("       IoT Monitoring Dashboard", className="fw-bold text-info"), width=8),
        dbc.Col(html.A(dbc.Button("Logout", color="danger"), href="/logout"), width=2, className="text-end")
    ], className="my-3 align-items-center"),

    # Gauges and relay control
    dbc.Row([
        # Temperature
        dbc.Col(dbc.Card([
            dbc.CardHeader("Temperature"),
            dbc.CardBody([
                dcc.Graph(id='temp-gauge', config={'displayModeBar': False}),
                dbc.Badge(id="temp-alert", className="mt-2", color="secondary"),
                html.Div(id="temp-last-update", className="mt-1 text-muted")
            ])
        ], className="shadow-lg"), md=4),

        # Humidity
        dbc.Col(dbc.Card([
            dbc.CardHeader("Humidity"),
            dbc.CardBody([
                dcc.Graph(id='humidity-gauge', config={'displayModeBar': False}),
                dbc.Badge(id="humidity-alert", className="mt-2", color="secondary"),
                html.Div(id="humidity-last-update", className="mt-1 text-muted")
            ])
        ], className="shadow-lg"), md=4),

        # Relay Control Panel
        dbc.Col(dbc.Card([
            dbc.CardHeader("Relay Control"),
            dbc.CardBody([
                # Relay Status
                dbc.Row([
                    dbc.Col(html.H6("Relay Status:", className="fw-bold"), width=5),
                    dbc.Col(dbc.Badge(id="relay-badge", color="secondary", className="text-white"), width=7)
                ], className="mb-3 align-items-center"),

                # ON/OFF Buttons
                dbc.Row([
                    dbc.Col(dbc.Button("Turn ON", id="relay-on", color="success", className="w-100"), md=6),
                    dbc.Col(dbc.Button("Turn OFF", id="relay-off", color="danger", className="w-100"), md=6)
                ], className="mb-3 g-2"),

                # MQTT Status
                dbc.Row([
                    dbc.Col(html.H6("MQTT Status:", className="fw-bold"), width=5),
                    dbc.Col(dbc.Badge(id="mqtt-status", color="secondary", className="text-white"), width=7)
                ], className="align-items-center")
            ])
        ], className="shadow-lg text-center"), md=4)
    ], className="mb-4"),

    # Historical charts
    dbc.Row([
        dbc.Col(dbc.Card([dbc.CardHeader("Temperature History"), dbc.CardBody([dcc.Graph(id="temp-chart")])], className="shadow-lg"), md=6),
        dbc.Col(dbc.Card([dbc.CardHeader("Humidity History"), dbc.CardBody([dcc.Graph(id="humidity-chart")])], className="shadow-lg"), md=6)
    ], className="mb-4"),

    # Interval for updates
    dcc.Interval(id="interval", interval=2000, n_intervals=0)
], fluid=True)

# ======================================
# RELAY BUTTON CALLBACK
# ======================================
@app.callback(
    Output('relay-badge', 'children'),
    Output('relay-badge', 'color'),
    Input('relay-on', 'n_clicks'),
    Input('relay-off', 'n_clicks')
)
def relay_control(on_clicks, off_clicks):
    global relay_status
    ctx = dash.callback_context
    if not ctx.triggered:
        color = "success" if relay_status == "ON" else "danger"
        return relay_status, color

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if button_id == "relay-on":
        relay_status = "ON"
    elif button_id == "relay-off":
        relay_status = "OFF"

    try:
        mqtt_client.publish(MQTT_CONTROL_TOPIC, relay_status)
        logging.info(f"Relay state published: {relay_status}")
    except Exception as e:
        logging.error(f"Failed to publish relay: {e}")

    color = "success" if relay_status == "ON" else "danger"
    return relay_status, color

# ======================================
# DASH UPDATE CALLBACK (GAUGES + CHARTS + ALERTS + TIMESTAMP)
# ======================================
@app.callback(
    Output('temp-gauge', 'figure'),
    Output('humidity-gauge', 'figure'),
    Output('temp-chart', 'figure'),
    Output('humidity-chart', 'figure'),
    Output('temp-alert', 'children'),
    Output('temp-alert', 'color'),
    Output('humidity-alert', 'children'),
    Output('humidity-alert', 'color'),
    Output('mqtt-status', 'children'),
    Output('mqtt-status', 'color'),
    Output('temp-last-update', 'children'),
    Output('humidity-last-update', 'children'),
    Input('interval', 'n_intervals')
)
def update_dashboard(n):
    with data_lock:
        # Gauges
        temp_fig = generate_gauge(current_temp, "Temperature", "°C", 50)
        humidity_fig = generate_gauge(current_humidity, "Humidity", "%", 100)

        # Charts
        temp_chart = go.Figure(go.Scatter(y=list(temperature_history), mode="lines+markers", line={'color': '#FF851B'}, name="Temperature"))
        temp_chart.update_layout(title="Temperature History", template="plotly_dark")

        humidity_chart = go.Figure(go.Scatter(y=list(humidity_history), mode="lines+markers", line={'color': '#0074D9'}, name="Humidity"))
        humidity_chart.update_layout(title="Humidity History", template="plotly_dark")

        # Alerts
        temp_alert = "Normal" if current_temp <= 40 else "High Temperature!"
        temp_color = "success" if current_temp <= 40 else "danger"

        humidity_alert = "Normal" if current_humidity <= 70 else "High Humidity!"
        humidity_color = "success" if current_humidity <= 70 else "warning"

        mqtt_text = "MQTT Connected" if mqtt_connected else "MQTT Disconnected!"
        mqtt_color = "success" if mqtt_connected else "danger"

        # Last updated timestamp & offline warning if >10s
        elapsed = time.time() - last_mqtt_update
        last_update_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_mqtt_update))
        if elapsed > 10:
            timestamp_color = "text-danger"
            offline_warning = " ⚠ Sensor offline!"
        else:
            timestamp_color = "text-muted"
            offline_warning = ""

        temp_last_update = html.Span(f"Last Updated: {last_update_str}{offline_warning}", className=timestamp_color)
        humidity_last_update = html.Span(f"Last Updated: {last_update_str}{offline_warning}", className=timestamp_color)

        return temp_fig, humidity_fig, temp_chart, humidity_chart, temp_alert, temp_color, humidity_alert, humidity_color, mqtt_text, mqtt_color, temp_last_update, humidity_last_update

# ======================================
# RUN
# ======================================
if __name__ == "__main__":
    server.run(debug=False, host="0.0.0.0", port=8050)
