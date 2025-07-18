import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import obd
import serial
import time
import functools
import serial.tools.list_ports
import threading
import time
import json
import datetime
import csv
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from typing import Dict, List, Optional, Any, Callable, Union
import logging
import os
import asyncio
import bleak
from bleak import BleakClient, BleakScanner
from ve_table import VETableWindow

# Type annotation for EnhancedOBDMonitor class to help Pylance
# This lets the IDE know all methods that will be defined later in the file
# pyright: reportGeneralTypeIssues=false

# For Windows audio alerts
try:
    import winsound
except ImportError:
    winsound = None

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)


class TkCallbackManager:
    """
    Class to manage Tkinter callbacks and prevent garbage collection issues.
    Stores callbacks as instance attributes and provides methods to create and
    retrieve callbacks safely.
    """

    def __init__(self):
        self._callbacks = {}
        self._callback_counter = 0

    def create_callback(self, func, *args, **kwargs):
        """Create a callback and store it to prevent garbage collection"""
        callback_id = f"callback_{self._callback_counter}"
        self._callback_counter += 1

        # Use functools.partial to create a callable with bound arguments
        callback = functools.partial(func, *args, **kwargs)

        # Store the callback
        self._callbacks[callback_id] = callback
        return callback

    def schedule_after(self, root, delay, func, *args, **kwargs):
        """Schedule a function to run after delay milliseconds"""
        callback = self.create_callback(func, *args, **kwargs)
        return root.after(delay, callback)

    def clear_old_callbacks(self, max_callbacks=1000):
        """Clear old callbacks if we have too many (prevent memory leaks)"""
        if len(self._callbacks) > max_callbacks:
            # Keep only the most recent callbacks
            keys_to_keep = sorted(self._callbacks.keys())[-max_callbacks:]
            new_callbacks = {k: self._callbacks[k] for k in keys_to_keep}
            self._callbacks = new_callbacks


class BluetoothOBDManager:
    """Manages Bluetooth OBD connections using Bleak"""

    def __init__(self):
        self.client = None
        self.is_connected = False
        self.device_address = None
        self.characteristic_uuid = None
        self.loop = None
        self.thread = None

    async def scan_devices(self, timeout=10):
        """Scan for available Bluetooth OBD devices"""
        try:
            logger.info("Scanning for Bluetooth devices...")
            devices = await BleakScanner.discover(timeout=timeout)

            obd_devices = []
            for device in devices:
                # Look for common OBD device names
                if device.name and any(keyword in device.name.upper() for keyword in
                                       ['OBD', 'ELM', 'OBDLINK', 'VGATE', 'KONNWEI']):
                    obd_devices.append({
                        'name': device.name,
                        'address': device.address,
                        'rssi': getattr(device, 'rssi', 'N/A')
                    })
                    logger.info(
                        f"Found OBD device: {device.name} ({device.address})")

            return obd_devices

        except Exception as e:
            logger.error(f"Error scanning for devices: {str(e)}")
            return []

    async def connect_device(self, device_address, timeout=10):
        """Connect to a specific Bluetooth OBD device"""
        try:
            logger.info(f"Connecting to device: {device_address}")

            self.client = BleakClient(device_address, timeout=timeout)
            await self.client.connect()

            if self.client.is_connected:
                self.is_connected = True
                self.device_address = device_address

                # Discover services and characteristics
                # Use alternative approach to discover services
                try:
                    # Different versions of Bleak have different ways to access services
                    # Using dynamic approach to avoid type checking errors
                    services = []

                    # Get all object attributes that might be services
                    if hasattr(self.client, 'services'):
                        client_services = getattr(self.client, 'services')

                        # Handle different service collection types
                        if hasattr(client_services, 'values'):
                            # If it's a dictionary-like object
                            services = list(client_services.values())
                        elif hasattr(client_services, '__iter__'):
                            # If it's any iterable
                            services = list(client_services)
                except Exception as e:
                    logger.error(f"Error getting services: {str(e)}")
                    services = []

                # Look for common OBD characteristics
                for service in services:
                    for char in service.characteristics:
                        # Common OBD characteristic UUIDs
                        if char.uuid.lower() in ['0000fff1-0000-1000-8000-00805f9b34fb',
                                                 '0000ffe1-0000-1000-8000-00805f9b34fb']:
                            self.characteristic_uuid = char.uuid
                            logger.info(
                                f"Found OBD characteristic: {char.uuid}")
                            break
                    if self.characteristic_uuid:
                        break

                # If no specific characteristic found, use the first writable one
                if not self.characteristic_uuid:
                    for service in services:
                        for char in service.characteristics:
                            if "write" in char.properties:
                                self.characteristic_uuid = char.uuid
                                logger.info(
                                    f"Using characteristic: {char.uuid}")
                                break
                        if self.characteristic_uuid:
                            break

                logger.info(f"Successfully connected to {device_address}")
                return True
            else:
                logger.error("Failed to connect to device")
                return False

        except Exception as e:
            logger.error(f"Error connecting to device: {str(e)}")
            self.is_connected = False
            return False

    async def disconnect_device(self):
        """Disconnect from the current Bluetooth device"""
        try:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
                logger.info("Disconnected from Bluetooth device")

            self.is_connected = False
            self.client = None
            self.device_address = None
            self.characteristic_uuid = None

        except Exception as e:
            logger.error(f"Error disconnecting: {str(e)}")

    async def send_command(self, command):
        """Send OBD command via Bluetooth"""
        try:
            if not self.client or not self.client.is_connected:
                raise Exception("Not connected to device")

            if not self.characteristic_uuid:
                raise Exception("No characteristic available")

            # Convert command to bytes
            if isinstance(command, str):
                command_bytes = command.encode('utf-8')
            else:
                command_bytes = command

            # Send command
            await self.client.write_gatt_char(self.characteristic_uuid, command_bytes)

            # Read response (this might need adjustment based on device)
            response = await self.client.read_gatt_char(self.characteristic_uuid)
            return response.decode('utf-8') if response else None

        except Exception as e:
            logger.error(f"Error sending command: {str(e)}")
            return None

    def run_async_task(self, coro):
        """Run async task in a separate thread"""
        try:
            if not self.loop or self.loop.is_closed():
                self.loop = asyncio.new_event_loop()

            if not self.thread or not self.thread.is_alive():
                self.thread = threading.Thread(
                    target=self._run_loop, daemon=True)
                self.thread.start()

            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            return future.result(timeout=30)
        except Exception as e:
            logger.error(f"Error running async task: {str(e)}")
            return None

    def _run_loop(self):
        """Run the asyncio event loop in a separate thread"""
        if self.loop:
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        else:
            logger.error("Asyncio loop is not initialized")


