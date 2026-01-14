import os
import sys
import PyQt5
import random
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import paho.mqtt.client as mqtt
import time
import datetime
from mqtt_init import *

# Global settings
global clientname, CONNECTED, hum_current
CONNECTED = False
r = random.randrange(1, 10000000)
clientname = "IOT_humidity_client-" + str(r)
DHT_topic = 'pr/home/5976397/sts'
update_rate = 5000  # 5 seconds
hum_current = 50.0  # Starting humidity percentage

class Mqtt_client():
    def __init__(self):
        self.broker = ''
        self.port = 1883
        self.clientname = clientname
        self.username = ''
        self.password = ''        
        self.on_connected_to_form = None
        
    def set_on_connected_to_form(self, on_connected_to_form):
        self.on_connected_to_form = on_connected_to_form
    def set_broker(self, value): self.broker = value         
    def set_port(self, value): self.port = value     
    def set_clientName(self, value): self.clientname = value        
    def set_username(self, value): self.username = value     
    def set_password(self, value): self.password = value         

    def on_connect(self, client, userdata, flags, rc):
        global CONNECTED
        if rc == 0:
            print("Connected OK")
            CONNECTED = True
            if self.on_connected_to_form:
                self.on_connected_to_form()            
        else:
            print("Bad connection Returned code=", rc)
            
    def on_disconnect(self, client, userdata, flags, rc=0):
        global CONNECTED
        CONNECTED = False
        print("Disconnected result code " + str(rc))
            
    def connect_to(self):
        self.client = mqtt.Client(self.clientname, clean_session=True)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.username_pw_set(self.username, self.password)        
        print("Connecting to broker ", self.broker)        
        self.client.connect(self.broker, self.port)    
    
    def start_listening(self):        
        self.client.loop_start()        
    
    def publish_to(self, topic, message):
        if CONNECTED:
            self.client.publish(topic, message)

class ConnectionDock(QDockWidget):
    def __init__(self, mc):
        QDockWidget.__init__(self)
        self.mc = mc
        self.mc.set_on_connected_to_form(self.on_connected)
        
        self.eHostInput = QLineEdit()
        self.eHostInput.setText(broker_ip)
        
        self.ePort = QLineEdit()
        self.ePort.setText(str(broker_port))
        
        self.eConnectbtn = QPushButton("Connect Humidity Sensor")
        self.eConnectbtn.clicked.connect(self.on_button_connect_click)
        self.eConnectbtn.setStyleSheet("background-color: gray; color: white;")
        
        self.ePublisherTopic = QLineEdit()
        self.ePublisherTopic.setText(DHT_topic)

        # Humidity Display
        self.Humidity = QLineEdit()
        self.Humidity.setReadOnly(True) 
        self.Humidity.setText('---')

        formLayout = QFormLayout()       
        formLayout.addRow("MQTT Control", self.eConnectbtn)
        formLayout.addRow("Topic", self.ePublisherTopic)
        formLayout.addRow("Humidity (%)", self.Humidity)

        widget = QWidget(self)
        widget.setLayout(formLayout)
        self.setWidget(widget)     
        self.setWindowTitle("Humidity Sensor") 
        
    def on_connected(self):
        self.eConnectbtn.setStyleSheet("background-color: blue; color: white;")
        self.eConnectbtn.setText("Streaming Humidity...")
                    
    def on_button_connect_click(self):
        self.mc.set_broker(self.eHostInput.text())
        self.mc.set_port(int(self.ePort.text()))
        self.mc.set_username(username)
        self.mc.set_password(password)
        self.mc.connect_to()        
        self.mc.start_listening()

class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.mc = Mqtt_client()
        
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(update_rate) 

        self.setGeometry(100, 100, 350, 200)
        self.setWindowTitle('IoT Humidity Simulator')        

        self.connectionDock = ConnectionDock(self.mc)        
        self.addDockWidget(Qt.TopDockWidgetArea, self.connectionDock)        

    def update_data(self):
        global hum_current
        
        # Simulate humidity change: +/- 2% change
        variation = random.uniform(-2.0, 2.0)
        hum_current += variation
        
        # Keep humidity within realistic bounds (30% to 90%)
        if hum_current < 30: hum_current = 30.0
        if hum_current > 90: hum_current = 90.0
        
        display_val = "{:.1f}".format(hum_current)
        print(f'Humidity Update: {display_val}%')
        
        self.connectionDock.Humidity.setText(display_val + " %")
        self.mc.publish_to(DHT_topic, f'{{"humidity": {display_val}}}')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainwin = MainWindow()
    mainwin.show()
    sys.exit(app.exec_())