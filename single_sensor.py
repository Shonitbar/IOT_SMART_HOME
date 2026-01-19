#!/usr/bin/env python3
"""
Single Sensor Publisher GUI
Select room and sensor type to publish sensor data
The data_manager will automatically parse it
"""

import paho.mqtt.client as mqtt
import time
import json
import random
import math
import socket
import threading
from PyQt5 import QtWidgets, QtCore

import room_config

# MQTT Configuration
nb = 1  # 0 = HIT, 1 = HiveMQ (open)
brokers = [str(socket.gethostbyname('vmm1.saaintertrade.com')), str(socket.gethostbyname('broker.hivemq.com'))]
ports = ['80', '1883']
usernames = ['MATZI', '']
passwords = ['MATZI', '']

broker_ip = brokers[nb]
port = ports[nb]
username = usernames[nb]
password = passwords[nb]


class SensorData:
    """Generates realistic sensor values"""
    def __init__(self):
        self.time_offset = random.uniform(0, 10)
        self.base_temp = 22
        self.base_humidity = 50
        self.base_lux = 800
    
    def get_temperature(self):
        variation = 2 * math.sin(time.time() / 30 + self.time_offset)
        noise = random.gauss(0, 0.3)
        return round(self.base_temp + variation + noise, 1)
    
    def get_humidity(self):
        variation = 8 * math.sin(time.time() / 40 + self.time_offset)
        noise = random.gauss(0, 0.5)
        return round(max(10, min(100, self.base_humidity + variation + noise)), 1)
    
    def get_light(self):
        variation = self.base_lux * 0.3 * math.sin(time.time() / 60 + self.time_offset)
        noise = random.gauss(0, self.base_lux * 0.05)
        return round(max(0, self.base_lux + variation + noise), 0)


class SingleSensorGUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Smart Home Sensor Publisher')
        self.resize(700, 550)
        
        # Dark theme
        STYLE = """
        QWidget { background: #0f1720; color: #d1e8e2; font-family: 'Segoe UI', 'Roboto', Arial; }
        QMainWindow { background: #0f1720; }
        QPushButton { background: #0f9f9a; color: white; border-radius: 8px; padding: 10px 16px; font-weight: bold; }
        QComboBox { background: #071018; border: 1px solid #122027; color: #d1e8e2; padding: 6px; }
        QLineEdit { background: #071018; border: 1px solid #122027; color: #d1e8e2; padding: 6px; }
        QDoubleSpinBox { background: #071018; border: 1px solid #122027; color: #d1e8e2; padding: 6px; }
        QCheckBox { color: #d1e8e2; }
        QGroupBox { border: 1px solid #122027; border-radius: 8px; color: #d1e8e2; padding: 12px; margin-top: 12px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }
        QTextEdit { background: #071018; border: 1px solid #122027; color: #d1e8e2; }
        """
        self.setStyleSheet(STYLE)
        
        # MQTT setup
        self.client = None
        self.is_connected = False
        self.is_publishing = False
        self.publish_thread = None
        self.sensor_data = SensorData()
        
        # Main layout
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Title
        title = QtWidgets.QLabel('Sensor Publisher')
        title.setStyleSheet('font-size:18px; font-weight:800; color: #e6fff9;')
        layout.addWidget(title)
        
        # Broker info
        broker_info = QtWidgets.QLabel(f'📡 Broker: {broker_ip}:{port}')
        broker_info.setStyleSheet('color: #9fbfc0; font-size: 11px;')
        layout.addWidget(broker_info)
        
        # Room Selection Section
        room_group = QtWidgets.QGroupBox("Room Selection")
        room_layout = QtWidgets.QVBoxLayout()
        
        room_select_layout = QtWidgets.QHBoxLayout()
        room_select_layout.addWidget(QtWidgets.QLabel("Room:"), 0)
        self.room_combo = QtWidgets.QComboBox()
        self.room_combo.addItems(room_config.get_room_names())
        self.room_combo.setCurrentIndex(0)
        room_select_layout.addWidget(self.room_combo, 1)
        room_layout.addLayout(room_select_layout)
        
        room_group.setLayout(room_layout)
        layout.addWidget(room_group)
        
        # Connect room selection change to update topics
        self.room_combo.currentTextChanged.connect(self.update_topics)
        
        # Temperature Section
        temp_group = QtWidgets.QGroupBox("Temperature Sensor")
        temp_layout = QtWidgets.QVBoxLayout()
        
        temp_enable_layout = QtWidgets.QHBoxLayout()
        self.temp_check = QtWidgets.QCheckBox("Enable Temperature")
        self.temp_check.setChecked(True)
        temp_enable_layout.addWidget(self.temp_check)
        temp_enable_layout.addStretch()
        temp_layout.addLayout(temp_enable_layout)
        
        temp_topic_layout = QtWidgets.QHBoxLayout()
        temp_topic_layout.addWidget(QtWidgets.QLabel("Topic:"), 0)
        self.temp_topic = QtWidgets.QLabel("pr/home/room1/temperature")
        self.temp_topic.setStyleSheet("color: #0f9f9a; font-size: 12px;")
        temp_topic_layout.addWidget(self.temp_topic, 1)
        temp_layout.addLayout(temp_topic_layout)
        
        temp_base_layout = QtWidgets.QHBoxLayout()
        temp_base_layout.addWidget(QtWidgets.QLabel("Base Value (°C):"), 0)
        self.temp_base = QtWidgets.QDoubleSpinBox()
        self.temp_base.setRange(-50, 50)
        self.temp_base.setValue(22)
        self.temp_base.setDecimals(1)
        temp_base_layout.addWidget(self.temp_base, 0)
        self.temp_value = QtWidgets.QLabel("-- °C")
        self.temp_value.setStyleSheet("color: #0f9f9a; font-weight: bold; font-size: 12px;")
        temp_base_layout.addWidget(QtWidgets.QLabel("Current:"), 0)
        temp_base_layout.addWidget(self.temp_value, 0)
        temp_base_layout.addStretch()
        temp_layout.addLayout(temp_base_layout)
        
        temp_group.setLayout(temp_layout)
        layout.addWidget(temp_group)
        
        # Humidity Section
        hum_group = QtWidgets.QGroupBox("Humidity Sensor")
        hum_layout = QtWidgets.QVBoxLayout()
        
        hum_enable_layout = QtWidgets.QHBoxLayout()
        self.hum_check = QtWidgets.QCheckBox("Enable Humidity")
        self.hum_check.setChecked(True)
        hum_enable_layout.addWidget(self.hum_check)
        hum_enable_layout.addStretch()
        hum_layout.addLayout(hum_enable_layout)
        
        hum_topic_layout = QtWidgets.QHBoxLayout()
        hum_topic_layout.addWidget(QtWidgets.QLabel("Topic:"), 0)
        self.hum_topic = QtWidgets.QLabel("pr/home/room1/humidity")
        self.hum_topic.setStyleSheet("color: #0f9f9a; font-size: 12px;")
        hum_topic_layout.addWidget(self.hum_topic, 1)
        hum_layout.addLayout(hum_topic_layout)
        
        hum_base_layout = QtWidgets.QHBoxLayout()
        hum_base_layout.addWidget(QtWidgets.QLabel("Base Value (%):"), 0)
        self.hum_base = QtWidgets.QDoubleSpinBox()
        self.hum_base.setRange(0, 100)
        self.hum_base.setValue(50)
        self.hum_base.setDecimals(1)
        hum_base_layout.addWidget(self.hum_base, 0)
        self.hum_value = QtWidgets.QLabel("-- %")
        self.hum_value.setStyleSheet("color: #0f9f9a; font-weight: bold; font-size: 12px;")
        hum_base_layout.addWidget(QtWidgets.QLabel("Current:"), 0)
        hum_base_layout.addWidget(self.hum_value, 0)
        hum_base_layout.addStretch()
        hum_layout.addLayout(hum_base_layout)
        
        hum_group.setLayout(hum_layout)
        layout.addWidget(hum_group)
        
        # Light Section
        lux_group = QtWidgets.QGroupBox("Light Sensor (Lux)")
        lux_layout = QtWidgets.QVBoxLayout()
        
        lux_enable_layout = QtWidgets.QHBoxLayout()
        self.lux_check = QtWidgets.QCheckBox("Enable Light")
        self.lux_check.setChecked(True)
        lux_enable_layout.addWidget(self.lux_check)
        lux_enable_layout.addStretch()
        lux_layout.addLayout(lux_enable_layout)
        
        lux_topic_layout = QtWidgets.QHBoxLayout()
        lux_topic_layout.addWidget(QtWidgets.QLabel("Topic:"), 0)
        self.lux_topic = QtWidgets.QLabel("pr/home/room1/light")
        self.lux_topic.setStyleSheet("color: #0f9f9a; font-size: 12px;")
        lux_topic_layout.addWidget(self.lux_topic, 1)
        lux_layout.addLayout(lux_topic_layout)
        
        lux_base_layout = QtWidgets.QHBoxLayout()
        lux_base_layout.addWidget(QtWidgets.QLabel("Base Value (lux):"), 0)
        self.lux_base = QtWidgets.QDoubleSpinBox()
        self.lux_base.setRange(0, 10000)
        self.lux_base.setValue(800)
        self.lux_base.setDecimals(0)
        lux_base_layout.addWidget(self.lux_base, 0)
        self.lux_value = QtWidgets.QLabel("-- lux")
        self.lux_value.setStyleSheet("color: #0f9f9a; font-weight: bold; font-size: 12px;")
        lux_base_layout.addWidget(QtWidgets.QLabel("Current:"), 0)
        lux_base_layout.addWidget(self.lux_value, 0)
        lux_base_layout.addStretch()
        lux_layout.addLayout(lux_base_layout)
        
        lux_group.setLayout(lux_layout)
        layout.addWidget(lux_group)
        
        # Control buttons
        controls = QtWidgets.QHBoxLayout()
        
        self.btn_connect = QtWidgets.QPushButton('Connect')
        self.btn_connect.setFixedWidth(120)
        self.btn_connect.clicked.connect(self.toggle_mqtt)
        controls.addWidget(self.btn_connect)
        
        self.btn_publish = QtWidgets.QPushButton('Start Publishing')
        self.btn_publish.setFixedWidth(140)
        self.btn_publish.setEnabled(False)
        self.btn_publish.clicked.connect(self.toggle_publishing)
        controls.addWidget(self.btn_publish)
        
        self.status_label = QtWidgets.QLabel('🔴 Disconnected')
        self.status_label.setStyleSheet('color: #ff6b6b; font-weight: bold;')
        controls.addWidget(self.status_label, 1)
        
        layout.addLayout(controls)
        
        # Log
        log_group = QtWidgets.QGroupBox("Log")
        log_layout = QtWidgets.QVBoxLayout()
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(120)
        log_layout.addWidget(self.log)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # Initialize topics based on default room
        self.update_topics()
    
    def update_topics(self):
        """Update topic labels based on selected room"""
        room_name = self.room_combo.currentText()
        room_data = room_config.ROOMS.get(room_name)
        
        if room_data:
            self.temp_topic.setText(room_data["sensors"]["temperature"])
            self.hum_topic.setText(room_data["sensors"]["humidity"])
            self.lux_topic.setText(room_data["sensors"]["light"])
    
    def append_log(self, text):
        ts = time.strftime('%H:%M:%S')
        self.log.append(f'[{ts}] {text}')
    
    def toggle_mqtt(self):
        if not self.is_connected:
            self.connect_mqtt()
        else:
            self.disconnect_mqtt()
    
    def connect_mqtt(self):
        try:
            client_id = f"sensor_{random.randint(10000, 99999)}"
            self.client = mqtt.Client(client_id, clean_session=True)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            
            if username != "":
                self.client.username_pw_set(username, password)
            
            self.client.connect(broker_ip, int(port))
            self.client.loop_start()
            self.append_log('🔄 Connecting to MQTT broker...')
        except Exception as e:
            self.append_log(f'✗ Connection failed: {e}')
    
    def disconnect_mqtt(self):
        if self.client:
            try:
                self.is_publishing = False
                if self.publish_thread and self.publish_thread.is_alive():
                    self.publish_thread.join(timeout=2)
                
                self.client.loop_stop()
                self.client.disconnect()
                self.is_connected = False
                self.btn_connect.setText('Connect')
                self.btn_publish.setEnabled(False)
                self.btn_publish.setText('Start Publishing')
                self.status_label.setText('🔴 Disconnected')
                self.status_label.setStyleSheet('color: #ff6b6b; font-weight: bold;')
                self.append_log('✓ Disconnected')
            except Exception as e:
                self.append_log(f'✗ Error: {e}')
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True
            self.btn_connect.setText('Disconnect')
            self.btn_publish.setEnabled(True)
            self.status_label.setText('🟢 Connected')
            self.status_label.setStyleSheet('color: #0f9f9a; font-weight: bold;')
            self.append_log('✓ Connected to MQTT broker')
        else:
            self.append_log(f'✗ Connection failed: code {rc}')
    
    def _on_disconnect(self, client, userdata, flags, rc=0):
        if rc != 0:
            self.append_log(f'✗ Disconnected: code {rc}')
    
    def toggle_publishing(self):
        if not self.is_publishing:
            self.start_publishing()
        else:
            self.stop_publishing()
    
    def start_publishing(self):
        self.is_publishing = True
        self.btn_publish.setText('Stop Publishing')
        self.sensor_data.base_temp = self.temp_base.value()
        self.sensor_data.base_humidity = self.hum_base.value()
        self.sensor_data.base_lux = self.lux_base.value()
        self.append_log('▶ Started publishing...')
        
        self.publish_thread = threading.Thread(target=self._publish_loop, daemon=True)
        self.publish_thread.start()
    
    def stop_publishing(self):
        self.is_publishing = False
        self.btn_publish.setText('Start Publishing')
        self.append_log('⏹ Stopped publishing')
    
    def _publish_loop(self):
        while self.is_publishing and self.is_connected:
            try:
                # Temperature
                if self.temp_check.isChecked() and self.temp_topic.text().strip():
                    value = self.sensor_data.get_temperature()
                    self.sensor_data.base_temp = self.temp_base.value()
                    payload = json.dumps({"temperature": value})
                    self.client.publish(self.temp_topic.text(), payload)
                    self.temp_value.setText(f"{value} °C")
                
                # Humidity
                if self.hum_check.isChecked() and self.hum_topic.text().strip():
                    value = self.sensor_data.get_humidity()
                    self.sensor_data.base_humidity = self.hum_base.value()
                    payload = json.dumps({"humidity": value})
                    self.client.publish(self.hum_topic.text(), payload)
                    self.hum_value.setText(f"{value} %")
                
                # Light
                if self.lux_check.isChecked() and self.lux_topic.text().strip():
                    value = self.sensor_data.get_light()
                    self.sensor_data.base_lux = self.lux_base.value()
                    payload = json.dumps({"lux": value})
                    self.client.publish(self.lux_topic.text(), payload)
                    self.lux_value.setText(f"{value} lux")
                
            except Exception as e:
                self.append_log(f'✗ Publish error: {e}')
            
            time.sleep(5)


def main():
    app = QtWidgets.QApplication([])
    win = SingleSensorGUI()
    win.show()
    app.exec_()


if __name__ == '__main__':
    main()
