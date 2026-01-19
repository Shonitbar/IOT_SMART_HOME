import sys
import json
import sqlite3
from datetime import datetime

import paho.mqtt.client as mqtt
from PyQt5 import QtWidgets, QtCore


try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    HAS_MPL = True
except Exception:
    HAS_MPL = False

import mqtt_init
from mqtt_init import client_init, send_msg
import room_config


class MqttMessageEvent(QtCore.QObject):
    message_received = QtCore.pyqtSignal(str, str)


class DataManagerApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Vessel Application')
        self.resize(1200, 700)

        
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
        QTabBar::tab { background: #0f1b22; color: #9fbfc0; padding: 8px 20px; }
        QTabBar::tab:selected { background: #0f9f9a; color: #000000; }
        """
        self.setStyleSheet(STYLE)

        
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)

        
        navbar = QtWidgets.QHBoxLayout()
        navbar.addStretch()
        title = QtWidgets.QLabel('Vessel')
        title.setStyleSheet('font-size:20px; font-weight:800; color: #e6fff9;')
        title.setAlignment(QtCore.Qt.AlignCenter)
        navbar.addWidget(title)
        navbar.addStretch()
        layout.addLayout(navbar)

        # Room tabs
        self.room_tabs = QtWidgets.QTabWidget()
        self.room_tabs.currentChanged.connect(self.on_room_changed)
        
        # Dictionary to store room UI elements
        self.room_cards = {}
        self.room_latest = {}
        
        # Create tab for each room
        for room_name in room_config.get_room_names():
            self.room_latest[room_name] = {'temperature': None, 'humidity': None, 'lux': None}
            
            # Create card container for this room
            center_card = QtWidgets.QFrame()
            center_card.setObjectName('card')
            center_card.setMinimumHeight(220)
            center_card_layout = QtWidgets.QVBoxLayout(center_card)
            center_card_layout.setContentsMargins(28, 24, 28, 24)
            center_card_layout.setSpacing(20)

            # Metrics row (centered)
            metrics_row = QtWidgets.QHBoxLayout()
            metrics_row.setSpacing(18)
            metrics_row.setAlignment(QtCore.Qt.AlignCenter)

            def make_metric(name):
                f = QtWidgets.QFrame()
                f.setObjectName('card')
                v = QtWidgets.QVBoxLayout(f)
                v.setAlignment(QtCore.Qt.AlignCenter)
                lbl_val = QtWidgets.QLabel('--')
                lbl_val.setObjectName('metricValue')
                lbl_val.setAlignment(QtCore.Qt.AlignCenter)
                lbl_name = QtWidgets.QLabel(name)
                lbl_name.setObjectName('metricLabel')
                lbl_name.setAlignment(QtCore.Qt.AlignCenter)
                v.addWidget(lbl_val)
                v.addWidget(lbl_name)
                return f, lbl_val

            temp_card, temp_val = make_metric('Temperature (°C)')
            hum_card, hum_val = make_metric('Humidity (%)')
            lux_card, lux_val = make_metric('Light (lux)')

            temp_card.setFixedSize(240, 140)
            hum_card.setFixedSize(240, 140)
            lux_card.setFixedSize(240, 140)

            metrics_row.addWidget(temp_card)
            metrics_row.addWidget(hum_card)
            metrics_row.addWidget(lux_card)

            center_card_layout.addLayout(metrics_row)
            
            # Store references for this room
            self.room_cards[room_name] = {
                'frame': center_card,
                'temp_val': temp_val,
                'hum_val': hum_val,
                'lux_val': lux_val
            }
            
            self.room_tabs.addTab(center_card, room_name)

        layout.addWidget(self.room_tabs)

        # Store reference to current room for threshold controls
        self.current_room = room_config.get_room_names()[0]

        # Threshold controls (centered)
        thr_layout = QtWidgets.QHBoxLayout()
        thr_layout.setAlignment(QtCore.Qt.AlignCenter)
        thr_layout.setSpacing(16)

        lbl_t = QtWidgets.QLabel('Temp THR:')
        lbl_t.setAlignment(QtCore.Qt.AlignCenter)
        self.temp_thr = QtWidgets.QDoubleSpinBox()
        self.temp_thr.setRange(-1000, 1000)
        self.temp_thr.setValue(50.0)

        lbl_h = QtWidgets.QLabel('Hum THR:')
        lbl_h.setAlignment(QtCore.Qt.AlignCenter)
        self.hum_thr = QtWidgets.QDoubleSpinBox()
        self.hum_thr.setRange(0, 100)
        self.hum_thr.setValue(80.0)

        lbl_l = QtWidgets.QLabel('Lux THR:')
        lbl_l.setAlignment(QtCore.Qt.AlignCenter)
        self.lux_thr = QtWidgets.QDoubleSpinBox()
        self.lux_thr.setRange(0, 100000)
        self.lux_thr.setValue(1000.0)

        thr_layout.addWidget(lbl_t)
        thr_layout.addWidget(self.temp_thr)
        thr_layout.addWidget(lbl_h)
        thr_layout.addWidget(self.hum_thr)
        thr_layout.addWidget(lbl_l)
        thr_layout.addWidget(self.lux_thr)

        layout.addLayout(thr_layout)

        # Action controls below card
        actions = QtWidgets.QHBoxLayout()
        actions.setAlignment(QtCore.Qt.AlignCenter)
        self.btn_connect = QtWidgets.QPushButton('Connect')
        self.btn_connect.setFixedWidth(140)
        self.btn_connect.clicked.connect(self.toggle_connect)
        self.btn_history = QtWidgets.QPushButton('History')
        self.btn_history.setFixedWidth(120)
        self.btn_history.clicked.connect(self.open_history)
        self.btn_toggle_log = QtWidgets.QPushButton('Hide Console')
        self.btn_toggle_log.setCheckable(True)
        self.btn_toggle_log.setChecked(True)
        self.btn_toggle_log.setObjectName('secondary')
        self.btn_toggle_log.clicked.connect(self.toggle_console)

        actions.addWidget(self.btn_connect)
        actions.addWidget(self.btn_history)
        actions.addWidget(self.btn_toggle_log)
        layout.addLayout(actions)

        # Collapsible log area (starts visible)
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(220)
        self.log.setVisible(True)
        layout.addWidget(self.log)

        # Status footer (centered)
        self.lbl_status = QtWidgets.QLabel('Disconnected')
        self.lbl_status.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_status.setStyleSheet('color: #9fbfc0;')
        layout.addWidget(self.lbl_status)

        # DB init
        self.db_path = 'sensor_data.db'
        self._ensure_db()

        # MQTT
        self.client = None
        self.mqtt_events = MqttMessageEvent()
        self.mqtt_events.message_received.connect(self.on_message_gui)

        # keep track if connected
        self._connected = False

        # Timer to refresh metric cards
        self._display_timer = QtCore.QTimer(self)
        self._display_timer.timeout.connect(self.update_display)
        self._display_timer.start(1000)
        

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

    def on_room_changed(self, index):
        """Handle room tab change"""
        room_names = room_config.get_room_names()
        if 0 <= index < len(room_names):
            self.current_room = room_names[index]
            self.update_display()

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
            # Determine which room this message belongs to
            room_name = room_config.get_room_from_topic(topic)
            sensor_type = room_config.get_sensor_type_from_topic(topic)
            self.append_log(f'DEBUG: Topic {topic} mapped to room: {room_name}, sensor: {sensor_type}')
            
            if room_name:
                # cache latest numeric readings for this room
                # Try multiple possible key names for robustness
                try:
                    if sensor_type == 'temperature' or 'temperature' in data:
                        val = data.get('temperature') or data.get('temp') or data.get('Temp') or data.get('TEMP')
                        if val is not None:
                            self.room_latest[room_name]['temperature'] = float(val)
                except Exception as e:
                    self.append_log(f'DEBUG: Failed to parse temperature: {e}')
                
                try:
                    if sensor_type == 'humidity' or 'humidity' in data:
                        # Handle various humidity formats
                        val = data.get('humidity')
                        if val is None:
                            val = data.get('Humidity (%)')
                        if val is None:
                            val = data.get('humidity_%')
                        if val is None:
                            val = data.get('hum')
                        
                        if val is not None:
                            # Remove % sign if present
                            if isinstance(val, str):
                                val = val.replace('%', '').strip()
                            self.room_latest[room_name]['humidity'] = float(val)
                            self.append_log(f'DEBUG: Updated {room_name} humidity to {self.room_latest[room_name]["humidity"]}')
                except Exception as e:
                    self.append_log(f'DEBUG: Failed to parse humidity: {e}')
                
                try:
                    if sensor_type == 'light' or sensor_type == 'lux' or 'lux' in data:
                        val = data.get('lux') or data.get('light') or data.get('Light') or data.get('lux')
                        if val is not None:
                            self.room_latest[room_name]['lux'] = float(val)
                except Exception as e:
                    self.append_log(f'DEBUG: Failed to parse lux: {e}')

            self._process_data(topic, data)

            # immediate UI refresh
            self.update_display()

    def update_display(self):
        # Get the current room's latest data
        room_data = self.room_latest.get(self.current_room, {'temperature': None, 'humidity': None, 'lux': None})
        room_ui = self.room_cards.get(self.current_room, {})
        
        if not room_ui:
            return
        
        # Temperature
        t = room_data.get('temperature')
        temp_label = room_ui.get('temp_val')
        if temp_label:
            if t is None:
                temp_label.setText('--')
                temp_label.setStyleSheet('color: #ffffff')
            else:
                temp_label.setText(f'{t:.1f}°C')
                if t >= float(self.temp_thr.value()):
                    temp_label.setStyleSheet('color: #ff6b6b')
                else:
                    temp_label.setStyleSheet('color: #9ff4ea')

        # Humidity
        h = room_data.get('humidity')
        hum_label = room_ui.get('hum_val')
        if hum_label:
            if h is None:
                hum_label.setText('--')
                hum_label.setStyleSheet('color: #ffffff')
            else:
                hum_label.setText(f'{h:.1f}%')
                if h >= float(self.hum_thr.value()):
                    hum_label.setStyleSheet('color: #ff6b6b')
                else:
                    hum_label.setStyleSheet('color: #9ff4ea')

        # Lux
        l = room_data.get('lux')
        lux_label = room_ui.get('lux_val')
        if lux_label:
            if l is None:
                lux_label.setText('--')
                lux_label.setStyleSheet('color: #ffffff')
            else:
                lux_label.setText(f'{l:.0f}')
                if l >= float(self.lux_thr.value()):
                    lux_label.setStyleSheet('color: #ff6b6b')
                else:
                    lux_label.setStyleSheet('color: #9ff4ea')

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

    def open_history(self):
        dlg = HistoryDialog(self, self.db_path)
        dlg.exec_()


class HistoryDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, db_path='sensor_data.db'):
        super().__init__(parent)
        self.setWindowTitle('Message History & Statistics')
        self.resize(900, 600)
        self.db_path = db_path

        # Main layout: controls on top, table left, chart+stats right
        layout = QtWidgets.QVBoxLayout(self)

        # Top controls: metric selector, limit, refresh
        controls = QtWidgets.QHBoxLayout()
        controls.setAlignment(QtCore.Qt.AlignLeft)
        controls.addWidget(QtWidgets.QLabel('Metric:'))
        self.metric_combo = QtWidgets.QComboBox()
        self.metric_combo.addItems(['temperature', 'humidity', 'lux'])
        controls.addWidget(self.metric_combo)

        controls.addWidget(QtWidgets.QLabel('Rows:'))
        self.limit_spin = QtWidgets.QSpinBox()
        self.limit_spin.setRange(10, 5000)
        self.limit_spin.setValue(500)
        controls.addWidget(self.limit_spin)

        self.btn_refresh = QtWidgets.QPushButton('Refresh')
        self.btn_refresh.clicked.connect(self.load_data)
        controls.addWidget(self.btn_refresh)

        controls.addStretch()
        layout.addLayout(controls)

        # content split: table | chart+stats
        content = QtWidgets.QHBoxLayout()

        # Table for messages (left)
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(['id', 'ts', 'topic', 'temperature', 'humidity', 'lux', 'payload'])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(6, QtWidgets.QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        # make text visible on dark background
        # Dark-blue theme with white text for better contrast
        self.table.setStyleSheet(
            "QTableWidget { background: #071d3a; color: #ffffff; gridline-color: #08314d; alternate-background-color: #0b2a46; }"
            "QHeaderView::section { background: #07253f; color: #ffffff; padding:6px; border: none; }"
            "QTableWidget::item:selected { background: #0f9f9a; color: #001017; }"
        )
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.itemSelectionChanged.connect(self.on_table_select)

        content.addWidget(self.table, 2)

        # Right panel: chart + summary
        right_panel = QtWidgets.QVBoxLayout()

        # Chart area
        if HAS_MPL:
            self.fig = Figure(figsize=(4, 3))
            self.canvas = FigureCanvas(self.fig)
            right_panel.addWidget(self.canvas, 3)
        else:
            self.canvas = None
            self.no_chart_label = QtWidgets.QLabel('matplotlib not installed — install matplotlib to see charts')
            self.no_chart_label.setWordWrap(True)
            right_panel.addWidget(self.no_chart_label, 1)

        # Summary area
        self.summary_label = QtWidgets.QLabel('Loading statistics...')
        self.summary_label.setWordWrap(True)
        right_panel.addWidget(self.summary_label, 1)

        content.addLayout(right_panel, 1)
        layout.addLayout(content, 1)

        # Bottom controls: export, close
        btns = QtWidgets.QHBoxLayout()
        btns.addStretch()
        self.btn_export = QtWidgets.QPushButton('Export CSV')
        self.btn_export.clicked.connect(self.export_csv)
        btns.addWidget(self.btn_export)

        self.btn_close = QtWidgets.QPushButton('Close')
        self.btn_close.clicked.connect(self.accept)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)

        # load initial data
        self.load_data()

    def load_data(self):
        conn = sqlite3.connect(self.db_path)
        try:
            c = conn.cursor()
            limit = int(self.limit_spin.value()) if hasattr(self, 'limit_spin') else 500
            c.execute('SELECT id, ts, topic, payload FROM messages ORDER BY id DESC LIMIT ?', (limit,))
            rows = c.fetchall()
        finally:
            conn.close()

        # populate table
        self.table.setRowCount(len(rows))

        temps = []
        hums = []
        luxes = []

        for rindex, row in enumerate(rows):
            _id, ts, topic, payload = row
            # parse payload
            temp = hum = lux = ''
            try:
                data = json.loads(payload)
                if isinstance(data, dict):
                    if 'temperature' in data:
                        temp = str(data.get('temperature'))
                        try:
                            temps.append(float(data.get('temperature')))
                        except Exception:
                            pass
                    if 'humidity' in data:
                        hum = str(data.get('humidity'))
                        try:
                            hums.append(float(data.get('humidity')))
                        except Exception:
                            pass
                    if 'lux' in data:
                        lux = str(data.get('lux'))
                        try:
                            luxes.append(float(data.get('lux')))
                        except Exception:
                            pass
            except Exception:
                pass

            cells = [str(_id), ts, topic, temp, hum, lux, payload]
            for cidx, val in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(val)
                item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable)
                item.setForeground(QtCore.Qt.white)
                self.table.setItem(rindex, cidx, item)

        # compute stats
        def stats(arr):
            if not arr:
                return 'n/a'
            return f'count={len(arr)} min={min(arr):.2f} max={max(arr):.2f} avg={sum(arr)/len(arr):.2f}'

        summary = f"Temperature: {stats(temps)}\nHumidity: {stats(hums)}\nLight (lux): {stats(luxes)}\nRows shown: {len(rows)}"
        self.summary_label.setText(summary)

        # update chart
        if HAS_MPL:
            self.plot_metric()

    def export_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export CSV', 'history.csv', 'CSV Files (*.csv)')
        if not path:
            return

        # read current table and write
        with open(path, 'w', encoding='utf-8') as f:
            # header
            headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
            f.write(','.join(headers) + '\n')
            for r in range(self.table.rowCount()):
                vals = []
                for c in range(self.table.columnCount()):
                    item = self.table.item(r, c)
                    vals.append('"' + (item.text().replace('"', '""') if item else '') + '"')
                f.write(','.join(vals) + '\n')
        QtWidgets.QMessageBox.information(self, 'Export', f'Exported {self.table.rowCount()} rows to {path}')

    def on_table_select(self):
        # when a row is selected, update chart to show topic-specific series
        if not HAS_MPL:
            return
        self.plot_metric()

    def plot_metric(self):
        metric = self.metric_combo.currentText()
        # fetch recent metric values for plotting
        conn = sqlite3.connect(self.db_path)
        try:
            c = conn.cursor()
            c.execute('SELECT ts, payload FROM messages ORDER BY id DESC LIMIT ?', (int(self.limit_spin.value()),))
            rows = c.fetchall()
        finally:
            conn.close()

        times = []
        vals = []
        # rows are newest first -> reverse for time order
        for ts, payload in reversed(rows):
            try:
                data = json.loads(payload)
                if isinstance(data, dict) and metric in data:
                    v = float(data.get(metric))
                    vals.append(v)
                    # try parse ts as ISO
                    try:
                        times.append(datetime.fromisoformat(ts))
                    except Exception:
                        times.append(ts)
            except Exception:
                pass

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        if vals:
            ax.plot(vals, '-o', color='#0f9f9a')
            ax.set_title(f'{metric} (last {len(vals)} samples)')
            ax.grid(True, color='#122027')
        else:
            ax.text(0.5, 0.5, 'No data for metric', ha='center', va='center', color='white')
        self.canvas.draw()


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = DataManagerApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
