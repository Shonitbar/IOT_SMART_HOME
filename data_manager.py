import sys
import json
import sqlite3
import threading
from datetime import datetime

import requests
import paho.mqtt.client as mqtt
from PyQt5 import QtWidgets, QtCore

import mqtt_init
from app_manager import client_init, send_msg


class MqttMessageEvent(QtCore.QObject):
    message_received = QtCore.pyqtSignal(str, str)


class DataManagerApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Simple Data Manager')
        self.resize(800, 480)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # Controls
        controls = QtWidgets.QHBoxLayout()
        self.btn_connect = QtWidgets.QPushButton('Connect')
        self.btn_connect.clicked.connect(self.toggle_connect)
        controls.addWidget(self.btn_connect)

        self.lbl_status = QtWidgets.QLabel('Disconnected')
        controls.addWidget(self.lbl_status)

        controls.addStretch()

        layout.addLayout(controls)

        # Threshold controls
        thr_layout = QtWidgets.QHBoxLayout()
        thr_layout.addWidget(QtWidgets.QLabel('Temp THR:'))
        self.temp_thr = QtWidgets.QDoubleSpinBox()
        self.temp_thr.setRange(-1000, 1000)
        self.temp_thr.setValue(50.0)
        thr_layout.addWidget(self.temp_thr)

        thr_layout.addWidget(QtWidgets.QLabel('Hum THR:'))
        self.hum_thr = QtWidgets.QDoubleSpinBox()
        self.hum_thr.setRange(0, 100)
        self.hum_thr.setValue(80.0)
        thr_layout.addWidget(self.hum_thr)

        thr_layout.addWidget(QtWidgets.QLabel('Lux THR:'))
        self.lux_thr = QtWidgets.QDoubleSpinBox()
        self.lux_thr.setRange(0, 100000)
        self.lux_thr.setValue(1000.0)
        thr_layout.addWidget(self.lux_thr)

        layout.addLayout(thr_layout)

        # Log view
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        # DB init
        self.db_path = 'sensor_data.db'
        self._ensure_db()

        # MQTT
        self.client = None
        self.mqtt_events = MqttMessageEvent()
        self.mqtt_events.message_received.connect(self.on_message_gui)

        # keep track if connected
        self._connected = False

    def _ensure_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT,
                    topic TEXT,
                    payload TEXT
                )
            ''')
            conn.commit()
        finally:
            conn.close()

    def toggle_connect(self):
        if not self._connected:
            self.connect_mqtt()
        else:
            self.disconnect_mqtt()

    def connect_mqtt(self):
        self.append_log('Connecting to MQTT broker...')
        try:
            self.client = client_init('DataMgr-')
        except Exception as e:
            self.append_log('MQTT client init failed: ' + str(e))
            return

        # override on_message to forward to Qt thread
        def _on_message(client, userdata, msg):
            topic = msg.topic
            payload = msg.payload.decode('utf-8', 'ignore')
            # emit to GUI thread
            self.mqtt_events.message_received.emit(topic, payload)

        self.client.on_message = _on_message
        try:
            # subscribe to common topic prefix
            sub = mqtt_init.comm_topic + '#'
            self.client.subscribe(sub)
            self.client.loop_start()
            self._connected = True
            self.btn_connect.setText('Disconnect')
            self.lbl_status.setText('Connected')
            self.append_log('Subscribed to: ' + sub)
        except Exception as e:
            self.append_log('MQTT connect/subscribe failed: ' + str(e))

    def disconnect_mqtt(self):
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
        self._connected = False
        self.btn_connect.setText('Connect')
        self.lbl_status.setText('Disconnected')
        self.append_log('Disconnected from broker')

    def append_log(self, text):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.log.append(f'[{ts}] {text}')

    @QtCore.pyqtSlot(str, str)
    def on_message_gui(self, topic, payload):
        self.append_log(f'MQTT {topic}: {payload}')
        # Save to DB
        self._save_message(topic, payload)
        # Process payload
        try:
            data = json.loads(payload)
        except Exception:
            data = None

        if isinstance(data, dict):
            self._process_data(topic, data)

    def _save_message(self, topic, payload):
        conn = sqlite3.connect(self.db_path)
        try:
            c = conn.cursor()
            c.execute('INSERT INTO messages (ts, topic, payload) VALUES (?, ?, ?)',
                      (datetime.now().isoformat(), topic, payload))
            conn.commit()
        finally:
            conn.close()

    def _process_data(self, topic, data):
        # Check for common sensor keys and thresholds
        alarms = []
        if 'temperature' in data:
            try:
                t = float(data['temperature'])
                if t >= float(self.temp_thr.value()):
                    alarms.append(f'Temperature high: {t}')
            except Exception:
                pass

        if 'humidity' in data:
            try:
                h = float(data['humidity'])
                if h >= float(self.hum_thr.value()):
                    alarms.append(f'Humidity high: {h}')
            except Exception:
                pass

        if 'lux' in data:
            try:
                l = float(data['lux'])
                if l >= float(self.lux_thr.value()):
                    alarms.append(f'Light (lux) high: {l}')
            except Exception:
                pass

        # Gas threshold from mqtt_init
        if 'gas_weight' in data:
            try:
                g = float(data['gas_weight'])
                if g >= float(mqtt_init.gas_weight_THR):
                    alarms.append(f'Gas weight alarm: {g}')
            except Exception:
                pass

        if alarms:
            msg = ' | '.join(alarms)
            self.append_log('ALARM: ' + msg)
            # publish alarm
            try:
                send_msg(self.client, mqtt_init.topic_alarm, msg)
            except Exception as e:
                self.append_log('Failed to send alarm: ' + str(e))
            # show GUI alert
            QtWidgets.QMessageBox.warning(self, 'Alarm', msg)


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = DataManagerApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
