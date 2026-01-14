import sys
import json
import sqlite3
from datetime import datetime

import paho.mqtt.client as mqtt
from PyQt5 import QtWidgets, QtCore, QtGui

import mqtt_init
from app_manager import client_init, send_msg


class MqttMessageEvent(QtCore.QObject):
    message_received = QtCore.pyqtSignal(str, str)


class DataManagerApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Vessel')
        self.resize(1000, 600)

        # Apply a modern dark stylesheet
        STYLE = """
        QWidget { background: #0f1720; color: #d1e8e2; font-family: 'Segoe UI', 'Roboto', Arial; }
        QMainWindow { background: #0f1720; }
        QPushButton { background: #0f9f9a; color: white; border-radius: 8px; padding: 8px 14px; }
        QPushButton#secondary { background: transparent; color: #9fbfc0; border: 1px solid #1f2a33; }
        QFrame#card { background: #0f1b22; border-radius: 12px; padding: 12px; }
        QLabel#metricValue { font-size: 28px; font-weight: 600; color: #ffffff; }
        QLabel#metricLabel { color: #9fbfc0; }
        QTextEdit { background: #071018; border: 1px solid #122027; border-radius: 8px; }
        QDoubleSpinBox { background: #071018; border: 1px solid #122027; color: #d1e8e2; }
        QSlider::handle:horizontal { background: #0f9f9a; }
        QGroupBox { border: none; }
        """
        self.setStyleSheet(STYLE)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)

        # Left: metrics and header
        left = QtWidgets.QVBoxLayout()

        header = QtWidgets.QHBoxLayout()
        header.addStretch()
        title = QtWidgets.QLabel('Vessel')
        title.setStyleSheet('font-size:18px; font-weight:700; color: #e6fff9;')
        title.setAlignment(QtCore.Qt.AlignCenter)
        header.addWidget(title)
        header.addStretch()

        # Right-side small controls (kept at right but title remains centered)
        right_controls = QtWidgets.QHBoxLayout()
        self.btn_connect = QtWidgets.QPushButton('Connect')
        self.btn_connect.setFixedWidth(120)
        self.btn_connect.clicked.connect(self.toggle_connect)
        right_controls.addWidget(self.btn_connect)

        # Console toggle button
        self.btn_toggle_log = QtWidgets.QPushButton('Hide Console')
        self.btn_toggle_log.setCheckable(True)
        self.btn_toggle_log.setChecked(True)
        self.btn_toggle_log.setObjectName('secondary')
        self.btn_toggle_log.clicked.connect(self.toggle_console)
        right_controls.addWidget(self.btn_toggle_log)

        self.lbl_status = QtWidgets.QLabel('Disconnected')
        self.lbl_status.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.lbl_status.setStyleSheet('color: #9fbfc0; margin-left:8px;')
        right_controls.addWidget(self.lbl_status)

        header.addLayout(right_controls)
        left.addLayout(header)

        # Metrics grid
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(14)

        # Temperature card
        temp_card = QtWidgets.QFrame()
        temp_card.setObjectName('card')
        tlay = QtWidgets.QVBoxLayout(temp_card)
        tlay.setAlignment(QtCore.Qt.AlignCenter)
        self.temp_label_value = QtWidgets.QLabel('--')
        self.temp_label_value.setObjectName('metricValue')
        self.temp_label_value.setAlignment(QtCore.Qt.AlignCenter)
        self.temp_label_label = QtWidgets.QLabel('Temperature (°C)')
        self.temp_label_label.setObjectName('metricLabel')
        self.temp_label_label.setAlignment(QtCore.Qt.AlignCenter)
        tlay.addWidget(self.temp_label_value)
        tlay.addWidget(self.temp_label_label)
        grid.addWidget(temp_card, 0, 0)

        # Humidity card
        hum_card = QtWidgets.QFrame()
        hum_card.setObjectName('card')
        hlay = QtWidgets.QVBoxLayout(hum_card)
        hlay.setAlignment(QtCore.Qt.AlignCenter)
        self.hum_label_value = QtWidgets.QLabel('--')
        self.hum_label_value.setObjectName('metricValue')
        self.hum_label_value.setAlignment(QtCore.Qt.AlignCenter)
        self.hum_label_label = QtWidgets.QLabel('Humidity (%)')
        self.hum_label_label.setObjectName('metricLabel')
        self.hum_label_label.setAlignment(QtCore.Qt.AlignCenter)
        hlay.addWidget(self.hum_label_value)
        hlay.addWidget(self.hum_label_label)
        grid.addWidget(hum_card, 0, 1)

        # Lux card
        lux_card = QtWidgets.QFrame()
        lux_card.setObjectName('card')
        llay = QtWidgets.QVBoxLayout(lux_card)
        llay.setAlignment(QtCore.Qt.AlignCenter)
        self.lux_label_value = QtWidgets.QLabel('--')
        self.lux_label_value.setObjectName('metricValue')
        self.lux_label_value.setAlignment(QtCore.Qt.AlignCenter)
        self.lux_label_label = QtWidgets.QLabel('Light (lux)')
        self.lux_label_label.setObjectName('metricLabel')
        self.lux_label_label.setAlignment(QtCore.Qt.AlignCenter)
        llay.addWidget(self.lux_label_value)
        llay.addWidget(self.lux_label_label)
        grid.addWidget(lux_card, 0, 2)

        left.addLayout(grid)

        # Spacer and thresholds group
        left.addSpacing(8)
        thr_group = QtWidgets.QGroupBox()
        thr_layout = QtWidgets.QHBoxLayout(thr_group)
        thr_layout.setAlignment(QtCore.Qt.AlignCenter)
        lbl_t = QtWidgets.QLabel('Temp THR:')
        lbl_t.setAlignment(QtCore.Qt.AlignCenter)
        thr_layout.addWidget(lbl_t)
        self.temp_thr = QtWidgets.QDoubleSpinBox()
        self.temp_thr.setRange(-1000, 1000)
        self.temp_thr.setValue(50.0)
        thr_layout.addWidget(self.temp_thr)
        lbl_h = QtWidgets.QLabel('Hum THR:')
        lbl_h.setAlignment(QtCore.Qt.AlignCenter)
        thr_layout.addWidget(lbl_h)
        self.hum_thr = QtWidgets.QDoubleSpinBox()
        self.hum_thr.setRange(0, 100)
        self.hum_thr.setValue(80.0)
        thr_layout.addWidget(self.hum_thr)
        lbl_l = QtWidgets.QLabel('Lux THR:')
        lbl_l.setAlignment(QtCore.Qt.AlignCenter)
        thr_layout.addWidget(lbl_l)
        self.lux_thr = QtWidgets.QDoubleSpinBox()
        self.lux_thr.setRange(0, 100000)
        self.lux_thr.setValue(1000.0)
        thr_layout.addWidget(self.lux_thr)

        left.addWidget(thr_group)

        layout.addLayout(left, 2)

        # Right: log and controls
        right = QtWidgets.QVBoxLayout()

        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumWidth(360)
        right.addWidget(self.log, 3)

        # DB init
        self.db_path = 'sensor_data.db'
        self._ensure_db()

        # MQTT
        self.client = None
        self.mqtt_events = MqttMessageEvent()
        self.mqtt_events.message_received.connect(self.on_message_gui)

        # keep track if connected
        self._connected = False

        # Latest readings cache
        self.latest = {'temperature': None, 'humidity': None, 'lux': None}

        # Timer to refresh metric cards
        self._display_timer = QtCore.QTimer(self)
        self._display_timer.timeout.connect(self.update_display)
        self._display_timer.start(1000)

        layout.addLayout(right, 1)

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

    def toggle_console(self, checked: bool):
        # Show/hide the log console
        try:
            if self.log is None:
                return
        except Exception:
            return

        visible = self.log.isVisible()
        # toggle based on current visibility or checked state
        if checked:
            # checked means visible
            self.log.setVisible(True)
            self.btn_toggle_log.setText('Hide Console')
        else:
            self.log.setVisible(False)
            self.btn_toggle_log.setText('Show Console')

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
            # cache latest numeric readings for display
            try:
                if 'temperature' in data:
                    self.latest['temperature'] = float(data['temperature'])
            except Exception:
                pass
            try:
                if 'humidity' in data:
                    self.latest['humidity'] = float(data['humidity'])
            except Exception:
                pass
            try:
                if 'lux' in data:
                    self.latest['lux'] = float(data['lux'])
            except Exception:
                pass

            self._process_data(topic, data)

            # immediate UI refresh
            self.update_display()

    def update_display(self):
        # Temperature
        t = self.latest.get('temperature')
        if t is None:
            self.temp_label_value.setText('--')
            self.temp_label_value.setStyleSheet('color: #ffffff')
        else:
            self.temp_label_value.setText(f'{t:.1f}°C')
            if t >= float(self.temp_thr.value()):
                self.temp_label_value.setStyleSheet('color: #ff6b6b')
            else:
                self.temp_label_value.setStyleSheet('color: #9ff4ea')

        # Humidity
        h = self.latest.get('humidity')
        if h is None:
            self.hum_label_value.setText('--')
            self.hum_label_value.setStyleSheet('color: #ffffff')
        else:
            self.hum_label_value.setText(f'{h:.1f}%')
            if h >= float(self.hum_thr.value()):
                self.hum_label_value.setStyleSheet('color: #ff6b6b')
            else:
                self.hum_label_value.setStyleSheet('color: #9ff4ea')

        # Lux
        l = self.latest.get('lux')
        if l is None:
            self.lux_label_value.setText('--')
            self.lux_label_value.setStyleSheet('color: #ffffff')
        else:
            self.lux_label_value.setText(f'{l:.0f}')
            if l >= float(self.lux_thr.value()):
                self.lux_label_value.setStyleSheet('color: #ff6b6b')
            else:
                self.lux_label_value.setStyleSheet('color: #9ff4ea')

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