class EnhancedOBDMonitor:
    def __init__(self):
        # Load configuration first
        self.config = self.create_default_config()
        self.load_config()

        # Set appearance
        ctk.set_appearance_mode(self.config['appearance']['mode'])
        ctk.set_default_color_theme(self.config['appearance']['theme'])

        # Initialize the callback manager for preventing Tkinter callback garbage collection
        self.callback_manager = TkCallbackManager()

        self.root = ctk.CTk()
        self.root.title("OBD Monitor Pro - Enhanced")
        self.root.geometry("1600x1000")
        self.root.minsize(1400, 900)

        # OBD connection
        self.connection = None
        self.is_connected = False
        self.monitoring = False
        self.monitor_thread = None

        # Bluetooth manager
        self.bluetooth_manager = BluetoothOBDManager()
        self.bluetooth_devices = []
        self.connection_type = "serial"  # "serial" or "bluetooth"

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
        # Set window close handler
        if hasattr(self, 'on_closing'):
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
                'timeout': 10,
                'type': 'serial'  # 'serial' or 'bluetooth'
            },
            'bluetooth': {
                'scan_timeout': 10,
                'connect_timeout': 10,
                'last_device': None
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

        # Schedule initial timer update with a proper function
        def start_timer():
            self.update_session_timer()
        self.root.after(1000, start_timer)

    def setup_enhanced_control_panel(self, parent):
        """Setup enhanced connection and control panel"""
        control_frame = ctk.CTkFrame(parent)
        control_frame.pack(fill="x", padx=5, pady=5)

        # Connection section
        conn_frame = ctk.CTkFrame(control_frame)
        conn_frame.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        ctk.CTkLabel(conn_frame, text="Connection", font=ctk.CTkFont(
            size=16, weight="bold")).pack(pady=5)

        # Connection type selection
        type_frame = ctk.CTkFrame(conn_frame)
        type_frame.pack(fill="x", padx=5, pady=2)

        ctk.CTkLabel(type_frame, text="Type:").grid(
            row=0, column=0, padx=5, sticky="w")
        self.connection_type_var = tk.StringVar(
            value=self.config.get('connection', {}).get('type', 'serial'))
        type_combo = ctk.CTkComboBox(type_frame, variable=self.connection_type_var,
                                     values=["serial", "bluetooth"], width=120,
                                     command=self.on_connection_type_change)
        type_combo.grid(row=0, column=1, padx=5)

        # Port and baudrate selection
        settings_frame = ctk.CTkFrame(conn_frame)
        settings_frame.pack(fill="x", padx=5, pady=2)

        # Port/Device selection
        ctk.CTkLabel(settings_frame, text="Port/Device:").grid(
            row=0, column=0, padx=5, sticky="w")
        self.port_var = tk.StringVar(value=self.config.get(
            'connection', {}).get('port', 'COM3'))
        self.port_combo = ctk.CTkComboBox(
            settings_frame, variable=self.port_var, width=200)
        self.port_combo.grid(row=0, column=1, padx=5)

        # Baudrate selection (only for serial)
        self.baudrate_label = ctk.CTkLabel(settings_frame, text="Baudrate:")
        self.baudrate_label.grid(row=0, column=2, padx=5, sticky="w")
        self.baudrate_var = tk.StringVar(value="38400")
        self.baudrate_combo = ctk.CTkComboBox(settings_frame, variable=self.baudrate_var,
                                              values=["9600", "38400", "115200"], width=100)
        self.baudrate_combo.grid(row=0, column=3, padx=5)

        # Refresh/Scan button
        self.refresh_btn = ctk.CTkButton(
            settings_frame, text="Refresh", command=self.refresh_connections, width=80)
        self.refresh_btn.grid(row=0, column=4, padx=5)

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

        # Initialize connections
        self.refresh_connections()

    def on_connection_type_change(self, value):
        """Handle connection type change"""
        self.connection_type = value
        self.config['connection']['type'] = value

        if value == "bluetooth":
            self.baudrate_label.grid_remove()
            self.baudrate_combo.grid_remove()
            self.refresh_btn.configure(text="Scan")
        else:
            self.baudrate_label.grid(row=0, column=2, padx=5, sticky="w")
            self.baudrate_combo.grid(row=0, column=3, padx=5)
            self.refresh_btn.configure(text="Refresh")

        self.refresh_connections()

    def refresh_connections(self):
        """Refresh the list of available connections (serial ports or Bluetooth devices)"""
        if self.connection_type_var.get() == "bluetooth":
            self.scan_bluetooth_devices()
        else:
            self.refresh_ports()

    def refresh_ports(self):
        """Refresh the list of available serial ports"""
        try:
            ports = [port.device for port in serial.tools.list_ports.comports()]

            # Always ensure COM3 is in the list for simulator purposes
            if 'COM3' not in ports:
                ports.insert(0, 'COM3')

            self.port_combo.configure(values=ports)

            # Set default port preference
            default_port = self.config.get(
                'connection', {}).get('port', 'COM3')

            if default_port in ports:
                self.port_combo.set(default_port)
            elif 'COM3' in ports:
                self.port_combo.set('COM3')
            elif ports:
                self.port_combo.set(ports[0])
            else:
                self.port_combo.set("")

        except Exception as e:
            logger.error(f"Failed to refresh ports: {str(e)}")
            # Fallback to COM3 for simulator
            self.port_combo.configure(values=['COM3'])
            self.port_combo.set('COM3')

    def scan_bluetooth_devices(self):
        """Scan for Bluetooth OBD devices"""
        def scan_thread():
            try:
                self.status_label.configure(
                    text="Scanning for Bluetooth devices...")
                self.refresh_btn.configure(
                    state="disabled", text="Scanning...")
                self.root.update()

                # Run Bluetooth scan with error handling
                try:
                    devices = self.bluetooth_manager.run_async_task(
                        self.bluetooth_manager.scan_devices(
                            timeout=self.config.get(
                                'bluetooth', {}).get('scan_timeout', 10)
                        )
                    )
                except Exception as bt_error:
                    logger.error(f"Bluetooth scan error: {str(bt_error)}")
                    devices = []

                self.bluetooth_devices = devices or []
                device_list = []

                if devices:
                    for device in devices:
                        display_name = f"{device['name']} ({device['address']})"
                        device_list.append(display_name)

                # Update UI in main thread
                self.root.after(0, self.update_bluetooth_devices, device_list)

            except Exception as e:
                logger.error(f"Error scanning Bluetooth devices: {str(e)}")
                self.root.after(0, self.bluetooth_scan_error, str(e))

        # Start scan in separate thread
        scan_thread_obj = threading.Thread(target=scan_thread, daemon=True)
        scan_thread_obj.start()

    def update_bluetooth_devices(self, device_list):
        """Update Bluetooth device list in UI"""
        try:
            self.port_combo.configure(values=device_list)

            if device_list:
                # Try to select previously used device
                last_device = self.config.get(
                    'bluetooth', {}).get('last_device')
                if last_device and last_device in device_list:
                    self.port_combo.set(last_device)
                else:
                    self.port_combo.set(device_list[0])

                self.status_label.configure(
                    text=f"Found {len(device_list)} Bluetooth device(s)")
            else:
                self.port_combo.set("")
                self.status_label.configure(
                    text="No Bluetooth OBD devices found")

            self.refresh_btn.configure(state="normal", text="Scan")

        except Exception as e:
            logger.error(f"Error updating Bluetooth devices: {str(e)}")
            self.bluetooth_scan_error(str(e))

    def bluetooth_scan_error(self, error_msg):
        """Handle Bluetooth scan error"""
        self.status_label.configure(text="Bluetooth scan failed")
        self.refresh_btn.configure(state="normal", text="Scan")
        messagebox.showerror("Bluetooth Scan Error",
                             f"Failed to scan for devices: {error_msg}")

    def connect_obd(self):
        """Connect to the OBD device (serial or Bluetooth)"""
        if self.connection_type_var.get() == "bluetooth":
            self.connect_bluetooth_obd()
        else:
            self.connect_serial_obd()

    def connect_serial_obd(self):
        """Connect to OBD device via serial port"""
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
                self.connection_type = "serial"
                self.update_connection_status(True)
                self.get_available_pids()
                self.status_label.configure(
                    text=f"Connected to OBD device on {port}")
                logger.info(f"Connected to OBD device on {port}")
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

    def connect_bluetooth_obd(self):
        """Connect to OBD device via Bluetooth"""
        def connect_thread():
            try:
                selected_device = self.port_var.get()
                if not selected_device:
                    # Use regular function to show warning
                    def show_warning():
                        messagebox.showwarning(
                            "No Device Selected", "Please select a Bluetooth device")
                    self.root.after(0, show_warning)
                    return

                # Extract device address from selection
                device_address = None
                for device in self.bluetooth_devices:
                    display_name = f"{device['name']} ({device['address']})"
                    if display_name == selected_device:
                        device_address = device['address']
                        break

                if not device_address:
                    # Use regular function to show error
                    def show_error():
                        messagebox.showerror(
                            "Device Error", "Could not find device address")
                    self.root.after(0, show_error)
                    return

                # Use regular functions for UI updates
                def update_status():
                    self.status_label.configure(
                        text=f"Connecting to {device_address}...")
                self.root.after(0, update_status)

                def disable_connect():
                    self.connect_btn.configure(state="disabled")
                self.root.after(0, disable_connect)

                # Connect to Bluetooth device
                # Get timeout from config
                timeout = self.config.get(
                    'bluetooth', {}).get('connect_timeout', 10)

                success = self.bluetooth_manager.run_async_task(
                    self.bluetooth_manager.connect_device(device_address)
                )

                if success:
                    self.is_connected = True
                    self.connection_type = "bluetooth"
                    self.connection = self.bluetooth_manager  # Use Bluetooth manager as connection

                    # Save last used device
                    self.config['bluetooth']['last_device'] = selected_device

                    # Use named functions instead of lambdas
                    def update_connection():
                        self.update_connection_status(True)
                    self.root.after(0, update_connection)

                    def get_pids():
                        self.get_available_pids()
                    self.root.after(0, get_pids)

                    def update_status():
                        self.status_label.configure(
                            text=f"Connected to Bluetooth device {device_address}")
                    self.root.after(0, update_status)

                    logger.info(
                        f"Connected to Bluetooth OBD device {device_address}")
                else:
                    # Use a separate function for failure handling
                    def handle_failure():
                        self.bluetooth_connection_failed()
                    self.root.after(0, handle_failure)

            except Exception as e:
                logger.error(f"Bluetooth connection error: {str(e)}")
                self.root.after(
                    0, lambda: self.bluetooth_connection_failed(str(e)))

        # Start connection in separate thread
        connect_thread_obj = threading.Thread(
            target=connect_thread, daemon=True)
        connect_thread_obj.start()

    def bluetooth_connection_failed(self, error_msg=None):
        """Handle Bluetooth connection failure"""
        self.is_connected = False
        self.update_connection_status(False)
        self.connect_btn.configure(state="normal")

        if error_msg:
            self.status_label.configure(
                text=f"Bluetooth connection failed: {error_msg}")
            messagebox.showerror("Bluetooth Connection Failed",
                                 f"Could not connect to Bluetooth device: {error_msg}")
        else:
            self.status_label.configure(text="Bluetooth connection failed")
            messagebox.showerror("Bluetooth Connection Failed",
                                 "Could not connect to Bluetooth device")

    def disconnect_obd(self):
        """Disconnect from the OBD device"""
        try:
            if self.connection_type == "bluetooth":
                self.disconnect_bluetooth_obd()
            else:
                self.disconnect_serial_obd()

        except Exception as e:
            logger.error(f"Failed to disconnect from OBD: {str(e)}")
            messagebox.showerror("Disconnection Error",
                                 f"Failed to disconnect from OBD: {str(e)}")

    def disconnect_serial_obd(self):
        """Disconnect from serial OBD device"""
        if self.connection:
            self.connection.close()
            self.connection = None

        self.is_connected = False
        self.update_connection_status(False)
        self.status_label.configure(text="Disconnected from OBD device")
        logger.info("Disconnected from serial OBD device")

    def disconnect_bluetooth_obd(self):
        """Disconnect from Bluetooth OBD device"""
        def disconnect_thread():
            try:
                self.bluetooth_manager.run_async_task(
                    self.bluetooth_manager.disconnect_device()
                )

                # Use named function instead of lambda
                def update_status():
                    self.status_label.configure(
                        text="Disconnected from Bluetooth device")
                self.root.after(0, update_status)

                logger.info("Disconnected from Bluetooth OBD device")

            except Exception as e:
                logger.error(f"Error disconnecting Bluetooth: {str(e)}")

        self.connection = None
        self.is_connected = False
        self.update_connection_status(False)

        # Start disconnection in separate thread
        disconnect_thread_obj = threading.Thread(
            target=disconnect_thread, daemon=True)
        disconnect_thread_obj.start()

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

        # Tables tab (for VE table and other tables)
        self.tables_tab = self.notebook.add("Tables")
        self.setup_tables_tab()

        # Settings tab
        self.settings_tab = self.notebook.add("Settings")
        self.setup_settings_tab()

    def setup_tables_tab(self):
        """Setup tables tab for VE table and other tables"""
        tables_frame = ctk.CTkFrame(self.tables_tab)
        tables_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Header
        ctk.CTkLabel(tables_frame, text="Engine Tables",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        # VE Table section
        ve_frame = ctk.CTkFrame(tables_frame)
        ve_frame.pack(fill="x", pady=10, padx=10)

        ctk.CTkLabel(ve_frame, text="Volumetric Efficiency Table",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)

        ve_desc = ctk.CTkLabel(
            ve_frame,
            text="Display and edit the Volumetric Efficiency (VE) table.\n"
                 "The VE table represents the engine's ability to fill cylinders with air.",
            wraplength=600)
        ve_desc.pack(pady=5)

        ve_button = ctk.CTkButton(
            ve_frame,
            text="Open VE Table",
            command=self.show_ve_table,
            width=150)
        ve_button.pack(pady=10)

        # Placeholder for other tables
        # You can add more tables here in the future

    def show_ve_table(self):
        """Show the Volumetric Efficiency (VE) table window"""
        try:
            # Create a function to get current PID data
            def get_pid_data():
                return self.pid_data

            # Create VE table window with data getter function
            ve_window = VETableWindow(self.root, pid_data_getter=get_pid_data)
            logger.info("Opened VE Table window")
        except Exception as e:
            logger.error(f"Error opening VE Table: {str(e)}")
            messagebox.showerror("Error", f"Failed to open VE Table: {str(e)}")

    def setup_enhanced_dashboard_tab(self):
        """Setup the enhanced digital dashboard"""
        dash_frame = ctk.CTkScrollableFrame(self.dashboard_tab)
        dash_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.dashboard_widgets = {}

        # Dashboard Controls
        controls_frame = ctk.CTkFrame(dash_frame)
        controls_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(controls_frame, text="Dashboard", font=ctk.CTkFont(
            size=16, weight="bold")).pack(side="left", padx=10)

        # Add PID to dashboard button
        add_pid_btn = ctk.CTkButton(
            controls_frame, text="Add PID to Dashboard",
            command=self.show_add_pid_dialog, width=180)
        add_pid_btn.pack(side="right", padx=10)

        # VE Table button
        ve_table_btn = ctk.CTkButton(
            controls_frame, text="VE Table",
            command=self.show_ve_table, width=100)
        ve_table_btn.pack(side="right", padx=10)

        # Alert panel
        alert_frame = ctk.CTkFrame(dash_frame)
        alert_frame.pack(fill="x", pady=5)

        active_alerts_label = ctk.CTkLabel(
            alert_frame,
            text="Active Alerts",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        active_alerts_label.pack(pady=5)
        self.alert_display = ctk.CTkTextbox(alert_frame, height=60)
        self.alert_display.pack(fill="x", padx=10, pady=5)

        # Key metrics
        metrics_frame = ctk.CTkFrame(dash_frame)
        metrics_frame.pack(fill="both", expand=True, pady=10)

        self.create_gauge_grid(metrics_frame)

    def create_gauge_grid(self, parent):
        """Create responsive gauge grid"""
        # Container for all gauge rows
        self.gauges_container = parent

        # Save the default gauges to create initially
        self.default_gauges = [
            {"title": "RPM", "key": "rpm", "min_val": 0,
                "max_val": 8000, "unit": "RPM", "color": "#FF6B6B"},
            {"title": "Speed", "key": "speed", "min_val": 0,
                "max_val": 200, "unit": "km/h", "color": "#4ECDC4"},
            {"title": "Engine Load", "key": "engine_load", "min_val": 0,
                "max_val": 100, "unit": "%", "color": "#45B7D1"}
        ]

        # Create the initial row
        self.current_row = 0
        self.current_col = 0
        self.max_cols = 3
        self.create_gauge_row()

        # Add default gauges
        for gauge in self.default_gauges:
            self.add_gauge_to_dashboard(**gauge)

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
            ("Throttle Position", "throttle_pos", 90, 100),
            ("Mass Air Flow", "maf", 25, 30),
            ("Manifold Pressure", "map", 100, 110),
            ("Timing Advance", "timing_advance", 22, 25),
            ("Lambda1", "lambda1", 1.1, 1.15)
        ]

        if not self.is_connected:
            messagebox.showwarning(
                "Not Connected", "Please connect to an OBD device first.")
            return

    def clear_dtcs(self):
        """Clear Diagnostic Trouble Codes"""
        if not self.is_connected:
            messagebox.showwarning(
                "Not Connected", "Please connect to an OBD device first.")
            return
        try:
            if self.connection_type == "bluetooth":
                # For Bluetooth, send clear DTC command directly
                response = self.bluetooth_manager.run_async_task(
                    self.bluetooth_manager.send_command("04\r\n")
                )
                if response:
                    messagebox.showinfo(
                        "Clear DTCs", "DTCs cleared successfully.")
                else:
                    messagebox.showinfo(
                        "Clear DTCs", "No response from OBD device.")
            else:
                # For serial connection, use OBD library
                if not self.connection:
                    messagebox.showinfo(
                        "Clear DTCs", "No OBD connection available.")
                    return

                try:
                    # Create a custom command for clearing DTCs (Mode 04)
                    clear_dtc_cmd = obd.OBDCommand(
                        "CLEAR_DTC", "Clear DTCs", b"04", 0, lambda _: None)
                    response = self.connection.query(clear_dtc_cmd)

                    if response and hasattr(response, 'is_null') and response.is_null():
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

        # Connection settings
        connection_frame = ctk.CTkFrame(settings_frame)
        connection_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(connection_frame, text="Connection Settings",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)

        # Timeout setting
        timeout_frame = ctk.CTkFrame(connection_frame)
        timeout_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(timeout_frame, text="Connection Timeout (s):").pack(
            side="left", padx=5)
        self.timeout_var = tk.StringVar(
            value=str(self.config['connection'].get('timeout', 10)))
        timeout_entry = ctk.CTkEntry(
            timeout_frame, textvariable=self.timeout_var, width=80)
        timeout_entry.pack(side="left", padx=5)

        # Bluetooth settings
        bluetooth_frame = ctk.CTkFrame(connection_frame)
        bluetooth_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(bluetooth_frame, text="Bluetooth Scan Timeout (s):").pack(
            side="left", padx=5)
        self.bt_scan_timeout_var = tk.StringVar(
            value=str(self.config.get('bluetooth', {}).get('scan_timeout', 10)))
        bt_scan_entry = ctk.CTkEntry(
            bluetooth_frame, textvariable=self.bt_scan_timeout_var, width=80)
        bt_scan_entry.pack(side="left", padx=5)

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

        # Save settings button
        save_settings_btn = ctk.CTkButton(
            settings_frame, text="Save Settings", command=self.save_settings, width=120)
        save_settings_btn.pack(pady=20)

    def save_settings(self):
        """Save current settings to configuration"""
        try:
            # Update configuration with current values
            self.config['connection']['timeout'] = int(self.timeout_var.get())
            self.config['bluetooth']['scan_timeout'] = int(
                self.bt_scan_timeout_var.get())
            self.config['monitoring']['max_log_entries'] = int(
                self.max_logs_var.get())

            # Save to file
            self.save_config_to_file()

            messagebox.showinfo(
                "Settings Saved", "Settings have been saved successfully.")
            logger.info("Settings saved")

        except ValueError as e:
            messagebox.showerror(
                "Invalid Value", "Please enter valid numeric values.")
        except Exception as e:
            logger.error(f"Error saving settings: {str(e)}")
            messagebox.showerror(
                "Save Error", f"Failed to save settings: {str(e)}")

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
            if self.connection_type == "bluetooth":
                # For Bluetooth, send DTC query command directly
                response = self.bluetooth_manager.run_async_task(
                    self.bluetooth_manager.send_command("03\r\n")
                )

                if response:
                    # Parse DTC response (simplified)
                    self.dtc_data = [
                        response.strip()] if response.strip() else []
                    dtc_text = f"Bluetooth DTC Response:\n{response}" if response else "No DTCs found"
                else:
                    self.dtc_data = []
                    dtc_text = "No response from Bluetooth OBD device"
            else:
                # For serial connection, use OBD library
                try:
                    # Create a custom command for reading DTCs (Mode 03)
                    get_dtc_cmd = obd.OBDCommand(
                        "GET_DTC", "Get DTCs", b"03", 0, lambda _: None)
                    dtc_response = self.connection.query(get_dtc_cmd)

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
            # Stop monitoring
            if self.monitoring:
                self.stop_monitoring()

            # Disconnect from device
            if self.is_connected:
                self.disconnect_obd()

            # Stop charting
            if hasattr(self, 'charting_active'):
                self.charting_active = False

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

            # Update log stats
            if hasattr(self, 'log_stats_label'):
                self.log_stats_label.configure(
                    text=f"Log entries: {len(self.log_data)} | Session time: {time_str}")

            # Schedule next update using callback manager
            self.callback_manager.schedule_after(
                self.root, 1000, self.update_session_timer)

            # Clean up old callbacks occasionally
            if self.callback_manager._callback_counter % 100 == 0:
                self.callback_manager.clear_old_callbacks()
        except Exception as e:
            logger.error(f"Error updating session timer: {str(e)}")

    def update_connection_status(self, connected):
        """Update connection status in UI"""
        try:
            if connected:
                conn_text = f"Connected ({self.connection_type.title()})"
                self.connection_status.configure(
                    text=conn_text, text_color="green")
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

            if self.connection_type == "bluetooth":
                # For Bluetooth, use a predefined list of common PIDs
                self.available_pids = [
                    'RPM', 'SPEED', 'ENGINE_LOAD', 'COOLANT_TEMP',
                    'INTAKE_TEMP', 'THROTTLE_POS', 'FUEL_LEVEL', 'BAROMETRIC_PRESSURE',
                    'MAF', 'MAP', 'TIMING_ADVANCE', 'TPS', 'LAMBDA1', 'LAMBDA2',
                    'AFR', 'O2_BANK1', 'O2_BANK2', 'IAT', 'ECT', 'ENGINE_SPEED',
                    'IAC', 'VE', 'IDLE_SPEED'
                ]
            else:
                # For serial connection, get supported PIDs from OBD library
                try:
                    for cmd in obd.commands:
                        if cmd and hasattr(cmd, 'supported') and cmd.supported:
                            if hasattr(cmd, 'name'):
                                self.available_pids.append(cmd.name)
                except Exception as e:
                    logger.warning(f"Could not enumerate OBD commands: {e}")
                    # Add some common PIDs manually
                    self.available_pids = [
                        'RPM', 'SPEED', 'ENGINE_LOAD', 'COOLANT_TEMP',
                        'INTAKE_TEMP', 'THROTTLE_POS'
                    ]

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
                if self.connection_type == "bluetooth":
                    self.monitor_bluetooth_pids()
                else:
                    self.monitor_serial_pids()

                # Update dashboard and PIDs display using callback manager
                self.callback_manager.schedule_after(
                    self.root, 0, self.update_dashboard)
                self.callback_manager.schedule_after(
                    self.root, 0, self.update_pids_display)

                # Sleep based on update interval
                interval = int(self.interval_var.get()) / 1000.0
                time.sleep(interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                break

    def monitor_bluetooth_pids(self):
        """Monitor PIDs via Bluetooth connection"""
        try:
            # Simulate PID data for Bluetooth (in real implementation, send actual OBD commands)
            import random

            # Common OBD PIDs and their commands
            pid_commands = {
                'RPM': '010C\r\n',
                'SPEED': '010D\r\n',
                'ENGINE_LOAD': '0104\r\n',
                'COOLANT_TEMP': '0105\r\n',
                'INTAKE_TEMP': '010F\r\n',
                'THROTTLE_POS': '0111\r\n',
                'MAF': '0110\r\n',                   # Mass Air Flow
                'MAP': '010B\r\n',                   # Manifold Absolute Pressure
                'TIMING_ADVANCE': '010E\r\n',        # Timing Advance
                'TPS': '0111\r\n',                   # Throttle Position Sensor
                # O2 Sensor Lambda (Bank 1)
                'LAMBDA1': '0124\r\n',
                # O2 Sensor Lambda (Bank 2)
                'LAMBDA2': '0125\r\n',
                'AFR': '0134\r\n',                   # Air-Fuel Ratio
                'O2_BANK1': '0114\r\n',              # O2 Sensor (Bank 1)
                'O2_BANK2': '0115\r\n',              # O2 Sensor (Bank 2)
                'IAT': '010F\r\n',                   # Intake Air Temperature
                'ECT': '0105\r\n',                   # Engine Coolant Temperature
                # Engine Speed (same as RPM)
                'ENGINE_SPEED': '010C\r\n',
                'IAC': '0103\r\n',                   # Idle Air Control
                # Volumetric Efficiency (similar to Engine Load)
                'VE': '0104\r\n',
                # Idle Speed (RPM when vehicle idle)
                'IDLE_SPEED': '010C\r\n'
            }

            for pid_name, command in pid_commands.items():
                if not self.monitoring:
                    break

                try:
                    # Send command via Bluetooth
                    response = self.bluetooth_manager.run_async_task(
                        self.bluetooth_manager.send_command(command)
                    )

                    if response:
                        # Parse response (simplified - in real implementation, parse actual OBD response)
                        # For now, generate simulated values
                        if pid_name == 'RPM' or pid_name == 'ENGINE_SPEED':
                            value = random.randint(800, 3000)
                            unit = 'rpm'
                        elif pid_name == 'IDLE_SPEED':
                            value = random.randint(750, 950)
                            unit = 'rpm'
                        elif pid_name == 'SPEED':
                            value = random.randint(0, 120)
                            unit = 'km/h'
                        elif pid_name == 'ENGINE_LOAD' or pid_name == 'VE':
                            value = random.randint(20, 80)
                            unit = '%'
                        elif pid_name == 'COOLANT_TEMP' or pid_name == 'ECT':
                            value = random.randint(80, 95)
                            unit = '°C'
                        elif pid_name == 'INTAKE_TEMP' or pid_name == 'IAT':
                            value = random.randint(20, 60)
                            unit = '°C'
                        elif pid_name == 'THROTTLE_POS' or pid_name == 'TPS':
                            value = random.randint(0, 100)
                            unit = '%'
                        elif pid_name == 'MAF':
                            value = random.randint(5, 30)
                            unit = 'g/s'
                        elif pid_name == 'MAP':
                            value = random.randint(30, 110)
                            unit = 'kPa'
                        elif pid_name == 'TIMING_ADVANCE':
                            value = random.randint(5, 25)
                            unit = '°'
                        elif pid_name == 'LAMBDA1' or pid_name == 'LAMBDA2':
                            value = round(random.uniform(0.85, 1.15), 2)
                            unit = 'λ'
                        elif pid_name == 'AFR':
                            value = round(random.uniform(12.5, 16.0), 1)
                            unit = ':1'
                        elif pid_name == 'O2_BANK1' or pid_name == 'O2_BANK2':
                            value = round(random.uniform(0.1, 0.9), 2)
                            unit = 'V'
                        elif pid_name == 'IAC':
                            value = random.randint(20, 50)
                            unit = '%'
                        else:
                            value = 0
                            unit = ''

                        self.update_pid_data(pid_name, value, unit)

                except Exception as e:
                    logger.error(
                        f"Error querying Bluetooth PID {pid_name}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in Bluetooth monitoring: {str(e)}")

    def monitor_serial_pids(self):
        """Monitor PIDs via serial connection"""
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

                # Additional PIDs
                maf_cmd = getattr(obd.commands, 'MAF', None)
                map_cmd = getattr(obd.commands, 'INTAKE_PRESSURE', None)  # MAP
                timing_cmd = getattr(obd.commands, 'TIMING_ADVANCE', None)
                o2_b1_cmd = getattr(obd.commands, 'O2_B1S1',
                                    None)  # O2 sensor bank 1
                o2_b2_cmd = getattr(obd.commands, 'O2_B2S1',
                                    None)  # O2 sensor bank 2
                lambda1_cmd = getattr(
                    obd.commands, 'COMMANDED_EQUIV_RATIO', None)  # Lambda
                iat_cmd = getattr(obd.commands, 'INTAKE_TEMP', None)
                ect_cmd = getattr(obd.commands, 'COOLANT_TEMP', None)
                # Idle speed is RPM when stationary
                idle_cmd = getattr(obd.commands, 'RPM', None)

                # Short and long fuel trims for AFR calculations
                short_ft_cmd = getattr(obd.commands, 'SHORT_FUEL_TRIM_1', None)
                long_ft_cmd = getattr(obd.commands, 'LONG_FUEL_TRIM_1', None)

                # Add valid commands to the list
                available_cmds = [
                    rpm_cmd, speed_cmd, load_cmd, coolant_cmd, intake_cmd, throttle_cmd,
                    maf_cmd, map_cmd, timing_cmd, o2_b1_cmd, o2_b2_cmd, lambda1_cmd,
                    iat_cmd, ect_cmd, idle_cmd, short_ft_cmd, long_ft_cmd
                ]

                for cmd in available_cmds:
                    if cmd is not None:
                        common_pids.append(cmd)

            except AttributeError:
                # If specific commands are not available, try alternative approach
                logger.warning(
                    "Some OBD commands not available in this version")
                # Use a more generic approach
                try:
                    for cmd in obd.commands:
                        if cmd and hasattr(cmd, 'name') and cmd.name in [
                            'RPM', 'SPEED', 'ENGINE_LOAD', 'COOLANT_TEMP', 'INTAKE_TEMP',
                            'THROTTLE_POS', 'MAF', 'MAP', 'TIMING_ADVANCE', 'O2_B1S1', 'O2_B2S1',
                            'SHORT_FUEL_TRIM_1', 'LONG_FUEL_TRIM_1', 'COMMANDED_EQUIV_RATIO'
                        ]:
                            common_pids.append(cmd)
                except:
                    # If all else fails, skip this iteration
                    return

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

        except Exception as e:
            logger.error(f"Error in serial monitoring: {str(e)}")

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

            # Check for alerts
            self.check_alerts(pid_name, value)

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

            # Auto-save if enabled
            if self.auto_save_var.get() and len(self.log_data) % 100 == 0:
                self.auto_save_logs()

        except Exception as e:
            logger.error(f"Error updating PID data: {str(e)}")

    def check_alerts(self, pid_name, value):
        """Check if PID value triggers any alerts"""
        try:
            if not isinstance(value, (int, float)):
                return

            # Map PID names to threshold keys
            threshold_map = {
                'RPM': 'rpm',
                'ENGINE_SPEED': 'rpm',
                'SPEED': 'speed',
                'ENGINE_LOAD': 'engine_load',
                'VE': 'engine_load',
                'COOLANT_TEMP': 'coolant_temp',
                'ECT': 'ect',
                'INTAKE_TEMP': 'intake_temp',
                'IAT': 'intake_temp',
                'THROTTLE_POS': 'throttle_pos',
                'TPS': 'throttle_pos',
                'MAF': 'maf',
                'MAP': 'map',
                'INTAKE_PRESSURE': 'map',
                'TIMING_ADVANCE': 'timing_advance',
                'LAMBDA1': 'lambda1',
                'LAMBDA2': 'lambda2',
                'AFR': 'afr',
                'COMMANDED_EQUIV_RATIO': 'lambda1',
                'O2_BANK1': 'o2_bank1',
                'O2_B1S1': 'o2_bank1',
                'O2_BANK2': 'o2_bank2',
                'O2_B2S1': 'o2_bank2',
                'IDLE_SPEED': 'idle_speed'
            }

            threshold_key = threshold_map.get(pid_name)
            if not threshold_key or threshold_key not in self.threshold_widgets:
                return

            try:
                warning_threshold = float(
                    self.threshold_widgets[threshold_key]['warning'].get())
                critical_threshold = float(
                    self.threshold_widgets[threshold_key]['critical'].get())
            except (ValueError, KeyError):
                return

            alert_level = None
            if value >= critical_threshold:
                alert_level = "CRITICAL"
            elif value >= warning_threshold:
                alert_level = "WARNING"

            if alert_level:
                alert_msg = f"{alert_level}: {pid_name} = {value}"

                # Add to active alerts if not already present
                if alert_msg not in self.active_alerts:
                    self.active_alerts.append(alert_msg)

                    # Update alert display using callback manager
                    self.callback_manager.schedule_after(
                        self.root, 0, self.update_alert_display)

                    # Trigger audio alert if enabled
                    if self.audio_alerts_var.get():
                        self.trigger_audio_alert(alert_level)

                    logger.warning(f"Alert triggered: {alert_msg}")
            else:
                # Remove from active alerts if value is back to normal
                alerts_to_remove = [
                    alert for alert in self.active_alerts if pid_name in alert]
                for alert in alerts_to_remove:
                    self.active_alerts.remove(alert)
                    # Update alert display using callback manager
                    self.callback_manager.schedule_after(
                        self.root, 0, self.update_alert_display)

        except Exception as e:
            logger.error(f"Error checking alerts: {str(e)}")

    def update_alert_display(self):
        """Update the alert display in the dashboard"""
        try:
            if hasattr(self, 'alert_display'):
                self.alert_display.delete("1.0", tk.END)
                if self.active_alerts:
                    # Show last 5 alerts
                    alert_text = "\n".join(self.active_alerts[-5:])
                    self.alert_display.insert("1.0", alert_text)
                else:
                    self.alert_display.insert("1.0", "No active alerts")

            if hasattr(self, 'active_alerts_text'):
                self.active_alerts_text.delete("1.0", tk.END)
                if self.active_alerts:
                    alert_text = "\n".join(self.active_alerts)
                    self.active_alerts_text.insert("1.0", alert_text)
                else:
                    self.active_alerts_text.insert("1.0", "No active alerts")

        except Exception as e:
            logger.error(f"Error updating alert display: {str(e)}")

    def trigger_audio_alert(self, level):
        """Trigger audio alert based on level"""
        try:
            if winsound:
                if level == "CRITICAL":
                    # High-pitched beep for critical
                    winsound.Beep(1000, 500)
                elif level == "WARNING":
                    # Lower-pitched beep for warning
                    winsound.Beep(800, 300)
        except Exception as e:
            logger.error(f"Error triggering audio alert: {str(e)}")

    def auto_save_logs(self):
        """Auto-save logs to file"""
        try:
            if not self.log_data:
                return

            log_dir = self.config.get('monitoring', {}).get(
                'log_directory', 'logs')
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(log_dir, f"auto_save_{timestamp}.csv")

            with open(filename, 'w', newline='') as csvfile:
                fieldnames = ['timestamp', 'pid', 'name', 'value', 'unit']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for entry in self.log_data:
                    writer.writerow(entry)

            logger.info(f"Auto-saved logs to {filename}")

        except Exception as e:
            logger.error(f"Error auto-saving logs: {str(e)}")

    def update_dashboard(self):
        """Update dashboard widgets"""
        try:
            for key, widget_data in self.dashboard_widgets.items():
                # Map dashboard keys to PID names
                pid_map = {
                    'rpm': 'RPM',
                    'speed': 'SPEED',
                    'engine_load': 'ENGINE_LOAD'
                }

                pid_name = pid_map.get(key, key.upper())

                if pid_name in self.pid_data:
                    value = self.pid_data[pid_name]['value']

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
                    f.write(
                        f"Connection Type: {self.connection_type.title()}\n")
                    f.write(f"Total Entries: {len(self.log_data)}\n")
                    f.write(
                        f"Session Duration: {self.session_label.cget('text')}\n\n")

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

    def show_add_pid_dialog(self):
        """Show dialog to add PID to dashboard"""
        try:
            # Create a popup dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Add PID to Dashboard")
            dialog.geometry("400x400")
            dialog.resizable(False, False)
            dialog.transient(self.root)
            dialog.grab_set()

            # Make dialog appear in center of parent window
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (400 // 2)
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (400 // 2)
            dialog.geometry(f"+{x}+{y}")

            # Create frame
            main_frame = ctk.CTkFrame(dialog)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)

            # Instructions
            ctk.CTkLabel(main_frame, text="Select a PID to add to dashboard",
                         font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)

            # Create PID selection listbox
            pid_frame = ctk.CTkFrame(main_frame)
            pid_frame.pack(fill="both", expand=True, padx=10, pady=10)

            # Search field
            search_frame = ctk.CTkFrame(pid_frame)
            search_frame.pack(fill="x", padx=5, pady=5)

            ctk.CTkLabel(search_frame, text="Search:").pack(
                side="left", padx=5)
            search_var = tk.StringVar()
            search_entry = ctk.CTkEntry(
                search_frame, textvariable=search_var, width=200)
            search_entry.pack(side="left", padx=5, fill="x", expand=True)

            # PID listbox
            pids_frame = ctk.CTkFrame(pid_frame)
            pids_frame.pack(fill="both", expand=True, padx=5, pady=5)

            # Use CTkScrollableFrame for the PID list
            scroll_frame = ctk.CTkScrollableFrame(pids_frame, height=200)
            scroll_frame.pack(fill="both", expand=True)

            # Get sorted list of available PIDs
            available_pids = sorted(list(self.pid_data.keys()))

            # Create PID buttons
            self.pid_buttons = []
            self.selected_pid = None

            def select_pid(pid_name):
                self.selected_pid = pid_name
                for btn, pid in self.pid_buttons:
                    if pid == pid_name:
                        btn.configure(fg_color=("gray70", "gray30"))
                    else:
                        btn.configure(fg_color=("gray80", "gray25"))

            def filter_pids(*args):
                search_term = search_var.get().lower()
                # Clear existing buttons
                for btn, _ in self.pid_buttons:
                    btn.destroy()
                self.pid_buttons = []

                # Create filtered buttons
                for pid_name in available_pids:
                    if search_term in pid_name.lower():
                        btn = ctk.CTkButton(
                            scroll_frame,
                            text=f"{pid_name} ({self.pid_data[pid_name].get('value', '--')} {self.pid_data[pid_name].get('unit', '')})",
                            command=lambda p=pid_name: select_pid(p),
                            fg_color=("gray80", "gray25")
                        )
                        btn.pack(fill="x", padx=5, pady=2)
                        self.pid_buttons.append((btn, pid_name))

            # Populate initial PID list
            filter_pids()

            # Bind search field
            search_var.trace_add("write", filter_pids)

            # Gauge configuration frame
            config_frame = ctk.CTkFrame(main_frame)
            config_frame.pack(fill="x", padx=10, pady=10)

            # Min/max values
            range_frame = ctk.CTkFrame(config_frame)
            range_frame.pack(fill="x", pady=5)

            ctk.CTkLabel(range_frame, text="Min Value:").pack(
                side="left", padx=5)
            min_var = tk.StringVar(value="0")
            min_entry = ctk.CTkEntry(
                range_frame, textvariable=min_var, width=80)
            min_entry.pack(side="left", padx=5)

            ctk.CTkLabel(range_frame, text="Max Value:").pack(
                side="left", padx=5)
            max_var = tk.StringVar(value="100")
            max_entry = ctk.CTkEntry(
                range_frame, textvariable=max_var, width=80)
            max_entry.pack(side="left", padx=5)

            # Color selection
            color_frame = ctk.CTkFrame(config_frame)
            color_frame.pack(fill="x", pady=5)

            ctk.CTkLabel(color_frame, text="Gauge Color:").pack(
                side="left", padx=5)
            color_var = tk.StringVar(value="blue")
            color_combo = ctk.CTkComboBox(color_frame, variable=color_var,
                                          values=["blue", "green", "red", "orange", "purple"])
            color_combo.pack(side="left", padx=5)

            # Buttons
            button_frame = ctk.CTkFrame(main_frame)
            button_frame.pack(fill="x", pady=10)

            def on_cancel():
                dialog.destroy()

            def on_add():
                if not self.selected_pid:
                    messagebox.showwarning(
                        "No Selection", "Please select a PID to add")
                    return

                try:
                    min_val = float(min_var.get())
                    max_val = float(max_var.get())

                    if min_val >= max_val:
                        messagebox.showwarning(
                            "Invalid Range", "Min value must be less than max value")
                        return

                    # Add gauge to dashboard
                    self.add_gauge_to_dashboard(
                        title=self.selected_pid,
                        key=self.selected_pid,
                        min_val=min_val,
                        max_val=max_val,
                        unit=self.pid_data[self.selected_pid].get('unit', ''),
                        color=color_var.get()
                    )
                    dialog.destroy()

                except ValueError:
                    messagebox.showwarning(
                        "Invalid Input", "Min and max values must be numbers")

            cancel_btn = ctk.CTkButton(
                button_frame, text="Cancel", command=on_cancel, width=100)
            cancel_btn.pack(side="right", padx=10)

            add_btn = ctk.CTkButton(
                button_frame, text="Add Gauge", command=on_add, width=100)
            add_btn.pack(side="right", padx=10)

        except Exception as e:
            logger.error(f"Error showing add PID dialog: {str(e)}")
            messagebox.showerror(
                "Dialog Error", f"Failed to show dialog: {str(e)}")

    def create_gauge_row(self):
        """Create a new row frame for gauges"""
        try:
            # Create a new row frame
            row_frame = ctk.CTkFrame(self.gauges_container)
            row_frame.pack(fill="x", pady=5)

            # Store in row frames list
            if not hasattr(self, 'row_frames'):
                self.row_frames = []
            self.row_frames.append(row_frame)

            return row_frame

        except Exception as e:
            logger.error(f"Error creating gauge row: {str(e)}")
            return None

    def add_gauge_to_dashboard(self, title, key, min_val, max_val, unit, color):
        """Add a gauge to the dashboard"""
        try:
            # Check if we need a new row
            if self.current_col >= self.max_cols:
                self.current_row += 1
                self.current_col = 0
                self.create_gauge_row()

            # Get current row frame
            if self.current_row < len(self.row_frames):
                row_frame = self.row_frames[self.current_row]
            else:
                row_frame = self.create_gauge_row()

            # Create gauge widget
            gauge = self.create_enhanced_gauge_widget(
                row_frame, title, key, min_val, max_val, unit,
                self.current_row, self.current_col, color
            )

            # Update column position
            self.current_col += 1

            # Update config to save dashboard layout
            if 'dashboard' not in self.config:
                self.config['dashboard'] = {'gauges': []}

            # Make sure gauges is a list before appending
            if not isinstance(self.config['dashboard']['gauges'], list):
                self.config['dashboard']['gauges'] = []

            self.config['dashboard']['gauges'].append({
                'title': title,
                'key': key,
                'min_val': min_val,
                'max_val': max_val,
                'unit': unit,
                'color': color
            })

            self.save_config_to_file()
            return gauge

        except Exception as e:
            logger.error(f"Error adding gauge to dashboard: {str(e)}")
            return None

    def run(self):
        """Run the application"""
        try:
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Application error: {str(e)}")
            messagebox.showerror("Application Error",
                                 f"An error occurred: {str(e)}")


class BluetoothOBDManager2:
    """Manager for Bluetooth OBD connections using bleak (updated version)"""

    def __init__(self):
        self.device = None
        self.client = None
        self.is_connected = False
        self.characteristic_uuid = None

    async def scan_devices(self, timeout=10):
        """Scan for available Bluetooth OBD devices"""
        try:
            devices = await bleak.BleakScanner.discover(timeout=timeout)
            obd_devices = []

            for device in devices:
                # Look for OBD-related device names
                if device.name and any(keyword in device.name.lower()
                                       for keyword in ['obd', 'elm', 'obdlink', 'vgate']):
                    obd_devices.append({
                        'name': device.name,
                        'address': device.address,
                        'signal_strength': getattr(device, 'rssi', 'N/A')
                    })

            return obd_devices

        except Exception as e:
            logger.error(f"Error scanning for Bluetooth devices: {str(e)}")
            return []

    async def connect_device(self, address):
        """Connect to a Bluetooth OBD device"""
        try:
            self.client = bleak.BleakClient(address)
            await self.client.connect()

            if self.client.is_connected:
                # Discover services and characteristics
                services = []

                # Use alternative approach to discover services
                try:
                    # Different versions of Bleak have different ways to access services
                    # Using dynamic approach to avoid type checking errors
                    services = []

                    # Get all object attributes that might be services
                    if hasattr(self.client, 'services'):
                        client_services = getattr(self.client, 'services')

                        # Handle different service collection types
                        if hasattr(client_services, 'values'):
                            # If it's a dictionary-like object
                            services = list(client_services.values())
                        elif hasattr(client_services, '__iter__'):
                            # If it's any iterable
                            services = list(client_services)
                except Exception as e:
                    logger.error(f"Error getting services: {str(e)}")
                    services = []

                # Look for UART service or similar
                for service in services:
                    for char in service.characteristics:
                        if "write" in char.properties:
                            self.characteristic_uuid = char.uuid
                            break
                    if self.characteristic_uuid:
                        break

                if self.characteristic_uuid:
                    self.is_connected = True
                    logger.info(
                        f"Connected to Bluetooth OBD device: {address}")
                    return True
                else:
                    await self.client.disconnect()
                    logger.error("No suitable characteristic found")
                    return False

            return False

        except Exception as e:
            logger.error(f"Error connecting to Bluetooth device: {str(e)}")
            return False

    async def disconnect_device(self):
        """Disconnect from Bluetooth OBD device"""
        try:
            if self.client and self.client.is_connected:
                await self.client.disconnect()

            self.is_connected = False
            self.client = None
            self.characteristic_uuid = None
            logger.info("Disconnected from Bluetooth OBD device")

        except Exception as e:
            logger.error(
                f"Error disconnecting from Bluetooth device: {str(e)}")

    async def send_command(self, command):
        """Send OBD command via Bluetooth"""
        try:
            if not self.is_connected or not self.client:
                return None

            # Check if characteristic UUID is available
            if not self.characteristic_uuid:
                logger.error("No characteristic UUID available")
                return None

            # Send command
            try:
                await self.client.write_gatt_char(
                    self.characteristic_uuid,
                    command.encode()
                )
            except ValueError as e:
                logger.error(f"Invalid characteristic UUID: {str(e)}")
                return None

            # Wait for response (simplified - in real implementation, use notifications)
            await asyncio.sleep(0.1)

            # For now, return a placeholder response
            # In real implementation, you'd read the response from the device
            return "41 0C 1A F8"  # Example RPM response

        except Exception as e:
            logger.error(f"Error sending Bluetooth command: {str(e)}")
            return None

    def run_async_task(self, coro):
        """Run an async task in a thread-safe manner"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(coro)
            return result
        except Exception as e:
            logger.error(f"Error running async task: {str(e)}")
            return None
        finally:
            if loop and hasattr(loop, 'close'):
                loop.close()


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
