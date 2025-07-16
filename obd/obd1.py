import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import obd
import serial
import serial.tools.list_ports
import threading
import time
import json
import datetime
import csv
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from typing import Dict, List, Optional
import logging
import os

# For Windows audio alerts
try:
    import winsound
except ImportError:
    winsound = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedOBDMonitor:
    def __init__(self):
        # Load configuration first
        self.config = self.create_default_config()
        self.load_config()

        # Set appearance
        ctk.set_appearance_mode(self.config['appearance']['mode'])
        ctk.set_default_color_theme(self.config['appearance']['theme'])

        self.root = ctk.CTk()
        self.root.title("OBD Monitor Pro - Enhanced")
        self.root.geometry("1600x1000")
        self.root.minsize(1400, 900)

        # OBD connection
        self.connection = None
        self.is_connected = False
        self.monitoring = False
        self.monitor_thread = None

        # Data storage
        self.pid_data = {}
        self.dtc_data = []
        self.log_data = []
        self.historical_data = {}

        # Available PIDs
        self.available_pids = []

        # Alerts
        self.active_alerts = []

        # Session tracking
        self.session_start_time = datetime.datetime.now()

        # Setup UI components
        self.setup_ui()
        self.create_log_directory()

        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_default_config(self):
        """Create default configuration"""
        return {
            'appearance': {
                'mode': 'dark',
                'theme': 'blue'
            },
            'connection': {
                'port': 'COM3',
                'baudrate': 38400,
                'timeout': 10
            },
            'monitoring': {
                'update_interval': 1,
                'max_log_entries': 1000,
                'log_directory': 'logs'
            },
            'alerts': {
                'audio_enabled': True,
                'visual_enabled': True,
                'thresholds': {}
            },
            'window': {
                'geometry': '1200x800',
                'state': 'normal'
            }
        }

    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r') as f:
                    loaded_config = json.load(f)
                # Merge with default config
                self.config.update(loaded_config)
                logger.info("Configuration loaded")
            else:
                logger.info("No configuration file found, using defaults")
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")

    def save_config_to_file(self):
        """Save current configuration"""
        try:
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")

    def create_log_directory(self):
        """Create logs directory if it doesn't exist"""
        log_dir = self.config.get('monitoring', {}).get(
            'log_directory', 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def setup_ui(self):
        """Setup the enhanced UI components"""
        # Main container
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Top control panel
        self.setup_enhanced_control_panel(main_frame)

        # Main content area with tabs
        self.setup_enhanced_tabbed_interface(main_frame)

        # Status bar with additional info
        self.setup_enhanced_status_bar(main_frame)

    def setup_enhanced_status_bar(self, parent):
        """Setup enhanced status bar at the bottom"""
        status_frame = ctk.CTkFrame(parent)
        status_frame.pack(fill="x", side="bottom", padx=5, pady=5)

        self.status_label = ctk.CTkLabel(
            status_frame, text="Ready", anchor="w")
        self.status_label.pack(side="left", padx=10)

        self.connection_status = ctk.CTkLabel(
            status_frame, text="Disconnected", text_color="red")
        self.connection_status.pack(side="right", padx=10)

        self.session_label = ctk.CTkLabel(
            status_frame, text="Session: 00:00:00")
        self.session_label.pack(side="right", padx=10)

        self.root.after(1000, self.update_session_timer)

    def setup_enhanced_control_panel(self, parent):
        """Setup enhanced connection and control panel"""
        control_frame = ctk.CTkFrame(parent)
        control_frame.pack(fill="x", padx=5, pady=5)

        # Connection section
        conn_frame = ctk.CTkFrame(control_frame)
        conn_frame.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        ctk.CTkLabel(conn_frame, text="Connection", font=ctk.CTkFont(
            size=16, weight="bold")).pack(pady=5)

        # Port and baudrate selection
        settings_frame = ctk.CTkFrame(conn_frame)
        settings_frame.pack(fill="x", padx=5, pady=2)

        # Port selection
        ctk.CTkLabel(settings_frame, text="Port:").grid(
            row=0, column=0, padx=5, sticky="w")
        self.port_var = tk.StringVar(value=self.config.get(
            'connection', {}).get('port', 'COM3'))
        self.port_combo = ctk.CTkComboBox(
            settings_frame, variable=self.port_var, width=150)
        self.port_combo.grid(row=0, column=1, padx=5)

        # Baudrate selection
        ctk.CTkLabel(settings_frame, text="Baudrate:").grid(
            row=0, column=2, padx=5, sticky="w")
        self.baudrate_var = tk.StringVar(value="38400")
        baudrate_combo = ctk.CTkComboBox(settings_frame, variable=self.baudrate_var,
                                         values=["9600", "38400", "115200"], width=100)
        baudrate_combo.grid(row=0, column=3, padx=5)

        refresh_btn = ctk.CTkButton(
            settings_frame, text="Refresh", command=self.refresh_ports, width=80)
        refresh_btn.grid(row=0, column=4, padx=5)

        # Connection buttons
        btn_frame = ctk.CTkFrame(conn_frame)
        btn_frame.pack(fill="x", padx=5, pady=2)

        self.connect_btn = ctk.CTkButton(
            btn_frame, text="Connect", command=self.connect_obd, width=100)
        self.connect_btn.pack(side="left", padx=5)

        self.disconnect_btn = ctk.CTkButton(
            btn_frame, text="Disconnect", command=self.disconnect_obd, width=100, state="disabled")
        self.disconnect_btn.pack(side="left", padx=5)

        # Auto-connect checkbox
        self.auto_connect_var = tk.BooleanVar()
        auto_connect_cb = ctk.CTkCheckBox(
            btn_frame, text="Auto-connect", variable=self.auto_connect_var)
        auto_connect_cb.pack(side="left", padx=10)

        # Monitoring controls
        monitor_frame = ctk.CTkFrame(control_frame)
        monitor_frame.pack(side="right", padx=5, pady=5)

        ctk.CTkLabel(monitor_frame, text="Monitoring",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)

        monitor_btn_frame = ctk.CTkFrame(monitor_frame)
        monitor_btn_frame.pack(fill="x", padx=5, pady=2)

        self.start_btn = ctk.CTkButton(
            monitor_btn_frame, text="Start", command=self.start_monitoring, width=80, state="disabled")
        self.start_btn.grid(row=0, column=0, padx=2)

        self.stop_btn = ctk.CTkButton(
            monitor_btn_frame, text="Stop", command=self.stop_monitoring, width=80, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=2)

        self.clear_dtc_btn = ctk.CTkButton(
            monitor_btn_frame, text="Clear DTCs", command=self.clear_dtcs, width=80, state="disabled")
        self.clear_dtc_btn.grid(row=1, column=0, padx=2, pady=2)

        self.export_btn = ctk.CTkButton(
            monitor_btn_frame, text="Export", command=self.export_data, width=80, state="disabled")
        self.export_btn.grid(row=1, column=1, padx=2, pady=2)

        # Update interval
        interval_frame = ctk.CTkFrame(monitor_frame)
        interval_frame.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(interval_frame, text="Update (ms):").pack(
            side="left", padx=5)
        self.interval_var = tk.StringVar(value="500")
        interval_entry = ctk.CTkEntry(
            interval_frame, textvariable=self.interval_var, width=60)
        interval_entry.pack(side="left", padx=5)

        # Initialize ports
        self.refresh_ports()

    def refresh_ports(self):
        """Refresh the list of available serial ports"""
        try:
            ports = [port.device for port in serial.tools.list_ports.comports()]
            self.port_combo.configure(values=ports)

            # Set default port preference
            default_port = self.config.get(
                'connection', {}).get('port', 'COM3')

            if default_port in ports:
                # Use the configured default port if available
                self.port_combo.set(default_port)
            elif 'COM3' in ports:
                # Fallback to COM3 if available
                self.port_combo.set('COM3')
            elif ports:
                # Use first available port as last resort
                self.port_combo.set(ports[0])
            else:
                self.port_combo.set("")
        except Exception as e:
            logger.error(f"Failed to refresh ports: {str(e)}")
            self.port_combo.configure(values=[])
            self.port_combo.set("")

    def connect_obd(self):
        """Connect to the OBD device"""
        try:
            port = self.port_var.get()
            baudrate = int(self.baudrate_var.get())
            timeout = self.config['connection'].get('timeout', 10)
            self.status_label.configure(text="Connecting to OBD...")
            self.root.update()

            self.connection = obd.OBD(
                port, baudrate=baudrate, timeout=timeout, fast=False)
            if self.connection.is_connected():
                self.is_connected = True
                self.update_connection_status(True)
                self.get_available_pids()
                self.status_label.configure(text="Connected to OBD device")
                logger.info("Connected to OBD device")
            else:
                self.is_connected = False
                self.update_connection_status(False)
                self.status_label.configure(
                    text="Failed to connect to OBD device")
                messagebox.showerror("Connection Failed",
                                     "Could not connect to OBD device.")

        except Exception as e:
            self.is_connected = False
            self.update_connection_status(False)
            logger.error(f"Failed to connect to OBD: {str(e)}")
            messagebox.showerror("Connection Error",
                                 f"Failed to connect to OBD: {str(e)}")

    def disconnect_obd(self):
        """Disconnect from the OBD device"""
        try:
            if self.connection:
                self.connection.close()
                self.connection = None
            self.is_connected = False
            self.update_connection_status(False)
            self.status_label.configure(text="Disconnected from OBD device")
            logger.info("Disconnected from OBD device")
        except Exception as e:
            logger.error(f"Failed to disconnect from OBD: {str(e)}")
            messagebox.showerror("Disconnection Error",
                                 f"Failed to disconnect from OBD: {str(e)}")

    def setup_enhanced_tabbed_interface(self, parent):
        """Setup the enhanced tabbed interface"""
        self.notebook = ctk.CTkTabview(parent)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # Dashboard tab
        self.dashboard_tab = self.notebook.add("Dashboard")
        self.setup_enhanced_dashboard_tab()

        # PIDs tab
        self.pids_tab = self.notebook.add("PIDs")
        self.setup_enhanced_pids_tab()

        # Charts tab
        self.charts_tab = self.notebook.add("Charts")
        self.setup_charts_tab()

        # DTCs tab
        self.dtcs_tab = self.notebook.add("DTCs")
        self.setup_enhanced_dtcs_tab()

        # Alerts tab
        self.alerts_tab = self.notebook.add("Alerts")
        self.setup_alerts_tab()

        # Logs tab
        self.logs_tab = self.notebook.add("Logs")
        self.setup_enhanced_logs_tab()

        # Settings tab
        self.settings_tab = self.notebook.add("Settings")
        self.setup_settings_tab()

    def setup_enhanced_dashboard_tab(self):
        """Setup the enhanced digital dashboard"""
        dash_frame = ctk.CTkScrollableFrame(self.dashboard_tab)
        dash_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.dashboard_widgets = {}

        # Alert panel
        alert_frame = ctk.CTkFrame(dash_frame)
        alert_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(alert_frame, text="Active Alerts",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)
        self.alert_display = ctk.CTkTextbox(alert_frame, height=60)
        self.alert_display.pack(fill="x", padx=10, pady=5)

        # Key metrics
        metrics_frame = ctk.CTkFrame(dash_frame)
        metrics_frame.pack(fill="both", expand=True, pady=10)

        self.create_gauge_grid(metrics_frame)

    def create_gauge_grid(self, parent):
        """Create responsive gauge grid"""
        # Row 1: Primary engine metrics
        row1_frame = ctk.CTkFrame(parent)
        row1_frame.pack(fill="x", padx=10, pady=5)

        self.create_enhanced_gauge_widget(
            row1_frame, "RPM", "rpm", 0, 8000, "RPM", 0, 0, "#FF6B6B")
        self.create_enhanced_gauge_widget(
            row1_frame, "Speed", "speed", 0, 200, "km/h", 0, 1, "#4ECDC4")
        self.create_enhanced_gauge_widget(
            row1_frame, "Engine Load", "engine_load", 0, 100, "%", 0, 2, "#45B7D1")

    def create_enhanced_gauge_widget(self, parent, title, key, min_val, max_val, unit, row, col, color):
        """Create an enhanced gauge widget with color coding"""
        gauge_frame = ctk.CTkFrame(parent)
        gauge_frame.grid(row=row, column=col, padx=10, pady=10, sticky="ew")
        parent.grid_columnconfigure(col, weight=1)

        # Title
        title_label = ctk.CTkLabel(
            gauge_frame, text=title, font=ctk.CTkFont(size=14, weight="bold"))
        title_label.pack(pady=5)

        # Value display
        value_label = ctk.CTkLabel(
            gauge_frame, text="--", font=ctk.CTkFont(size=28, weight="bold"))
        value_label.pack(pady=5)

        # Unit label
        unit_label = ctk.CTkLabel(gauge_frame, text=unit,
                                  font=ctk.CTkFont(size=12))
        unit_label.pack()

        # Progress bar
        progress = ctk.CTkProgressBar(
            gauge_frame, width=220, height=20, progress_color=color)
        progress.pack(pady=10)
        progress.set(0)

        # Store references
        self.dashboard_widgets[key] = {
            'value_label': value_label,
            'progress': progress,
            'min_val': min_val,
            'max_val': max_val,
            'unit': unit,
            'color': color,
            'title': title
        }

    def setup_enhanced_pids_tab(self):
        """Setup enhanced PIDs monitoring tab"""
        pids_frame = ctk.CTkFrame(self.pids_tab)
        pids_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Controls frame
        controls_frame = ctk.CTkFrame(pids_frame)
        controls_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(controls_frame, text="PIDs Control", font=ctk.CTkFont(
            size=16, weight="bold")).pack(side="left", padx=10)

        # Filter entry
        ctk.CTkLabel(controls_frame, text="Filter:").pack(side="left", padx=5)
        self.pid_filter_var = tk.StringVar()
        filter_entry = ctk.CTkEntry(
            controls_frame, textvariable=self.pid_filter_var, width=200)
        filter_entry.pack(side="left", padx=5)
        filter_entry.bind('<KeyRelease>', self.filter_pids)

        # Export PIDs button
        export_pids_btn = ctk.CTkButton(
            controls_frame, text="Export PIDs", command=self.export_pids_data, width=100)
        export_pids_btn.pack(side="right", padx=5)

        # PIDs list with enhanced styling
        list_frame = ctk.CTkFrame(pids_frame)
        list_frame.pack(fill="both", expand=True, pady=5)

        # Create enhanced treeview for PIDs
        columns = ("PID", "Name", "Value", "Unit", "Min",
                   "Max", "Last Updated", "Status")
        self.pids_tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", height=20)

        # Configure columns
        column_widths = {"PID": 80, "Name": 200, "Value": 100, "Unit": 80,
                         "Min": 80, "Max": 80, "Last Updated": 150, "Status": 100}

        for col in columns:
            self.pids_tree.heading(col, text=col)
            self.pids_tree.column(col, width=column_widths.get(col, 100))

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.pids_tree.yview)
        h_scrollbar = ttk.Scrollbar(
            list_frame, orient="horizontal", command=self.pids_tree.xview)
        self.pids_tree.configure(
            yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack treeview and scrollbars
        self.pids_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

    def setup_charts_tab(self):
        """Setup real-time charts tab"""
        charts_frame = ctk.CTkFrame(self.charts_tab)
        charts_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Chart controls
        controls_frame = ctk.CTkFrame(charts_frame)
        controls_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(controls_frame, text="Real-time Charts",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=10)

        # PID selection for charting
        ctk.CTkLabel(controls_frame, text="Chart PID:").pack(
            side="left", padx=5)
        self.chart_pid_var = tk.StringVar()
        self.chart_pid_combo = ctk.CTkComboBox(
            controls_frame, variable=self.chart_pid_var, width=200)
        self.chart_pid_combo.pack(side="left", padx=5)

        # Chart controls
        start_chart_btn = ctk.CTkButton(
            controls_frame, text="Start Chart", command=self.start_charting, width=100)
        start_chart_btn.pack(side="left", padx=5)

        stop_chart_btn = ctk.CTkButton(
            controls_frame, text="Stop Chart", command=self.stop_charting, width=100)
        stop_chart_btn.pack(side="left", padx=5)

        # Chart display
        self.chart_frame = ctk.CTkFrame(charts_frame)
        self.chart_frame.pack(fill="both", expand=True, pady=5)

        # Initialize matplotlib chart
        self.setup_matplotlib_chart()

    def setup_matplotlib_chart(self):
        """Setup matplotlib chart for real-time data"""
        self.fig, self.ax = plt.subplots(figsize=(12, 6), facecolor='#2b2b2b')
        self.ax.set_facecolor('#2b2b2b')
        self.ax.tick_params(colors='white')
        self.ax.xaxis.label.set_color('white')
        self.ax.yaxis.label.set_color('white')
        self.ax.title.set_color('white')

        self.canvas = FigureCanvasTkAgg(self.fig, self.chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Initialize empty data
        self.chart_data = {'x': [], 'y': []}
        self.chart_line, = self.ax.plot([], [], 'cyan', linewidth=2)

    def setup_enhanced_dtcs_tab(self):
        """Setup enhanced DTCs tab"""
        dtcs_frame = ctk.CTkFrame(self.dtcs_tab)
        dtcs_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # DTC controls
        controls_frame = ctk.CTkFrame(dtcs_frame)
        controls_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(controls_frame, text="Diagnostic Trouble Codes", font=ctk.CTkFont(
            size=16, weight="bold")).pack(side="left", padx=10)

        refresh_dtc_btn = ctk.CTkButton(
            controls_frame, text="Refresh DTCs", command=self.refresh_dtcs, width=120)
        refresh_dtc_btn.pack(side="right", padx=5)

        export_dtc_btn = ctk.CTkButton(
            controls_frame, text="Export DTCs", command=self.export_dtcs, width=120)
        export_dtc_btn.pack(side="right", padx=5)

        # DTC summary
        summary_frame = ctk.CTkFrame(dtcs_frame)
        summary_frame.pack(fill="x", pady=5)

        self.dtc_count_label = ctk.CTkLabel(
            summary_frame, text="DTCs Found: 0", font=ctk.CTkFont(size=14))
        self.dtc_count_label.pack(side="left", padx=10, pady=5)

        self.dtc_status_label = ctk.CTkLabel(
            summary_frame, text="Status: OK", font=ctk.CTkFont(size=14), text_color="green")
        self.dtc_status_label.pack(side="right", padx=10, pady=5)

        # DTCs display
        self.dtcs_text = ctk.CTkTextbox(
            dtcs_frame, height=400, font=("Consolas", 11))
        self.dtcs_text.pack(fill="both", expand=True, padx=10, pady=10)

    def setup_alerts_tab(self):
        """Setup alerts configuration tab"""
        alerts_frame = ctk.CTkFrame(self.alerts_tab)
        alerts_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(alerts_frame, text="Alert Configuration",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        # Alert settings
        settings_frame = ctk.CTkFrame(alerts_frame)
        settings_frame.pack(fill="x", padx=10, pady=5)

        # Enable/disable alerts
        self.audio_alerts_var = tk.BooleanVar(value=True)
        audio_cb = ctk.CTkCheckBox(
            settings_frame, text="Audio Alerts", variable=self.audio_alerts_var)
        audio_cb.pack(side="left", padx=10)

        self.visual_alerts_var = tk.BooleanVar(value=True)
        visual_cb = ctk.CTkCheckBox(
            settings_frame, text="Visual Alerts", variable=self.visual_alerts_var)
        visual_cb.pack(side="left", padx=10)

        # Alert thresholds
        thresholds_frame = ctk.CTkScrollableFrame(alerts_frame)
        thresholds_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.threshold_widgets = {}
        self.setup_threshold_controls(thresholds_frame)

        # Active alerts display
        active_frame = ctk.CTkFrame(alerts_frame)
        active_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(active_frame, text="Active Alerts",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)
        self.active_alerts_text = ctk.CTkTextbox(active_frame, height=100)
        self.active_alerts_text.pack(fill="x", padx=10, pady=5)

    def setup_threshold_controls(self, parent):
        """Setup threshold control widgets"""
        thresholds = [
            ("RPM", "rpm", 6000, 7000),
            ("Speed", "speed", 120, 160),
            ("Engine Load", "engine_load", 80, 95),
            ("Coolant Temperature", "coolant_temp", 90, 105),
            ("Intake Temperature", "intake_temp", 60, 80),
            ("Throttle Position", "throttle_pos", 90, 100)
        ]

        for i, (name, key, warn_val, crit_val) in enumerate(thresholds):
            frame = ctk.CTkFrame(parent)
            frame.pack(fill="x", padx=5, pady=5)

            ctk.CTkLabel(frame, text=name, width=150).pack(side="left", padx=5)

            ctk.CTkLabel(frame, text="Warning:").pack(side="left", padx=5)
            warn_var = tk.StringVar(value=str(warn_val))
            warn_entry = ctk.CTkEntry(frame, textvariable=warn_var, width=80)
            warn_entry.pack(side="left", padx=5)

            ctk.CTkLabel(frame, text="Critical:").pack(side="left", padx=5)
            crit_var = tk.StringVar(value=str(crit_val))
            crit_entry = ctk.CTkEntry(frame, textvariable=crit_var, width=80)
            crit_entry.pack(side="left", padx=5)

            self.threshold_widgets[key] = {
                'warning': warn_var,
                'critical': crit_var
            }

    def clear_dtcs(self):
        """Clear Diagnostic Trouble Codes (DTCs) from the vehicle and update the display."""
        if not self.is_connected or not self.connection:
            messagebox.showwarning(
                "Not Connected", "Please connect to an OBD device first.")
            return
        try:
            # Attempt to clear DTCs using the OBD library
            # Note: Use the correct command for clearing DTCs
            try:
                response = self.connection.query(obd.commands.CLEAR_DTC)
                if response.is_null():
                    messagebox.showinfo(
                        "Clear DTCs", "No response from OBD device.")
                else:
                    messagebox.showinfo(
                        "Clear DTCs", "DTCs cleared successfully.")
            except AttributeError:
                messagebox.showinfo(
                    "Clear DTCs", "Clear DTC command not available in this OBD version.")
            except Exception as inner_e:
                messagebox.showerror(
                    "Error", f"Failed to clear DTCs: {str(inner_e)}")
                return
            # Refresh DTCs after clearing
            self.refresh_dtcs()
        except Exception as e:
            logger.error(f"Failed to clear DTCs: {str(e)}")
            messagebox.showerror("Error", f"Failed to clear DTCs: {str(e)}")

    def setup_enhanced_logs_tab(self):
        """Setup enhanced logs tab"""
        logs_frame = ctk.CTkFrame(self.logs_tab)
        logs_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Log controls
        controls_frame = ctk.CTkFrame(logs_frame)
        controls_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(controls_frame, text="Data Logging", font=ctk.CTkFont(
            size=16, weight="bold")).pack(side="left", padx=10)

        # Auto-save toggle
        self.auto_save_var = tk.BooleanVar(value=True)
        auto_save_cb = ctk.CTkCheckBox(
            controls_frame, text="Auto-save", variable=self.auto_save_var)
        auto_save_cb.pack(side="left", padx=10)

        # Log level selection
        ctk.CTkLabel(controls_frame, text="Log Level:").pack(
            side="left", padx=5)
        self.log_level_var = tk.StringVar(value="INFO")
        log_level_combo = ctk.CTkComboBox(controls_frame, variable=self.log_level_var,
                                          values=["DEBUG", "INFO", "WARNING", "ERROR"], width=100)
        log_level_combo.pack(side="left", padx=5)

        # Log control buttons
        save_btn = ctk.CTkButton(
            controls_frame, text="Save Logs", command=self.save_logs_enhanced, width=100)
        save_btn.pack(side="right", padx=5)

        clear_btn = ctk.CTkButton(
            controls_frame, text="Clear Logs", command=self.clear_logs, width=100)
        clear_btn.pack(side="right", padx=5)

        export_csv_btn = ctk.CTkButton(
            controls_frame, text="Export CSV", command=self.export_csv, width=100)
        export_csv_btn.pack(side="right", padx=5)

        # Log statistics
        stats_frame = ctk.CTkFrame(logs_frame)
        stats_frame.pack(fill="x", padx=10, pady=5)

        self.log_stats_label = ctk.CTkLabel(
            stats_frame, text="Log entries: 0 | Session time: 00:00:00")
        self.log_stats_label.pack(side="left", padx=10, pady=5)

        # Logs display with search functionality
        search_frame = ctk.CTkFrame(logs_frame)
        search_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(search_frame, text="Search:").pack(side="left", padx=5)
        self.search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(
            search_frame, textvariable=self.search_var, width=200)
        search_entry.pack(side="left", padx=5)
        search_entry.bind('<KeyRelease>', self.search_logs)

        search_btn = ctk.CTkButton(
            search_frame, text="Search", command=self.search_logs, width=80)
        search_btn.pack(side="left", padx=5)

        # Enhanced logs display
        self.logs_text = ctk.CTkTextbox(
            logs_frame, height=300, font=("Consolas", 9))
        self.logs_text.pack(fill="both", expand=True, padx=10, pady=10)

    def setup_settings_tab(self):
        """Setup settings configuration tab"""
        settings_frame = ctk.CTkScrollableFrame(self.settings_tab)
        settings_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(settings_frame, text="Application Settings",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        # Appearance settings
        appearance_frame = ctk.CTkFrame(settings_frame)
        appearance_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(appearance_frame, text="Appearance",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)

        # Theme selection
        theme_frame = ctk.CTkFrame(appearance_frame)
        theme_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(theme_frame, text="Theme:").pack(side="left", padx=5)
        self.theme_var = tk.StringVar(value=self.config['appearance']['mode'])
        theme_combo = ctk.CTkComboBox(theme_frame, variable=self.theme_var,
                                      values=["dark", "light", "system"], width=120)
        theme_combo.pack(side="left", padx=5)

        apply_theme_btn = ctk.CTkButton(
            theme_frame, text="Apply", command=self.apply_theme, width=80)
        apply_theme_btn.pack(side="left", padx=10)

        # Color theme
        color_frame = ctk.CTkFrame(appearance_frame)
        color_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(color_frame, text="Color Theme:").pack(
            side="left", padx=5)
        self.color_theme_var = tk.StringVar(
            value=self.config['appearance']['theme'])

        # Timeout setting
        timeout_frame = ctk.CTkFrame(settings_frame)
        timeout_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(timeout_frame, text="Connection Timeout (s):").pack(
            side="left", padx=5)
        self.timeout_var = tk.StringVar(
            value=str(self.config['connection'].get('timeout', 10)))
        timeout_entry = ctk.CTkEntry(
            timeout_frame, textvariable=self.timeout_var, width=80)
        timeout_entry.pack(side="left", padx=5)

        # Max log entries setting
        max_logs_frame = ctk.CTkFrame(settings_frame)
        max_logs_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(max_logs_frame, text="Max Log Entries:").pack(
            side="left", padx=5)
        self.max_logs_var = tk.StringVar(
            value=str(self.config['monitoring'].get('max_log_entries', 1000)))
        max_logs_entry = ctk.CTkEntry(
            max_logs_frame, textvariable=self.max_logs_var, width=80)
        max_logs_entry.pack(side="left", padx=5)

    def export_data(self):
        """Export monitoring data to CSV file"""
        if not self.log_data:
            messagebox.showwarning("No Data", "No data to export")
            return

        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialdir=self.config.get('monitoring', {}).get(
                    'log_directory', 'logs')
            )

            if filename:
                with open(filename, 'w', newline='') as csvfile:
                    fieldnames = ['timestamp', 'pid', 'name', 'value', 'unit']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    writer.writeheader()
                    for entry in self.log_data:
                        writer.writerow(entry)

                messagebox.showinfo("Export Complete",
                                    f"Data exported to {filename}")
                logger.info(f"Data exported to {filename}")

        except Exception as e:
            logger.error(f"Failed to export data: {str(e)}")
            messagebox.showerror(
                "Export Error", f"Failed to export data: {str(e)}")

    def export_pids_data(self):
        """Export current PID data to CSV file"""
        if not self.pid_data:
            messagebox.showwarning("No Data", "No PID data to export")
            return

        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialdir=self.config.get('monitoring', {}).get(
                    'log_directory', 'logs')
            )

            if filename:
                with open(filename, 'w', newline='') as csvfile:
                    fieldnames = ['pid', 'name', 'value', 'unit', 'timestamp']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    writer.writeheader()
                    for pid_name, data in self.pid_data.items():
                        writer.writerow({
                            'pid': pid_name,
                            'name': data.get('name', pid_name),
                            'value': data.get('value', ''),
                            'unit': data.get('unit', ''),
                            'timestamp': data.get('timestamp', '')
                        })

                messagebox.showinfo("Export Complete",
                                    f"PID data exported to {filename}")
                logger.info(f"PID data exported to {filename}")

        except Exception as e:
            logger.error(f"Failed to export PID data: {str(e)}")
            messagebox.showerror(
                "Export Error", f"Failed to export PID data: {str(e)}")

    def export_dtcs(self):
        """Export DTC data to text file"""
        if not self.dtc_data:
            messagebox.showwarning("No Data", "No DTC data to export")
            return

        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialdir=self.config.get('monitoring', {}).get(
                    'log_directory', 'logs')
            )

            if filename:
                with open(filename, 'w') as f:
                    f.write("Diagnostic Trouble Codes Report\n")
                    f.write("=" * 40 + "\n\n")
                    f.write(
                        f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Total DTCs: {len(self.dtc_data)}\n\n")

                    for i, dtc in enumerate(self.dtc_data, 1):
                        f.write(f"{i}. {dtc}\n")

                messagebox.showinfo("Export Complete",
                                    f"DTCs exported to {filename}")
                logger.info(f"DTCs exported to {filename}")

        except Exception as e:
            logger.error(f"Failed to export DTCs: {str(e)}")
            messagebox.showerror(
                "Export Error", f"Failed to export DTCs: {str(e)}")

    def filter_pids(self, event=None):
        """Filter PIDs based on search term"""
        if not hasattr(self, 'pids_tree'):
            return

        search_term = self.pid_filter_var.get().lower()

        # Clear existing items
        for item in self.pids_tree.get_children():
            self.pids_tree.delete(item)

        # Add filtered items
        for pid_name, data in self.pid_data.items():
            if search_term in pid_name.lower() or search_term in data.get('name', '').lower():
                self.pids_tree.insert("", "end", values=(
                    pid_name,
                    data.get('name', pid_name),
                    data.get('value', '--'),
                    data.get('unit', ''),
                    data.get('min_value', '--'),
                    data.get('max_value', '--'),
                    data.get('timestamp', '--'),
                    data.get('status', 'OK')
                ))

    def start_charting(self):
        """Start real-time charting for selected PID"""
        selected_pid = self.chart_pid_var.get()
        if not selected_pid:
            messagebox.showwarning(
                "No PID Selected", "Please select a PID to chart")
            return

        if not self.is_connected:
            messagebox.showwarning(
                "Not Connected", "Please connect to OBD device first")
            return

        # Initialize chart data
        self.chart_data = {'x': [], 'y': []}
        self.charting_active = True

        # Start chart update thread
        self.chart_thread = threading.Thread(
            target=self.update_chart, daemon=True)
        self.chart_thread.start()

        logger.info(f"Started charting for PID: {selected_pid}")

    def stop_charting(self):
        """Stop real-time charting"""
        self.charting_active = False
        if hasattr(self, 'chart_thread') and self.chart_thread.is_alive():
            self.chart_thread.join(timeout=1)

        logger.info("Stopped charting")

    def update_chart(self):
        """Update chart with real-time data"""
        selected_pid = self.chart_pid_var.get()

        while self.charting_active and self.is_connected:
            try:
                # Get current value for selected PID
                if selected_pid in self.pid_data:
                    current_time = time.time()
                    current_value = self.pid_data[selected_pid].get('value', 0)

                    # Try to convert to float
                    try:
                        current_value = float(current_value)
                    except (ValueError, TypeError):
                        current_value = 0

                    # Add to chart data
                    self.chart_data['x'].append(current_time)
                    self.chart_data['y'].append(current_value)

                    # Limit data points to last 100
                    if len(self.chart_data['x']) > 100:
                        self.chart_data['x'] = self.chart_data['x'][-100:]
                        self.chart_data['y'] = self.chart_data['y'][-100:]

                    # Update chart in main thread
                    self.root.after(0, self.refresh_chart)

                time.sleep(0.5)  # Update every 500ms

            except Exception as e:
                logger.error(f"Error updating chart: {str(e)}")
                break

    def refresh_chart(self):
        """Refresh the matplotlib chart"""
        if not hasattr(self, 'chart_line') or not self.chart_data['x']:
            return

        try:
            # Update chart data
            self.chart_line.set_data(
                self.chart_data['x'], self.chart_data['y'])

            # Update axes
            if self.chart_data['x']:
                self.ax.set_xlim(
                    min(self.chart_data['x']), max(self.chart_data['x']))
                self.ax.set_ylim(
                    min(self.chart_data['y']) - 1, max(self.chart_data['y']) + 1)

            # Refresh canvas
            self.canvas.draw()

        except Exception as e:
            logger.error(f"Error refreshing chart: {str(e)}")

    def refresh_dtcs(self):
        """Refresh DTC data from vehicle"""
        if not self.is_connected or not self.connection:
            messagebox.showwarning(
                "Not Connected", "Please connect to an OBD device first.")
            return

        try:
            # Query DTCs
            try:
                dtc_response = self.connection.query(obd.commands.GET_DTC)

                if dtc_response.is_null():
                    self.dtc_data = []
                    dtc_text = "No DTCs found or unable to retrieve DTCs"
                else:
                    self.dtc_data = dtc_response.value if dtc_response.value else []

                    if self.dtc_data:
                        dtc_text = f"Found {len(self.dtc_data)} DTC(s):\n\n"
                        for dtc in self.dtc_data:
                            dtc_text += f"• {dtc}\n"
                    else:
                        dtc_text = "No DTCs found - Vehicle systems OK"

            except AttributeError:
                # If GET_DTC is not available, try alternative
                self.dtc_data = []
                dtc_text = "DTC query not supported by this OBD adapter"
                # Update UI
                self.dtcs_text.delete("1.0", tk.END)
                self.dtcs_text.insert("1.0", dtc_text)
                return

            # Update UI
            self.dtcs_text.delete("1.0", tk.END)
            self.dtcs_text.insert("1.0", dtc_text)

            # Update status
            self.dtc_count_label.configure(
                text=f"DTCs Found: {len(self.dtc_data)}")

            if self.dtc_data:
                self.dtc_status_label.configure(
                    text="Status: Issues Found", text_color="red")
            else:
                self.dtc_status_label.configure(
                    text="Status: OK", text_color="green")

            logger.info(f"DTCs refreshed: {len(self.dtc_data)} found")

        except Exception as e:
            logger.error(f"Failed to refresh DTCs: {str(e)}")
            messagebox.showerror("Error", f"Failed to refresh DTCs: {str(e)}")

    def on_closing(self):
        """Handle window close event: save config and cleanup."""
        try:
            self.save_config_to_file()
        except Exception as e:
            logger.error(f"Error saving config on close: {str(e)}")
        self.root.destroy()

    def save_config(self):
        """Save current configuration"""
        try:
            self.config['window'] = {
                'geometry': self.root.geometry(),
                'state': self.root.state()
            }

            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=2)

            logger.info("Configuration saved")

        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")

    def update_session_timer(self):
        """Update session timer display"""
        try:
            elapsed = datetime.datetime.now() - self.session_start_time
            hours, remainder = divmod(elapsed.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.session_label.configure(text=f"Session: {time_str}")

            # Schedule next update
            self.root.after(1000, self.update_session_timer)
        except Exception as e:
            logger.error(f"Error updating session timer: {str(e)}")

    def update_connection_status(self, connected):
        """Update connection status in UI"""
        try:
            if connected:
                self.connection_status.configure(
                    text="Connected", text_color="green")
                self.connect_btn.configure(state="disabled")
                self.disconnect_btn.configure(state="normal")
                self.start_btn.configure(state="normal")
                self.clear_dtc_btn.configure(state="normal")
                self.export_btn.configure(state="normal")
            else:
                self.connection_status.configure(
                    text="Disconnected", text_color="red")
                self.connect_btn.configure(state="normal")
                self.disconnect_btn.configure(state="disabled")
                self.start_btn.configure(state="disabled")
                self.stop_btn.configure(state="disabled")
                self.clear_dtc_btn.configure(state="disabled")
                self.export_btn.configure(state="disabled")
        except Exception as e:
            logger.error(f"Error updating connection status: {str(e)}")

    def get_available_pids(self):
        """Get list of available PIDs from the vehicle"""
        try:
            if not self.connection:
                return

            self.available_pids = []
            # Get supported PIDs
            try:
                for cmd in obd.commands:
                    if cmd and hasattr(cmd, 'supported') and cmd.supported:
                        if hasattr(cmd, 'name'):
                            self.available_pids.append(cmd.name)
            except Exception as e:
                logger.warning(f"Could not enumerate OBD commands: {e}")
                # Add some common PIDs manually
                self.available_pids = [
                    'RPM', 'SPEED', 'ENGINE_LOAD', 'COOLANT_TEMP', 'INTAKE_TEMP', 'THROTTLE_POS']

            # Update chart PID combo
            if hasattr(self, 'chart_pid_combo'):
                self.chart_pid_combo.configure(values=self.available_pids)
                if self.available_pids:
                    self.chart_pid_combo.set(self.available_pids[0])

            logger.info(f"Found {len(self.available_pids)} available PIDs")

        except Exception as e:
            logger.error(f"Error getting available PIDs: {str(e)}")

    def start_monitoring(self):
        """Start OBD monitoring"""
        if not self.is_connected:
            messagebox.showwarning(
                "Not Connected", "Please connect to OBD device first")
            return

        if self.monitoring:
            return

        self.monitoring = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_label.configure(text="Monitoring started")

        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

        logger.info("OBD monitoring started")

    def stop_monitoring(self):
        """Stop OBD monitoring"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_label.configure(text="Monitoring stopped")
        logger.info("Monitoring stopped")

    def monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring and self.is_connected:
            try:
                # Query common PIDs with error handling
                common_pids = []

                # Try to get common PIDs from obd commands
                try:
                    # Use getattr to safely access commands
                    rpm_cmd = getattr(obd.commands, 'RPM', None)
                    speed_cmd = getattr(obd.commands, 'SPEED', None)
                    load_cmd = getattr(obd.commands, 'ENGINE_LOAD', None)
                    coolant_cmd = getattr(obd.commands, 'COOLANT_TEMP', None)
                    intake_cmd = getattr(obd.commands, 'INTAKE_TEMP', None)
                    throttle_cmd = getattr(obd.commands, 'THROTTLE_POS', None)

                    # Add valid commands to the list
                    for cmd in [rpm_cmd, speed_cmd, load_cmd, coolant_cmd, intake_cmd, throttle_cmd]:
                        if cmd is not None:
                            common_pids.append(cmd)

                except AttributeError:
                    # If specific commands are not available, try alternative approach
                    logger.warning(
                        "Some OBD commands not available in this version")
                    # Use a more generic approach
                    try:
                        for cmd in obd.commands:
                            if cmd and hasattr(cmd, 'name') and cmd.name in ['RPM', 'SPEED', 'ENGINE_LOAD']:
                                common_pids.append(cmd)
                    except:
                        # If all else fails, skip this iteration
                        continue

                for pid in common_pids:
                    if self.connection and self.monitoring:
                        try:
                            response = self.connection.query(pid)
                            if not response.is_null():
                                self.update_pid_data(
                                    pid.name, response.value, str(response.unit))
                        except Exception as e:
                            logger.error(
                                f"Error querying PID {pid.name}: {str(e)}")

                # Update dashboard
                self.root.after(0, self.update_dashboard)
                self.root.after(0, self.update_pids_display)

                # Sleep based on update interval
                interval = int(self.interval_var.get()) / 1000.0
                time.sleep(interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                break

    def update_pid_data(self, pid_name, value, unit):
        """Update PID data storage"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if pid_name not in self.pid_data:
                self.pid_data[pid_name] = {
                    'name': pid_name,
                    'value': value,
                    'unit': unit,
                    'timestamp': timestamp,
                    'min_value': value,
                    'max_value': value,
                    'status': 'OK'
                }
            else:
                # Update existing data
                self.pid_data[pid_name]['value'] = value
                self.pid_data[pid_name]['timestamp'] = timestamp

                # Update min/max values
                if isinstance(value, (int, float)):
                    current_min = self.pid_data[pid_name].get(
                        'min_value', value)
                    current_max = self.pid_data[pid_name].get(
                        'max_value', value)

                    if isinstance(current_min, (int, float)) and value < current_min:
                        self.pid_data[pid_name]['min_value'] = value
                    if isinstance(current_max, (int, float)) and value > current_max:
                        self.pid_data[pid_name]['max_value'] = value

            # Add to log data
            self.log_data.append({
                'timestamp': timestamp,
                'pid': pid_name,
                'name': pid_name,
                'value': value,
                'unit': unit
            })

            # Limit log data size
            max_entries = self.config.get(
                'monitoring', {}).get('max_log_entries', 1000)
            if len(self.log_data) > max_entries:
                self.log_data = self.log_data[-max_entries:]

        except Exception as e:
            logger.error(f"Error updating PID data: {str(e)}")

    def update_dashboard(self):
        """Update dashboard widgets"""
        try:
            for key, widget_data in self.dashboard_widgets.items():
                if key in self.pid_data:
                    value = self.pid_data[key]['value']

                    # Update value label
                    if isinstance(value, (int, float)):
                        widget_data['value_label'].configure(
                            text=f"{value:.1f}")

                        # Update progress bar
                        min_val = widget_data['min_val']
                        max_val = widget_data['max_val']
                        progress = (value - min_val) / (max_val -
                                                        min_val) if max_val > min_val else 0
                        progress = max(0, min(1, progress))  # Clamp to 0-1
                        widget_data['progress'].set(progress)
                    else:
                        widget_data['value_label'].configure(text=str(value))
                        widget_data['progress'].set(0)
                else:
                    widget_data['value_label'].configure(text="--")
                    widget_data['progress'].set(0)

        except Exception as e:
            logger.error(f"Error updating dashboard: {str(e)}")

    def update_pids_display(self):
        """Update PIDs tree display"""
        try:
            if not hasattr(self, 'pids_tree'):
                return

            # Clear existing items
            for item in self.pids_tree.get_children():
                self.pids_tree.delete(item)

            # Add current PID data
            for pid_name, data in self.pid_data.items():
                self.pids_tree.insert("", "end", values=(
                    pid_name,
                    data.get('name', pid_name),
                    data.get('value', '--'),
                    data.get('unit', ''),
                    data.get('min_value', '--'),
                    data.get('max_value', '--'),
                    data.get('timestamp', '--'),
                    data.get('status', 'OK')
                ))

        except Exception as e:
            logger.error(f"Error updating PIDs display: {str(e)}")

    def save_logs_enhanced(self):
        """Save logs to file with enhanced formatting"""
        try:
            if not self.log_data:
                messagebox.showwarning("No Data", "No log data to save")
                return

            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialdir=self.config.get('monitoring', {}).get(
                    'log_directory', 'logs')
            )

            if filename:
                with open(filename, 'w') as f:
                    f.write(
                        f"OBD Monitor Log - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 60 + "\n\n")

                    for entry in self.log_data:
                        f.write(
                            f"[{entry['timestamp']}] {entry['pid']}: {entry['value']} {entry['unit']}\n")

                messagebox.showinfo(
                    "Save Complete", f"Logs saved to {filename}")
                logger.info(f"Logs saved to {filename}")

        except Exception as e:
            logger.error(f"Error saving logs: {str(e)}")
            messagebox.showerror(
                "Save Error", f"Failed to save logs: {str(e)}")

    def clear_logs(self):
        """Clear all log data"""
        try:
            result = messagebox.askyesno(
                "Clear Logs", "Are you sure you want to clear all log data?")
            if result:
                self.log_data.clear()
                self.logs_text.delete("1.0", tk.END)
                logger.info("Log data cleared")
                messagebox.showinfo("Clear Complete", "Log data cleared")
        except Exception as e:
            logger.error(f"Error clearing logs: {str(e)}")

    def export_csv(self):
        """Export logs to CSV format"""
        try:
            if not self.log_data:
                messagebox.showwarning("No Data", "No log data to export")
                return

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialdir=self.config.get('monitoring', {}).get(
                    'log_directory', 'logs')
            )

            if filename:
                with open(filename, 'w', newline='') as csvfile:
                    fieldnames = ['timestamp', 'pid', 'name', 'value', 'unit']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    writer.writeheader()
                    for entry in self.log_data:
                        writer.writerow(entry)

                messagebox.showinfo("Export Complete",
                                    f"Data exported to {filename}")
                logger.info(f"Data exported to {filename}")

        except Exception as e:
            logger.error(f"Error exporting CSV: {str(e)}")
            messagebox.showerror(
                "Export Error", f"Failed to export CSV: {str(e)}")

    def search_logs(self, event=None):
        """Search through log data"""
        try:
            search_term = self.search_var.get().lower()

            # Clear current display
            self.logs_text.delete("1.0", tk.END)

            if not search_term:
                # Show all logs if no search term
                for entry in self.log_data[-100:]:  # Show last 100 entries
                    log_line = f"[{entry['timestamp']}] {entry['pid']}: {entry['value']} {entry['unit']}\n"
                    self.logs_text.insert(tk.END, log_line)
            else:
                # Filter logs based on search term
                filtered_logs = []
                for entry in self.log_data:
                    if (search_term in entry['pid'].lower() or
                        search_term in entry['name'].lower() or
                            search_term in str(entry['value']).lower()):
                        filtered_logs.append(entry)

                # Display filtered results
                # Show last 100 matching entries
                for entry in filtered_logs[-100:]:
                    log_line = f"[{entry['timestamp']}] {entry['pid']}: {entry['value']} {entry['unit']}\n"
                    self.logs_text.insert(tk.END, log_line)

        except Exception as e:
            logger.error(f"Error searching logs: {str(e)}")

    def apply_theme(self):
        """Apply selected theme"""
        try:
            theme = self.theme_var.get()
            ctk.set_appearance_mode(theme)
            self.config['appearance']['mode'] = theme
            logger.info(f"Theme changed to {theme}")
            messagebox.showinfo("Theme Applied", f"Theme changed to {theme}")
        except Exception as e:
            logger.error(f"Error applying theme: {str(e)}")
            messagebox.showerror(
                "Theme Error", f"Failed to apply theme: {str(e)}")

    def run(self):
        """Run the application"""
        try:
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Application error: {str(e)}")
            messagebox.showerror("Application Error",
                                 f"An error occurred: {str(e)}")


class OBDMonitorApp:
    """Main application class"""

    def __init__(self):
        self.monitor = EnhancedOBDMonitor()

    def run(self):
        """Run the application"""
        self.monitor.run()


def main():
    """Main function to run the application"""
    try:
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)

        # Initialize and run the application
        app = OBDMonitorApp()
        app.run()

    except Exception as e:
        logger.error(f"Application startup failed: {str(e)}")
        try:
            messagebox.showerror(
                "Startup Error", f"Failed to start application: {str(e)}")
        except:
            print(f"Startup Error: Failed to start application: {str(e)}")


if __name__ == "__main__":
    main()
