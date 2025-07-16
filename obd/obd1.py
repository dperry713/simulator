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
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import tkinterweb
import tempfile
import webbrowser

# For Windows audio alerts
try:
    import winsound
except ImportError:
    winsound = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlotlyChartManager:
    """Manager for Plotly-based interactive charts"""
    
    def __init__(self, parent, theme='dark'):
        self.parent = parent
        self.theme = theme
        self.charts = {}
        self.data_cache = {}
        self.selected_pids = []
        self.chart_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#6C5CE7', '#FD79A8', '#FDCB6E']
        self.color_index = 0
        self.temp_dir = tempfile.mkdtemp()
        
    def get_theme_colors(self):
        """Get theme-specific colors"""
        if self.theme == 'dark':
            return {
                'background': '#2b2b2b',
                'paper': '#1e1e1e',
                'text': '#ffffff',
                'grid': '#404040',
                'font_family': 'Arial, sans-serif'
            }
        else:
            return {
                'background': '#ffffff',
                'paper': '#f8f9fa',
                'text': '#000000',
                'grid': '#e0e0e0',
                'font_family': 'Arial, sans-serif'
            }
    
    def create_real_time_chart(self, title="Real-time OBD Data", height=600):
        """Create a real-time chart with multiple PID support"""
        colors = self.get_theme_colors()
        
        fig = go.Figure()
        
        # Configure layout for dark/light theme
        fig.update_layout(
            title=dict(
                text=title,
                font=dict(color=colors['text'], size=16, family=colors['font_family']),
                x=0.5
            ),
            plot_bgcolor=colors['background'],
            paper_bgcolor=colors['paper'],
            font=dict(color=colors['text'], family=colors['font_family']),
            xaxis=dict(
                title="Time",
                gridcolor=colors['grid'],
                color=colors['text'],
                showgrid=True,
                type='date'
            ),
            yaxis=dict(
                title="Value",
                gridcolor=colors['grid'],
                color=colors['text'],
                showgrid=True
            ),
            height=height,
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor="rgba(0,0,0,0)",
                bordercolor=colors['text'],
                borderwidth=1
            )
        )
        
        return fig
    
    def create_dashboard_chart(self, pid_data, chart_type='line'):
        """Create dashboard-style chart with trend analysis"""
        colors = self.get_theme_colors()
        
        if chart_type == 'gauge':
            return self.create_gauge_chart(pid_data)
        elif chart_type == 'sparkline':
            return self.create_sparkline_chart(pid_data)
        else:
            return self.create_trend_chart(pid_data)
    
    def create_gauge_chart(self, pid_data):
        """Create a gauge chart for dashboard"""
        colors = self.get_theme_colors()
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = pid_data.get('value', 0),
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': pid_data.get('name', 'PID')},
            delta = {'reference': pid_data.get('reference', 0)},
            gauge = {
                'axis': {'range': [None, pid_data.get('max_value', 100)]},
                'bar': {'color': self.chart_colors[self.color_index % len(self.chart_colors)]},
                'steps': [
                    {'range': [0, pid_data.get('warning_threshold', 50)], 'color': "lightgray"},
                    {'range': [pid_data.get('warning_threshold', 50), pid_data.get('critical_threshold', 75)], 'color': "yellow"},
                    {'range': [pid_data.get('critical_threshold', 75), pid_data.get('max_value', 100)], 'color': "red"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': pid_data.get('critical_threshold', 75)
                }
            }
        ))
        
        fig.update_layout(
            paper_bgcolor=colors['paper'],
            plot_bgcolor=colors['background'],
            font=dict(color=colors['text'], family=colors['font_family']),
            height=300
        )
        
        return fig
    
    def create_sparkline_chart(self, pid_data):
        """Create a sparkline chart for compact display"""
        colors = self.get_theme_colors()
        
        x_data = pid_data.get('timestamps', [])
        y_data = pid_data.get('values', [])
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=x_data,
            y=y_data,
            mode='lines',
            line=dict(color=self.chart_colors[self.color_index % len(self.chart_colors)], width=2),
            fill='tonexty',
            fillcolor=f"rgba({','.join(map(str, [int(self.chart_colors[self.color_index % len(self.chart_colors)][1:3], 16), int(self.chart_colors[self.color_index % len(self.chart_colors)][3:5], 16), int(self.chart_colors[self.color_index % len(self.chart_colors)][5:7], 16)]))}, 0.2)",
            showlegend=False
        ))
        
        fig.update_layout(
            paper_bgcolor=colors['paper'],
            plot_bgcolor=colors['background'],
            font=dict(color=colors['text'], family=colors['font_family']),
            height=100,
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=False,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        
        return fig
    
    def create_trend_chart(self, pid_data):
        """Create a trend analysis chart"""
        colors = self.get_theme_colors()
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Real-time Values', 'Min/Max/Avg Trends'),
            vertical_spacing=0.1,
            row_heights=[0.7, 0.3]
        )
        
        x_data = pid_data.get('timestamps', [])
        y_data = pid_data.get('values', [])
        
        # Main trend line
        fig.add_trace(
            go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines',
                name='Current Value',
                line=dict(color=self.chart_colors[0], width=2),
                hovertemplate='<b>%{y:.2f}</b><br>%{x}<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Min/Max envelope
        if len(y_data) > 1:
            min_vals = [min(y_data[:i+1]) for i in range(len(y_data))]
            max_vals = [max(y_data[:i+1]) for i in range(len(y_data))]
            
            fig.add_trace(
                go.Scatter(
                    x=x_data,
                    y=max_vals,
                    mode='lines',
                    name='Max',
                    line=dict(color=self.chart_colors[1], width=1),
                    showlegend=False
                ),
                row=2, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=x_data,
                    y=min_vals,
                    mode='lines',
                    name='Min',
                    line=dict(color=self.chart_colors[2], width=1),
                    fill='tonexty',
                    fillcolor=f"rgba({','.join(map(str, [int(self.chart_colors[1][1:3], 16), int(self.chart_colors[1][3:5], 16), int(self.chart_colors[1][5:7], 16)]))}, 0.2)",
                    showlegend=False
                ),
                row=2, col=1
            )
        
        fig.update_layout(
            paper_bgcolor=colors['paper'],
            plot_bgcolor=colors['background'],
            font=dict(color=colors['text'], family=colors['font_family']),
            height=500,
            hovermode='x unified',
            showlegend=True
        )
        
        return fig
    
    def update_chart_data(self, chart_id, pid_name, timestamp, value):
        """Update chart data for real-time updates"""
        if chart_id not in self.data_cache:
            self.data_cache[chart_id] = {}
        
        if pid_name not in self.data_cache[chart_id]:
            self.data_cache[chart_id][pid_name] = {'timestamps': [], 'values': []}
        
        # Add new data point
        self.data_cache[chart_id][pid_name]['timestamps'].append(timestamp)
        self.data_cache[chart_id][pid_name]['values'].append(value)
        
        # Limit data points to last 100 for performance
        if len(self.data_cache[chart_id][pid_name]['timestamps']) > 100:
            self.data_cache[chart_id][pid_name]['timestamps'] = self.data_cache[chart_id][pid_name]['timestamps'][-100:]
            self.data_cache[chart_id][pid_name]['values'] = self.data_cache[chart_id][pid_name]['values'][-100:]
    
    def generate_chart_html(self, fig, chart_id):
        """Generate HTML for chart embedding"""
        html_content = fig.to_html(
            include_plotlyjs='cdn',
            div_id=chart_id,
            config={
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
                'responsive': True
            }
        )
        
        # Add custom styling for dark/light theme
        colors = self.get_theme_colors()
        custom_css = f"""
        <style>
            body {{
                background-color: {colors['background']};
                color: {colors['text']};
                font-family: {colors['font_family']};
                margin: 0;
                padding: 0;
            }}
            .plotly-graph-div {{
                background-color: {colors['background']};
            }}
        </style>
        """
        
        html_content = html_content.replace('<head>', f'<head>{custom_css}')
        return html_content
    
    def save_chart_html(self, fig, chart_id):
        """Save chart as HTML file and return path"""
        html_content = self.generate_chart_html(fig, chart_id)
        html_path = os.path.join(self.temp_dir, f'{chart_id}.html')
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return html_path
    
    def set_theme(self, theme):
        """Update theme for all charts"""
        self.theme = theme
        # Refresh all active charts with new theme
        for chart_id in self.charts:
            self.refresh_chart(chart_id)
    
    def refresh_chart(self, chart_id):
        """Refresh a specific chart"""
        if chart_id in self.charts:
            chart_info = self.charts[chart_id]
            # This would trigger a chart update in the UI
            pass
    
    def cleanup(self):
        """Clean up temporary files"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass


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

        # Initialize Plotly chart manager
        self.plotly_manager = PlotlyChartManager(self.root, self.config['appearance']['mode'])
        
        # Chart state
        self.charting_active = False
        self.chart_thread = None

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
        
        # Advanced Dashboard tab (new Plotly-based)
        self.advanced_dashboard_tab = self.notebook.add("Advanced Dashboard")
        self.setup_advanced_dashboard_tab()

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
        """Setup real-time charts tab with Plotly integration"""
        charts_frame = ctk.CTkFrame(self.charts_tab)
        charts_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Chart controls
        controls_frame = ctk.CTkFrame(charts_frame)
        controls_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(controls_frame, text="Interactive Real-time Charts (Plotly)",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=10)

        # Multi-PID selection for charting
        pid_selection_frame = ctk.CTkFrame(controls_frame)
        pid_selection_frame.pack(side="left", padx=20)
        
        ctk.CTkLabel(pid_selection_frame, text="Select PIDs:").pack(side="left", padx=5)
        self.selected_pids_var = tk.StringVar()
        self.selected_pids_listbox = tk.Listbox(pid_selection_frame, selectmode=tk.MULTIPLE, height=3, width=30)
        self.selected_pids_listbox.pack(side="left", padx=5)
        
        # Chart type selection
        ctk.CTkLabel(pid_selection_frame, text="Chart Type:").pack(side="left", padx=5)
        self.chart_type_var = tk.StringVar(value="line")
        chart_type_combo = ctk.CTkComboBox(pid_selection_frame, variable=self.chart_type_var,
                                          values=["line", "scatter", "bar"], width=100)
        chart_type_combo.pack(side="left", padx=5)

        # Chart controls
        chart_controls_frame = ctk.CTkFrame(controls_frame)
        chart_controls_frame.pack(side="right", padx=10)
        
        start_plotly_chart_btn = ctk.CTkButton(
            chart_controls_frame, text="Start Plotly Chart", command=self.start_plotly_charting, width=120)
        start_plotly_chart_btn.pack(side="left", padx=5)

        stop_plotly_chart_btn = ctk.CTkButton(
            chart_controls_frame, text="Stop Chart", command=self.stop_plotly_charting, width=100)
        stop_plotly_chart_btn.pack(side="left", padx=5)
        
        refresh_chart_btn = ctk.CTkButton(
            chart_controls_frame, text="Refresh", command=self.refresh_plotly_chart, width=80)
        refresh_chart_btn.pack(side="left", padx=5)

        # Main chart display area
        chart_display_frame = ctk.CTkFrame(charts_frame)
        chart_display_frame.pack(fill="both", expand=True, pady=5)
        
        # Create notebook for multiple chart views
        self.chart_notebook = ctk.CTkTabview(chart_display_frame)
        self.chart_notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Plotly chart tab
        self.plotly_chart_tab = self.chart_notebook.add("Interactive Chart")
        self.setup_plotly_chart_widget()
        
        # Legacy matplotlib tab (commented out but kept for reference)
        # self.matplotlib_tab = self.chart_notebook.add("Legacy Chart")
        # self.setup_matplotlib_chart_legacy()

    def setup_plotly_chart_widget(self):
        """Setup the Plotly chart widget using tkinterweb"""
        try:
            # Create tkinterweb HTML widget for Plotly charts
            self.plotly_widget = tkinterweb.HtmlFrame(self.plotly_chart_tab, messages_enabled=False)
            self.plotly_widget.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Load initial empty chart
            self.load_initial_plotly_chart()
            
        except Exception as e:
            logger.error(f"Error setting up Plotly widget: {str(e)}")
            # Fallback to label if tkinterweb fails
            error_label = ctk.CTkLabel(self.plotly_chart_tab, 
                                     text=f"Error loading Plotly widget: {str(e)}\nPlease check tkinterweb installation.")
            error_label.pack(expand=True)
    
    def load_initial_plotly_chart(self):
        """Load an initial empty Plotly chart"""
        try:
            initial_fig = self.plotly_manager.create_real_time_chart("Select PIDs and Start Monitoring")
            html_path = self.plotly_manager.save_chart_html(initial_fig, "main_chart")
            self.plotly_widget.load_file(html_path)
        except Exception as e:
            logger.error(f"Error loading initial Plotly chart: {str(e)}")
    
    def start_plotly_charting(self):
        """Start real-time Plotly charting for selected PIDs"""
        try:
            # Get selected PIDs from listbox
            selected_indices = self.selected_pids_listbox.curselection()
            if not selected_indices:
                messagebox.showwarning("No PIDs Selected", "Please select one or more PIDs to chart")
                return
            
            selected_pids = [self.selected_pids_listbox.get(i) for i in selected_indices]
            
            if not self.is_connected:
                messagebox.showwarning("Not Connected", "Please connect to OBD device first")
                return
            
            # Update plotly manager with selected PIDs
            self.plotly_manager.selected_pids = selected_pids
            
            # Start charting
            self.charting_active = True
            self.chart_thread = threading.Thread(target=self.update_plotly_chart, daemon=True)
            self.chart_thread.start()
            
            logger.info(f"Started Plotly charting for PIDs: {selected_pids}")
            
        except Exception as e:
            logger.error(f"Error starting Plotly charting: {str(e)}")
            messagebox.showerror("Charting Error", f"Failed to start charting: {str(e)}")
    
    def stop_plotly_charting(self):
        """Stop real-time Plotly charting"""
        try:
            self.charting_active = False
            if hasattr(self, 'chart_thread') and self.chart_thread and self.chart_thread.is_alive():
                self.chart_thread.join(timeout=1)
            
            logger.info("Stopped Plotly charting")
            
        except Exception as e:
            logger.error(f"Error stopping Plotly charting: {str(e)}")
    
    def update_plotly_chart(self):
        """Update Plotly chart with real-time data"""
        try:
            chart_id = "main_chart"
            
            while self.charting_active and self.is_connected:
                # Create new figure for real-time update
                fig = self.plotly_manager.create_real_time_chart(
                    f"Real-time Data: {', '.join(self.plotly_manager.selected_pids)}"
                )
                
                # Add traces for each selected PID
                for i, pid_name in enumerate(self.plotly_manager.selected_pids):
                    if pid_name in self.pid_data:
                        # Get cached data for this PID
                        if chart_id in self.plotly_manager.data_cache and pid_name in self.plotly_manager.data_cache[chart_id]:
                            data = self.plotly_manager.data_cache[chart_id][pid_name]
                            
                            fig.add_trace(go.Scatter(
                                x=data['timestamps'],
                                y=data['values'],
                                mode='lines+markers',
                                name=f"{pid_name} ({self.pid_data[pid_name].get('unit', '')})",
                                line=dict(color=self.plotly_manager.chart_colors[i % len(self.plotly_manager.chart_colors)], width=2),
                                marker=dict(size=4),
                                hovertemplate=f'<b>{pid_name}</b><br>Value: %{{y}}<br>Time: %{{x}}<extra></extra>'
                            ))
                
                # Update chart in main thread
                self.root.after(0, self.refresh_plotly_chart_with_figure, fig)
                
                time.sleep(1)  # Update every second
                
        except Exception as e:
            logger.error(f"Error updating Plotly chart: {str(e)}")
    
    def refresh_plotly_chart(self):
        """Refresh the Plotly chart display"""
        try:
            if hasattr(self, 'plotly_widget') and self.plotly_widget:
                self.load_initial_plotly_chart()
        except Exception as e:
            logger.error(f"Error refreshing Plotly chart: {str(e)}")
    
    def refresh_plotly_chart_with_figure(self, fig):
        """Refresh Plotly chart with specific figure"""
        try:
            if hasattr(self, 'plotly_widget') and self.plotly_widget:
                html_path = self.plotly_manager.save_chart_html(fig, "main_chart")
                self.plotly_widget.load_file(html_path)
        except Exception as e:
            logger.error(f"Error refreshing Plotly chart with figure: {str(e)}")

    # def setup_matplotlib_chart(self):
    #     """Setup matplotlib chart for real-time data - LEGACY VERSION"""
    #     # This is kept for reference but commented out in favor of Plotly
    #     self.fig, self.ax = plt.subplots(figsize=(12, 6), facecolor='#2b2b2b')
    #     self.ax.set_facecolor('#2b2b2b')
    #     self.ax.tick_params(colors='white')
    #     self.ax.xaxis.label.set_color('white')
    #     self.ax.yaxis.label.set_color('white')
    #     self.ax.title.set_color('white')
    #
    #     self.canvas = FigureCanvasTkAgg(self.fig, self.chart_frame)
    #     self.canvas.get_tk_widget().pack(fill="both", expand=True)
    #
    #     # Initialize empty data
    #     self.chart_data = {'x': [], 'y': []}
    #     self.chart_line, = self.ax.plot([], [], 'cyan', linewidth=2)
    
    def setup_advanced_dashboard_tab(self):
        """Setup advanced dashboard tab with Plotly visualizations"""
        dashboard_frame = ctk.CTkScrollableFrame(self.advanced_dashboard_tab)
        dashboard_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Dashboard header
        header_frame = ctk.CTkFrame(dashboard_frame)
        header_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(header_frame, text="Advanced Analytics Dashboard",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", padx=10, pady=10)
        
        # Dashboard controls
        controls_frame = ctk.CTkFrame(header_frame)
        controls_frame.pack(side="right", padx=10, pady=5)
        
        # Theme toggle
        self.dashboard_theme_var = tk.StringVar(value=self.config['appearance']['mode'])
        theme_combo = ctk.CTkComboBox(controls_frame, variable=self.dashboard_theme_var,
                                     values=["dark", "light"], width=80)
        theme_combo.pack(side="left", padx=5)
        theme_combo.configure(command=self.update_dashboard_theme)
        
        # Refresh button
        refresh_dashboard_btn = ctk.CTkButton(
            controls_frame, text="Refresh", command=self.refresh_dashboard, width=80)
        refresh_dashboard_btn.pack(side="left", padx=5)
        
        # Main dashboard grid
        self.dashboard_grid = ctk.CTkFrame(dashboard_frame)
        self.dashboard_grid.pack(fill="both", expand=True, pady=10)
        
        # Create dashboard sections
        self.create_dashboard_sections()
    
    def create_dashboard_sections(self):
        """Create different sections of the advanced dashboard"""
        # Section 1: Gauges Row
        gauges_frame = ctk.CTkFrame(self.dashboard_grid)
        gauges_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(gauges_frame, text="Live Gauges",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)
        
        self.gauges_container = ctk.CTkFrame(gauges_frame)
        self.gauges_container.pack(fill="x", padx=10, pady=5)
        
        # Section 2: Trend Analysis
        trends_frame = ctk.CTkFrame(self.dashboard_grid)
        trends_frame.pack(fill="both", expand=True, pady=5)
        
        ctk.CTkLabel(trends_frame, text="Trend Analysis",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)
        
        self.trends_container = ctk.CTkFrame(trends_frame)
        self.trends_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Section 3: Sparklines
        sparklines_frame = ctk.CTkFrame(self.dashboard_grid)
        sparklines_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(sparklines_frame, text="Mini Charts (Sparklines)",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)
        
        self.sparklines_container = ctk.CTkFrame(sparklines_frame)
        self.sparklines_container.pack(fill="x", padx=10, pady=5)
        
        # Initialize dashboard widgets
        self.setup_dashboard_widgets()
    
    def setup_dashboard_widgets(self):
        """Setup individual dashboard widgets"""
        # Create placeholder widgets that will be populated with data
        self.dashboard_widgets_dict = {}
        
        # Gauges for key metrics
        key_metrics = ['RPM', 'SPEED', 'ENGINE_LOAD', 'COOLANT_TEMP']
        
        for i, metric in enumerate(key_metrics):
            gauge_widget = ctk.CTkFrame(self.gauges_container)
            gauge_widget.grid(row=0, column=i, padx=5, pady=5, sticky="ew")
            self.gauges_container.grid_columnconfigure(i, weight=1)
            
            # Create tkinterweb widget for gauge
            try:
                gauge_html_widget = tkinterweb.HtmlFrame(gauge_widget, messages_enabled=False)
                gauge_html_widget.pack(fill="both", expand=True, padx=2, pady=2)
                
                self.dashboard_widgets_dict[f'{metric}_gauge'] = gauge_html_widget
                
                # Load initial empty gauge
                self.load_gauge_chart(metric, gauge_html_widget)
                
            except Exception as e:
                logger.error(f"Error creating gauge widget for {metric}: {str(e)}")
                # Fallback to label
                ctk.CTkLabel(gauge_widget, text=f"{metric}\n--").pack(expand=True)
        
        # Trend analysis widget
        try:
            self.trends_widget = tkinterweb.HtmlFrame(self.trends_container, messages_enabled=False)
            self.trends_widget.pack(fill="both", expand=True, padx=5, pady=5)
            self.load_trends_chart()
        except Exception as e:
            logger.error(f"Error creating trends widget: {str(e)}")
            ctk.CTkLabel(self.trends_container, text="Trends widget error").pack(expand=True)
        
        # Sparklines
        sparkline_metrics = ['RPM', 'SPEED', 'ENGINE_LOAD', 'COOLANT_TEMP', 'INTAKE_TEMP', 'THROTTLE_POS']
        
        for i, metric in enumerate(sparkline_metrics):
            sparkline_frame = ctk.CTkFrame(self.sparklines_container)
            sparkline_frame.grid(row=i//3, column=i%3, padx=5, pady=5, sticky="ew")
            self.sparklines_container.grid_columnconfigure(i%3, weight=1)
            
            # Label for metric name
            ctk.CTkLabel(sparkline_frame, text=metric, font=ctk.CTkFont(size=10)).pack(pady=2)
            
            try:
                sparkline_widget = tkinterweb.HtmlFrame(sparkline_frame, messages_enabled=False)
                sparkline_widget.pack(fill="both", expand=True, padx=2, pady=2)
                
                self.dashboard_widgets_dict[f'{metric}_sparkline'] = sparkline_widget
                self.load_sparkline_chart(metric, sparkline_widget)
                
            except Exception as e:
                logger.error(f"Error creating sparkline widget for {metric}: {str(e)}")
                ctk.CTkLabel(sparkline_frame, text="--").pack(expand=True)
    
    def load_gauge_chart(self, metric, widget):
        """Load gauge chart for a specific metric"""
        try:
            # Get data for the metric
            pid_data = self.pid_data.get(metric, {
                'value': 0,
                'name': metric,
                'max_value': 100,
                'warning_threshold': 75,
                'critical_threshold': 90
            })
            
            fig = self.plotly_manager.create_gauge_chart(pid_data)
            html_path = self.plotly_manager.save_chart_html(fig, f'{metric}_gauge')
            widget.load_file(html_path)
            
        except Exception as e:
            logger.error(f"Error loading gauge chart for {metric}: {str(e)}")
    
    def load_trends_chart(self):
        """Load trends analysis chart"""
        try:
            # Create a combined trends chart
            fig = self.plotly_manager.create_real_time_chart("Trends Analysis", height=400)
            
            # Add sample data if available
            for pid_name, data in self.pid_data.items():
                if pid_name in ['RPM', 'SPEED', 'ENGINE_LOAD']:
                    timestamps = [datetime.datetime.now() - datetime.timedelta(minutes=i) for i in range(10, 0, -1)]
                    values = [data.get('value', 0) + (i * 0.1) for i in range(10)]
                    
                    fig.add_trace(go.Scatter(
                        x=timestamps,
                        y=values,
                        mode='lines',
                        name=pid_name,
                        line=dict(width=2)
                    ))
            
            html_path = self.plotly_manager.save_chart_html(fig, 'trends_chart')
            self.trends_widget.load_file(html_path)
            
        except Exception as e:
            logger.error(f"Error loading trends chart: {str(e)}")
    
    def load_sparkline_chart(self, metric, widget):
        """Load sparkline chart for a specific metric"""
        try:
            # Generate sample sparkline data
            timestamps = [datetime.datetime.now() - datetime.timedelta(minutes=i) for i in range(20, 0, -1)]
            values = [50 + (i * 2) + (i % 3) for i in range(20)]
            
            pid_data = {
                'timestamps': timestamps,
                'values': values,
                'name': metric
            }
            
            fig = self.plotly_manager.create_sparkline_chart(pid_data)
            html_path = self.plotly_manager.save_chart_html(fig, f'{metric}_sparkline')
            widget.load_file(html_path)
            
        except Exception as e:
            logger.error(f"Error loading sparkline chart for {metric}: {str(e)}")
    
    def update_dashboard_theme(self, theme=None):
        """Update dashboard theme"""
        try:
            if theme:
                self.plotly_manager.set_theme(theme)
                self.config['appearance']['mode'] = theme
                ctk.set_appearance_mode(theme)
                
                # Refresh all dashboard widgets
                self.refresh_dashboard()
                
        except Exception as e:
            logger.error(f"Error updating dashboard theme: {str(e)}")
    
    def refresh_dashboard(self):
        """Refresh all dashboard widgets"""
        try:
            # Refresh gauges
            for metric in ['RPM', 'SPEED', 'ENGINE_LOAD', 'COOLANT_TEMP']:
                gauge_key = f'{metric}_gauge'
                if gauge_key in self.dashboard_widgets_dict:
                    self.load_gauge_chart(metric, self.dashboard_widgets_dict[gauge_key])
            
            # Refresh trends
            if hasattr(self, 'trends_widget'):
                self.load_trends_chart()
            
            # Refresh sparklines
            for metric in ['RPM', 'SPEED', 'ENGINE_LOAD', 'COOLANT_TEMP', 'INTAKE_TEMP', 'THROTTLE_POS']:
                sparkline_key = f'{metric}_sparkline'
                if sparkline_key in self.dashboard_widgets_dict:
                    self.load_sparkline_chart(metric, self.dashboard_widgets_dict[sparkline_key])
            
            logger.info("Dashboard refreshed")
            
        except Exception as e:
            logger.error(f"Error refreshing dashboard: {str(e)}")

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

    # Legacy matplotlib methods - commented out but kept for reference
    # def start_charting(self):
    #     """Start real-time charting for selected PID - LEGACY MATPLOTLIB VERSION"""
    #     selected_pid = self.chart_pid_var.get()
    #     if not selected_pid:
    #         messagebox.showwarning(
    #             "No PID Selected", "Please select a PID to chart")
    #         return
    #
    #     if not self.is_connected:
    #         messagebox.showwarning(
    #             "Not Connected", "Please connect to OBD device first")
    #         return
    #
    #     # Initialize chart data
    #     self.chart_data = {'x': [], 'y': []}
    #     self.charting_active = True
    #
    #     # Start chart update thread
    #     self.chart_thread = threading.Thread(
    #         target=self.update_chart, daemon=True)
    #     self.chart_thread.start()
    #
    #     logger.info(f"Started charting for PID: {selected_pid}")
    #
    # def stop_charting(self):
    #     """Stop real-time charting - LEGACY MATPLOTLIB VERSION"""
    #     self.charting_active = False
    #     if hasattr(self, 'chart_thread') and self.chart_thread.is_alive():
    #         self.chart_thread.join(timeout=1)
    #
    #     logger.info("Stopped charting")
    #
    # def update_chart(self):
    #     """Update chart with real-time data - LEGACY MATPLOTLIB VERSION"""
    #     selected_pid = self.chart_pid_var.get()
    #
    #     while self.charting_active and self.is_connected:
    #         try:
    #             # Get current value for selected PID
    #             if selected_pid in self.pid_data:
    #                 current_time = time.time()
    #                 current_value = self.pid_data[selected_pid].get('value', 0)
    #
    #                 # Try to convert to float
    #                 try:
    #                     current_value = float(current_value)
    #                 except (ValueError, TypeError):
    #                     current_value = 0
    #
    #                 # Add to chart data
    #                 self.chart_data['x'].append(current_time)
    #                 self.chart_data['y'].append(current_value)
    #
    #                 # Limit data points to last 100
    #                 if len(self.chart_data['x']) > 100:
    #                     self.chart_data['x'] = self.chart_data['x'][-100:]
    #                     self.chart_data['y'] = self.chart_data['y'][-100:]
    #
    #                 # Update chart in main thread
    #                 self.root.after(0, self.refresh_chart)
    #
    #             time.sleep(0.5)  # Update every 500ms
    #
    #         except Exception as e:
    #             logger.error(f"Error updating chart: {str(e)}")
    #             break
    #
    # def refresh_chart(self):
    #     """Refresh the matplotlib chart - LEGACY VERSION"""
    #     if not hasattr(self, 'chart_line') or not self.chart_data['x']:
    #         return
    #
    #     try:
    #         # Update chart data
    #         self.chart_line.set_data(
    #             self.chart_data['x'], self.chart_data['y'])
    #
    #         # Update axes
    #         if self.chart_data['x']:
    #             self.ax.set_xlim(
    #                 min(self.chart_data['x']), max(self.chart_data['x']))
    #             self.ax.set_ylim(
    #                 min(self.chart_data['y']) - 1, max(self.chart_data['y']) + 1)
    #
    #         # Refresh canvas
    #         self.canvas.draw()
    #
    #     except Exception as e:
    #         logger.error(f"Error refreshing chart: {str(e)}")

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
            # Stop any active charting
            if hasattr(self, 'charting_active'):
                self.charting_active = False
            
            # Cleanup Plotly manager
            if hasattr(self, 'plotly_manager'):
                self.plotly_manager.cleanup()
                
            # Save configuration
            self.save_config_to_file()
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
        finally:
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

            # Update chart PID combo (legacy)
            if hasattr(self, 'chart_pid_combo'):
                self.chart_pid_combo.configure(values=self.available_pids)
                if self.available_pids:
                    self.chart_pid_combo.set(self.available_pids[0])
            
            # Update PID listbox for Plotly charts
            if hasattr(self, 'selected_pids_listbox'):
                self.selected_pids_listbox.delete(0, tk.END)
                for pid in self.available_pids:
                    self.selected_pids_listbox.insert(tk.END, pid)

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
            timestamp = datetime.datetime.now()
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

            if pid_name not in self.pid_data:
                self.pid_data[pid_name] = {
                    'name': pid_name,
                    'value': value,
                    'unit': unit,
                    'timestamp': timestamp_str,
                    'min_value': value,
                    'max_value': value,
                    'status': 'OK'
                }
            else:
                # Update existing data
                self.pid_data[pid_name]['value'] = value
                self.pid_data[pid_name]['timestamp'] = timestamp_str

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

            # Update Plotly chart data cache
            if hasattr(self, 'plotly_manager'):
                self.plotly_manager.update_chart_data("main_chart", pid_name, timestamp, value)

            # Add to log data
            self.log_data.append({
                'timestamp': timestamp_str,
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
            
            # Update Plotly theme
            if hasattr(self, 'plotly_manager'):
                self.plotly_manager.set_theme(theme)
            
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
