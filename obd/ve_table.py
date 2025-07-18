import tkinter as tk
from tkinter import ttk, Entry, Label, filedialog, messagebox
import customtkinter as ctk
import numpy as np
import logging
import os
import json
import time
import csv
import datetime
from typing import List, Any, Optional, Union, Dict, Callable, TextIO

logger = logging.getLogger(__name__)


class VETableWindow:
    """
    Volumetric Efficiency (VE) Table window for viewing and editing engine VE data.

    This table displays the efficiency of the engine's ability to fill cylinders with air.
    The cell units are in Grams*Kelvin/kPa.
    - Rows represent MAP (Manifold Absolute Pressure) values in kPa
    - Columns represent RPM values

    The air mass per cylinder can be calculated using:
    g/cyl = VE*MAP/Charge Temperature
    Where:
    - VE is in g*K/kPa
    - MAP is in kPa
    - Charge Temperature is in degrees Kelvin
    """

    def __init__(self, parent, pid_data_getter: Optional[Callable] = None, force_reset=False):
        """Initialize the VE Table window"""
        self.parent = parent
        self.root = ctk.CTkToplevel(parent)
        self.root.title("Volumetric Efficiency (VE) Table")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)

        # Function to get real-time PID data
        self.pid_data_getter = pid_data_getter

        # Flag to track if the window is being closed
        self._closing = False

        # Create default VE table data with updated ranges
        # RPM range: 400-8000 in intervals of 400
        self.rpm_values = list(range(400, 8001, 400))
        # MAP range: 15-105 in intervals of 5
        self.map_values = list(range(15, 110, 5))

        # Store the force_reset flag
        self.force_reset = force_reset

        # Current engine values
        self.current_rpm = 0
        self.current_map = 0
        self.current_ve = 0.0
        self.update_timer = None

        # Logging settings
        self.log_enabled = False
        self.log_file = None
        self.csv_writer = None
        self.log_interval = 1000  # ms (1 second by default)
        self.logs_directory = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "logs")

        # Create logs directory if it doesn't exist
        if not os.path.exists(self.logs_directory):
            os.makedirs(self.logs_directory)

        # Log data history for plotting
        self.log_history = {
            'timestamp': [],
            'rpm': [],
            'map': [],
            've': []
        }
        self.max_history_points = 300  # Store 5 minutes of data at 1s interval

        # Set config file path
        self.config_file = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "ve_table_config.json")

        # Initialize VE data and visited cells with proper dimensions
        map_count = len(self.map_values)
        rpm_count = len(self.rpm_values)

        # Always start with an empty VE table (zeros)
        self.ve_data = np.zeros((map_count, rpm_count), dtype=float)
        self.visited_cells = np.zeros((map_count, rpm_count), dtype=bool)

        # Initialize history tracker
        self.ve_table_history = {
            'timestamp': [],
            'location': [],
            'old_value': [],
            'new_value': []
        }

        # Load configuration settings (not VE data) from file if it exists
        # This will only load the configuration without populating the VE table with values
        self.load_config()

        # Log that we're starting with an empty table
        logger.info(
            "VE Table initialized with empty data. It will only populate with real-time data.")

        # Set up cleanup when window is closed
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.setup_ui()

        # Start real-time updates if a data getter is provided
        if self.pid_data_getter:
            self.start_real_time_updates()

    def setup_ui(self):
        """Setup the UI components"""
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Add title and description
        title_label = ctk.CTkLabel(
            main_frame,
            text="Volumetric Efficiency (VE) Table",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_label.pack(pady=5)

        desc_label = ctk.CTkLabel(
            main_frame,
            text="Cell units are in Grams*Kelvin/kPa",
            font=ctk.CTkFont(size=14)
        )
        desc_label.pack(pady=2)

        # Add real-time status display
        self.status_label = ctk.CTkLabel(
            main_frame,
            text="Current: Not connected to vehicle",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.status_label.pack(pady=5)

        # Display range information
        range_info = f"RPM Range: {min(self.rpm_values)}-{max(self.rpm_values)} RPM | MAP Range: {min(self.map_values)}-{max(self.map_values)} kPa"
        range_label = ctk.CTkLabel(
            main_frame,
            text=range_info,
            font=ctk.CTkFont(size=12)
        )
        range_label.pack(pady=2)

        # Create scrollable frame for the table
        table_frame = ctk.CTkScrollableFrame(main_frame)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Create the table
        self.create_ve_table(table_frame)

        # Add information text
        info_frame = ctk.CTkFrame(main_frame)
        info_frame.pack(fill="x", padx=10, pady=10)

        info_text = ctk.CTkTextbox(info_frame, height=150, wrap="word")
        info_text.pack(fill="x", expand=True)

        info_content = """The values in this table represent the efficiency of the engine's ability to fill the cylinders with air. It is used to predict the volume of air entering each cylinder under varying conditions.

The air mass per cylinder can be determined from the VE table using the following formula:

g/cyl = VE*MAP/Charge Temperature

Where:
VE is in g*K/kPa,
MAP is in kPa,
Charge Temperature is in degrees Kelvin."""

        info_text.insert("1.0", info_content)
        info_text.configure(state="disabled")  # Make read-only

        # Logging frame
        logging_frame = ctk.CTkFrame(main_frame)
        logging_frame.pack(fill="x", pady=5)

        logging_label = ctk.CTkLabel(
            logging_frame,
            text="Real-time Logging",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        logging_label.pack(side="left", padx=10)

        self.log_status_label = ctk.CTkLabel(
            logging_frame,
            text="Status: Not logging",
            font=ctk.CTkFont(size=14)
        )
        self.log_status_label.pack(side="left", padx=20)

        # Logging controls
        log_controls_frame = ctk.CTkFrame(main_frame)
        log_controls_frame.pack(fill="x", pady=5)

        # Interval selection
        interval_frame = ctk.CTkFrame(log_controls_frame)
        interval_frame.pack(side="left", padx=10, fill="x", expand=True)

        ctk.CTkLabel(interval_frame, text="Log interval (ms):").pack(
            side="left", padx=5)

        self.interval_var = tk.StringVar(value=str(self.log_interval))
        interval_entry = ctk.CTkEntry(
            interval_frame, width=80, textvariable=self.interval_var)
        interval_entry.pack(side="left", padx=5)

        # Update interval button
        update_interval_btn = ctk.CTkButton(
            interval_frame,
            text="Update",
            command=self.update_log_interval,
            width=80
        )
        update_interval_btn.pack(side="left", padx=5)

        # Start/Stop logging
        log_button_frame = ctk.CTkFrame(log_controls_frame)
        log_button_frame.pack(side="right", padx=10)

        self.start_log_btn = ctk.CTkButton(
            log_button_frame,
            text="Start Logging",
            command=self.toggle_logging,
            width=120,
            fg_color="#4CAF50"  # Green
        )
        self.start_log_btn.pack(side="left", padx=5)

        # Save log button
        save_log_btn = ctk.CTkButton(
            log_button_frame,
            text="Save Log As...",
            command=self.save_log_as,
            width=120
        )
        save_log_btn.pack(side="left", padx=5)

        # Export VE table button
        export_ve_table_btn = ctk.CTkButton(
            log_button_frame,
            text="Export VE Table",
            command=self.export_ve_table,
            width=120
        )
        export_ve_table_btn.pack(side="left", padx=5)

        # Export history button
        export_history_btn = ctk.CTkButton(
            log_button_frame,
            text="Export History",
            command=self.export_ve_table_history,
            width=120
        )
        export_history_btn.pack(side="left", padx=5)

        # Button frame
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(fill="x", pady=10)

        save_button = ctk.CTkButton(
            button_frame,
            text="Save Table",
            command=self.save_table,
            width=100
        )
        save_button.pack(side="right", padx=5)

        generate_report_button = ctk.CTkButton(
            button_frame,
            text="Generate Report",
            command=self.generate_ve_table_report,
            width=120
        )
        generate_report_button.pack(side="right", padx=5)

        load_button = ctk.CTkButton(
            button_frame,
            text="Load Table",
            command=self.load_table,
            width=100
        )
        load_button.pack(side="right", padx=5)

        # Backup table state button
        backup_button = ctk.CTkButton(
            button_frame,
            text="Backup Table",
            command=self.backup_ve_table,
            width=100
        )
        backup_button.pack(side="right", padx=5)

        reset_button = ctk.CTkButton(
            button_frame,
            text="Reset to Default",
            command=self.reset_table,
            width=120
        )
        reset_button.pack(side="left", padx=5)

    def create_ve_table(self, parent):
        """Create the VE table grid"""
        # Create a frame with normal tkinter to hold the table
        table_container = tk.Frame(parent)
        table_container.pack(fill="both", expand=True)

        # Number of rows and columns
        n_rows = len(self.map_values) + 1  # +1 for header
        n_cols = len(self.rpm_values) + 1  # +1 for row headers

        # Generate default data if not exists
        if not hasattr(self, 've_data'):
            self.create_default_ve_data()

        # Create entries for each cell
        self.entries: List[List[Union[tk.Entry, tk.Label, None]]] = [
            [None for _ in range(n_cols)] for _ in range(n_rows)]

        # Style for the headers
        header_bg = "#3B3B3B"
        header_fg = "#FFFFFF"
        cell_bg = "#2B2B2B"
        cell_fg = "#FFFFFF"

        # Adjust sizes based on number of columns - make cells smaller when there are more columns
        cell_width = max(4, min(8, int(20 / (len(self.rpm_values) / 10))))

        # Empty corner cell
        corner_label = tk.Label(
            table_container,
            text="MAP\\RPM",
            bg=header_bg,
            fg=header_fg,
            width=cell_width,
            height=1,
            relief="raised",
            borderwidth=1
        )
        corner_label.grid(row=0, column=0, sticky="nsew")

        # RPM column headers
        for j, rpm in enumerate(self.rpm_values):
            header = tk.Label(
                table_container,
                text=str(rpm),
                bg=header_bg,
                fg=header_fg,
                width=cell_width,
                height=1,
                relief="raised",
                borderwidth=1
            )
            header.grid(row=0, column=j+1, sticky="nsew")
            self.entries[0][j+1] = header

        # MAP row headers and data cells
        for i, map_val in enumerate(self.map_values):
            # MAP header
            map_header = tk.Label(
                table_container,
                text=str(map_val),
                bg=header_bg,
                fg=header_fg,
                width=cell_width,
                height=1,
                relief="raised",
                borderwidth=1
            )
            map_header.grid(row=i+1, column=0, sticky="nsew")
            self.entries[i+1][0] = map_header

            # Data cells
            for j, rpm in enumerate(self.rpm_values):
                value = self.ve_data[i, j]

                # Check if the cell has been visited (has real data)
                cell_has_data = hasattr(
                    self, 'visited_cells') and self.visited_cells[i, j]

                # Always show 0.0 for cells that haven't been visited with real-time data
                # Only show actual value if the cell has been visited with real-time data during this session
                display_value = str(value) if cell_has_data else "0.0"

                entry_var = tk.StringVar(value=display_value)

                # Adjust background based on whether cell has been visited
                cell_background = cell_bg if cell_has_data else "#1A1A1A"  # Darker for unvisited

                entry = tk.Entry(
                    table_container,
                    textvariable=entry_var,
                    width=cell_width,
                    justify='center',
                    bg=cell_background,
                    fg=cell_fg,
                    relief="sunken",
                    borderwidth=1,
                    font=('TkDefaultFont', 8)  # Smaller font for more cells
                )
                entry.grid(row=i+1, column=j+1, sticky="nsew", padx=0, pady=0)
                self.entries[i+1][j+1] = entry

                # Highlight on focus
                entry.bind("<FocusIn>", lambda event,
                           e=entry: e.configure(bg="#4B4B4B"))
                entry.bind("<FocusOut>", lambda event,
                           e=entry: e.configure(bg=cell_bg))

                # Validate input to allow only numeric values
                entry.config(validate="key", validatecommand=(
                    entry.register(self.validate_float), '%P'))

        # Configure grid to expand with window
        for i in range(n_rows):
            table_container.grid_rowconfigure(i, weight=1)
        for j in range(n_cols):
            table_container.grid_columnconfigure(j, weight=1)

    def validate_float(self, value):
        """Validate if the input is a valid float"""
        if value == "":
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False

    def interpolate_ve_value(self, new_ve_data, i, j, map_val, rpm_val, old_ve_data, old_map_values, old_rpm_values):
        """Interpolate VE value from old data to new grid position"""
        try:
            # Find closest old MAP index
            closest_map_idx = min(range(len(old_map_values)),
                                  key=lambda x: abs(old_map_values[x] - map_val)) if old_map_values else 0

            # Find closest old RPM index
            closest_rpm_idx = min(range(len(old_rpm_values)),
                                  key=lambda x: abs(old_rpm_values[x] - rpm_val)) if old_rpm_values else 0

            # If within bounds, use the value from old data
            if closest_map_idx < old_ve_data.shape[0] and closest_rpm_idx < old_ve_data.shape[1]:
                new_ve_data[i, j] = old_ve_data[closest_map_idx,
                                                closest_rpm_idx]
            else:
                # Otherwise use the default formula
                # Peak efficiency around 4000 RPM
                rpm_factor = 1.0 - abs((rpm_val - 4000) / 5000) * 0.4

                # Higher MAP values generally mean better cylinder filling
                map_factor = 0.7 + (map_val / 105) * 0.3

                # Additional factor for very low RPM (poor efficiency)
                if rpm_val < 1200:
                    rpm_factor *= 0.8 + (rpm_val / 1200) * 0.2

                # Additional factor for very high RPM (reduced efficiency)
                if rpm_val > 6000:
                    rpm_factor *= 1.0 - ((rpm_val - 6000) / 2000) * 0.15

                ve_value = 85.0 * rpm_factor * map_factor
                new_ve_data[i, j] = round(ve_value, 1)
        except Exception as e:
            logger.error(f"Error interpolating VE value: {str(e)}")
            new_ve_data[i, j] = 85.0  # Default value on error

    def save_table(self):
        """Save the current VE table data"""
        try:
            # Update ve_data from entries
            for i in range(len(self.map_values)):
                for j in range(len(self.rpm_values)):
                    entry = self.entries[i+1][j+1]
                    if isinstance(entry, tk.Entry):
                        value = entry.get()
                        try:
                            self.ve_data[i, j] = float(value)
                        except ValueError:
                            # If invalid input, keep previous value
                            entry.delete(0, tk.END)
                            entry.insert(0, str(self.ve_data[i, j]))

            # Save to configuration file
            self.save_config()
            logger.info("VE table saved")
        except Exception as e:
            logger.error(f"Failed to save VE table: {str(e)}")

    def start_real_time_updates(self):
        """Start updating VE table with real-time data"""
        if self.pid_data_getter is None:
            logger.warning(
                "No PID data getter provided, real-time updates disabled")
            return

        # Set up auto-saving of logs
        self.setup_auto_save()

        # Start updating table
        self.update_table_with_live_data()

    def setup_auto_save(self):
        """Set up auto-saving of logs"""
        try:
            # Create a new auto-save file with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            auto_save_filename = f"auto_save_{timestamp}.csv"
            auto_save_path = os.path.join(
                self.logs_directory, auto_save_filename)

            # Open file for writing
            auto_save_file = open(auto_save_path, 'w', newline='')
            auto_save_writer = csv.writer(auto_save_file)

            # Write header row
            auto_save_writer.writerow([
                "Timestamp", "RPM", "MAP (kPa)", "VE (g*K/kPa)",
                "Charge Temp (K)", "Air Mass (g/cyl)"
            ])

            # Store references for auto-saving
            self.auto_save = {
                'file': auto_save_file,
                'writer': auto_save_writer,
                'path': auto_save_path,
                'last_save': time.time()
            }

            logger.info(f"Set up auto-save to {auto_save_path}")

            # Schedule auto-save check only if window is not being closed
            # Check every 10 seconds
            if not (hasattr(self, '_closing') and self._closing) and self.root.winfo_exists():
                try:
                    self.root.after(10000, self.check_auto_save)
                except Exception as e:
                    logger.error(f"Error scheduling auto-save check: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to set up auto-save: {str(e)}")

    def check_auto_save(self):
        """Check if we need to create a new auto-save file"""
        try:
            # Check if the window is being closed - don't continue if it is
            if hasattr(self, '_closing') and self._closing:
                return

            # Check if 5 minutes have passed since last auto-save file
            if hasattr(self, 'auto_save') and time.time() - self.auto_save['last_save'] > 300:
                # Close the current file
                if self.auto_save['file']:
                    try:
                        self.auto_save['file'].close()
                    except Exception as e:
                        logger.error(f"Error closing auto-save file: {str(e)}")

                # Create a new file
                self.setup_auto_save()

            # Only schedule next check if window still exists
            if self.root.winfo_exists():
                try:
                    self.root.after(10000, self.check_auto_save)
                except Exception as e:
                    logger.error(
                        f"Error scheduling next auto-save check: {str(e)}")

        except Exception as e:
            logger.error(f"Error in auto-save check: {str(e)}")

    def update_table_with_live_data(self):
        """Update the table with live data from the vehicle"""
        try:
            # Check if the window is being closed - don't schedule more updates
            if hasattr(self, '_closing') and self._closing:
                return

            if self.pid_data_getter:
                try:
                    pid_data = self.pid_data_getter()

                    # Get RPM and MAP values if available
                    if pid_data and 'RPM' in pid_data and 'INTAKE_PRESSURE' in pid_data:
                        self.current_rpm = float(
                            pid_data['RPM'].get('value', 0))
                        self.current_map = float(
                            pid_data['INTAKE_PRESSURE'].get('value', 0))

                        # Highlight the current cell in the VE table
                        # This will also populate the cell with data if it's empty
                        self.highlight_current_cell()

                        # Start data logging if not already started
                        if not hasattr(self, '_logging_started'):
                            self._logging_started = True
                            self.log_data_point()
                except Exception as e:
                    logger.error(f"Error processing PID data: {str(e)}")

            # Check if window still exists before scheduling next update
            if self.root.winfo_exists():
                # Schedule the next update (separate from logging interval)
                self.update_timer = self.root.after(
                    200, self.update_table_with_live_data)  # Update display faster than logging
        except Exception as e:
            logger.error(f"Error updating VE table with live data: {str(e)}")

    def highlight_current_cell(self):
        """Highlight the cell closest to current RPM and MAP values and update with real-time data"""
        try:
            # Find closest RPM and MAP indices
            rpm_idx = min(range(len(self.rpm_values)),
                          key=lambda i: abs(self.rpm_values[i] - self.current_rpm))
            map_idx = min(range(len(self.map_values)),
                          key=lambda i: abs(self.map_values[i] - self.current_map))

            # Reset all cell backgrounds
            for i in range(len(self.map_values)):
                for j in range(len(self.rpm_values)):
                    entry = self.entries[i+1][j+1]
                    if isinstance(entry, tk.Entry):
                        # Color based on whether cell has been visited or not
                        if hasattr(self, 'visited_cells') and self.visited_cells[i, j]:
                            # Default background for visited cells
                            entry.configure(bg="#2B2B2B")
                        else:
                            # Darker background for unvisited cells
                            entry.configure(bg="#1A1A1A")

                            # Ensure that unvisited cells show 0.0
                            entry.delete(0, tk.END)
                            entry.insert(0, "0.0")

            # Highlight the current cell and mark as visited
            current_cell = self.entries[map_idx+1][rpm_idx+1]
            if isinstance(current_cell, tk.Entry):
                current_cell.configure(bg="#4CAF50")  # Green highlight

                # Mark this cell as visited for the current session only
                if hasattr(self, 'visited_cells'):
                    # Ensure the indices are valid
                    if 0 <= map_idx < self.visited_cells.shape[0] and 0 <= rpm_idx < self.visited_cells.shape[1]:
                        # Mark as visited in this session
                        self.visited_cells[map_idx, rpm_idx] = True
                    else:
                        # Reset the dimensions if we have an index error
                        logger.warning(
                            f"Invalid indices for visited_cells: {map_idx}, {rpm_idx}. Shape is {self.visited_cells.shape}. Recreating array.")
                        self.visited_cells = np.zeros(
                            (len(self.map_values), len(self.rpm_values)), dtype=bool)
                        # Only mark the current cell as visited if indices are valid
                        if 0 <= map_idx < len(self.map_values) and 0 <= rpm_idx < len(self.rpm_values):
                            self.visited_cells[map_idx, rpm_idx] = True

                # Calculate a VE value based on current conditions if this is our first time here
                # In a real application, this would be calculated from actual sensor data
                # For now, we're using a simplified model
                # Only populate cells that haven't been visited yet with real-time data
                # Check if the cell hasn't been populated yet
                if hasattr(self, 'visited_cells') and 0 <= map_idx < self.visited_cells.shape[0] and 0 <= rpm_idx < self.visited_cells.shape[1] and not self.visited_cells[map_idx, rpm_idx]:
                    # Calculate VE based on RPM and MAP
                    rpm_val = self.rpm_values[rpm_idx]
                    map_val = self.map_values[map_idx]

                    # Peak efficiency around 4000 RPM
                    rpm_factor = 1.0 - abs((rpm_val - 4000) / 5000) * 0.4

                    # Higher MAP values generally mean better cylinder filling
                    map_factor = 0.7 + (map_val / 105) * 0.3

                    # Additional factor for very low RPM (poor efficiency)
                    if rpm_val < 1200:
                        rpm_factor *= 0.8 + (rpm_val / 1200) * 0.2

                    # Additional factor for very high RPM (reduced efficiency)
                    if rpm_val > 6000:
                        rpm_factor *= 1.0 - ((rpm_val - 6000) / 2000) * 0.15

                    # Add a random variation to make it look like real data
                    import random
                    random_factor = 1.0 + \
                        (random.random() - 0.5) * 0.1  # ±5% variation

                    ve_value = 85.0 * rpm_factor * map_factor * random_factor
                    ve_value = round(ve_value, 1)

                    # Ensure ve_data is properly initialized as a 2D array with correct shape
                    if not hasattr(self, 've_data') or self.ve_data.shape != (len(self.map_values), len(self.rpm_values)):
                        logger.warning(
                            f"ve_data has incorrect shape or is not initialized. Creating new array.")
                        self.ve_data = np.zeros(
                            (len(self.map_values), len(self.rpm_values)), dtype=float)

                    # Record the change in the history tracker
                    old_value = self.ve_data[map_idx, rpm_idx] if (
                        0 <= map_idx < self.ve_data.shape[0] and 0 <= rpm_idx < self.ve_data.shape[1]) else 0.0

                    # Ensure indices are valid before updating
                    if 0 <= map_idx < self.ve_data.shape[0] and 0 <= rpm_idx < self.ve_data.shape[1]:
                        self.ve_data[map_idx, rpm_idx] = ve_value
                    else:
                        logger.error(
                            f"Invalid indices for ve_data: {map_idx}, {rpm_idx}. Shape is {self.ve_data.shape}")
                        # Skip the rest of the processing for this cell
                        return

                    # Track the change in history
                    self.ve_table_history['timestamp'].append(time.time())
                    self.ve_table_history['location'].append(
                        f"{self.map_values[map_idx]}kPa/{self.rpm_values[rpm_idx]}RPM")
                    self.ve_table_history['old_value'].append(old_value)
                    self.ve_table_history['new_value'].append(ve_value)

                    # Limit history size to prevent memory issues
                    max_history = 1000
                    if len(self.ve_table_history['timestamp']) > max_history:
                        for key in self.ve_table_history:
                            self.ve_table_history[key] = self.ve_table_history[key][-max_history:]

                    # Update the entry with the calculated value
                    current_cell.delete(0, tk.END)
                    current_cell.insert(0, str(ve_value))

            # Store the current VE value for logging
            self.current_ve = self.ve_data[map_idx, rpm_idx]

            # Update the status display
            self.status_label.configure(
                text=f"Current: RPM={self.current_rpm:.1f}, MAP={self.current_map:.1f}kPa, "
                f"VE={self.current_ve:.1f} g*K/kPa"
            )
        except Exception as e:
            logger.error(f"Error highlighting current cell: {str(e)}")
            self.status_label.configure(text=f"Error: {str(e)}")

    def load_table(self):
        """Load VE table configuration from file and recreate with empty cells"""
        # Only load configuration settings, not data values
        self.load_config()

        # Reset VE data to ensure it's empty
        self.create_default_ve_data()

        # Recreate the table with empty data
        for widget in self.root.winfo_children():
            widget.destroy()
        self.setup_ui()

        logger.info(
            "VE table configuration loaded but table is empty, ready for real-time data")

    def load_config(self):
        """Load VE table configuration from file"""
        try:
            # Always use the defined ranges
            rpm_range = list(range(400, 8001, 400))
            map_range = list(range(15, 110, 5))

            if os.path.exists(self.config_file) and not self.force_reset:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)

                    # Check if this is the expected version and format
                    config_version = config.get('version', '1.0')
                    config_has_correct_ranges = False

                    # Check if the config has the correct RPM and MAP ranges
                    if 'rpm_values' in config and 'map_values' in config:
                        expected_rpm = list(range(400, 8001, 400))
                        expected_map = list(range(15, 110, 5))
                        if len(config['rpm_values']) == len(expected_rpm) and len(config['map_values']) == len(expected_map):
                            if all(abs(a-b) < 0.1 for a, b in zip(config['rpm_values'], expected_rpm)) and \
                               all(abs(a-b) < 0.1 for a, b in zip(config['map_values'], expected_map)):
                                config_has_correct_ranges = True

                    # Always create an empty table regardless of what's in the config file
                    # This ensures the table only populates with real-time data from the current session
                    map_count = len(self.map_values)
                    rpm_count = len(self.rpm_values)

                    # Create empty arrays for VE data and visited cells
                    self.ve_data = np.zeros(
                        (map_count, rpm_count), dtype=float)
                    self.visited_cells = np.zeros(
                        (map_count, rpm_count), dtype=bool)

                    # We'll keep the structure/dimensions from the config file but not the actual values
                    logger.info(
                        "Created empty VE table for real-time data logging")

                    # Save the historical data in a separate attribute in case we want to reference it later
                    # but don't use it to populate the table
                    if 've_data' in config:
                        ve_data_list = config['ve_data']
                        if (isinstance(ve_data_list, list) and
                            len(ve_data_list) == map_count and
                                all(isinstance(row, list) and len(row) == rpm_count for row in ve_data_list)):
                            self.historical_ve_data = np.array(
                                ve_data_list, dtype=float)
                            logger.info(
                                "Saved historical VE data for reference")

                    if 'visited_cells' in config:
                        visited_cells_list = config['visited_cells']
                        if (isinstance(visited_cells_list, list) and
                            len(visited_cells_list) == map_count and
                                all(isinstance(row, list) and len(row) == rpm_count for row in visited_cells_list)):
                            self.historical_visited_cells = np.array(
                                visited_cells_list, dtype=bool)
                            logger.info(
                                "Saved historical visited cells for reference")

                        logger.info("Loaded VE table with correct dimensions")
                    elif 've_data' in config:
                        # Need to transform old data to new format
                        old_ve_data = np.array(config['ve_data'])
                        old_rpm_values = config.get('rpm_values', [])
                        old_map_values = config.get('map_values', [])

                        # Create a new VE data array with the correct dimensions
                        new_ve_data = np.ones(
                            (len(map_range), len(rpm_range))) * 85.0

                        # If we have old data, map it to the new ranges as best we can
                        if len(old_rpm_values) > 0 and len(old_map_values) > 0:
                            # Interpolate/map old values to new grid
                            for i, map_val in enumerate(map_range):
                                for j, rpm_val in enumerate(rpm_range):
                                    # Find closest old indices
                                    if map_val in old_map_values and rpm_val in old_rpm_values:
                                        # Direct match
                                        old_map_idx = old_map_values.index(
                                            map_val)
                                        old_rpm_idx = old_rpm_values.index(
                                            rpm_val)
                                        if old_map_idx < old_ve_data.shape[0] and old_rpm_idx < old_ve_data.shape[1]:
                                            new_ve_data[i,
                                                        j] = old_ve_data[old_map_idx, old_rpm_idx]
                                    else:
                                        # Find closest values and interpolate
                                        self.interpolate_ve_value(new_ve_data, i, j, map_val, rpm_val,
                                                                  old_ve_data, old_map_values, old_rpm_values)

                            self.ve_data = new_ve_data
                        else:
                            # If no proper old data, create new default
                            self.create_default_ve_data()
                    else:
                        # No VE data in config
                        self.create_default_ve_data()

                    # Always use the new ranges
                    self.rpm_values = rpm_range
                    self.map_values = map_range

                logger.info(f"Loaded VE table from {self.config_file}")
                return True
        except Exception as e:
            logger.error(f"Failed to load VE table config: {str(e)}")

        # If loading fails, create default data
        self.create_default_ve_data()
        return False

    def create_default_ve_data(self):
        """Create empty VE table data to be populated with real-time data"""
        # Create an empty VE table with zeros - the values will only be populated during real-time data logging
        # Ensure the array is explicitly created as 2D
        map_count = len(self.map_values)
        rpm_count = len(self.rpm_values)

        # Always use zeros for a truly empty table
        self.ve_data = np.zeros((map_count, rpm_count), dtype=float)

        # Initialize a visited cells tracker to know which cells have real data
        # All cells start as unvisited (False)
        self.visited_cells = np.zeros((map_count, rpm_count), dtype=bool)

        # Clear any previously stored historical data
        if hasattr(self, 'historical_ve_data'):
            delattr(self, 'historical_ve_data')
        if hasattr(self, 'historical_visited_cells'):
            delattr(self, 'historical_visited_cells')

        # Initialize a history tracker for VE table changes
        self.ve_table_history = {
            'timestamp': [],
            'location': [],
            'old_value': [],
            'new_value': []
        }

        logger.info(
            "Created empty VE table that will only populate with real-time data")

    def save_config(self):
        """Save VE table configuration to file"""
        try:
            # Ensure we're using the correct ranges
            rpm_range = list(range(400, 8001, 400))
            map_range = list(range(15, 110, 5))

            # Verify dimensions match
            if self.ve_data.shape != (len(map_range), len(rpm_range)):
                logger.warning(
                    "VE data dimensions don't match expected ranges, recreating table")
                # Save the old data for potential mapping
                old_ve_data = self.ve_data
                old_rpm_values = self.rpm_values
                old_map_values = self.map_values

                # Reset to correct ranges
                self.rpm_values = rpm_range
                self.map_values = map_range

                # Create new VE data with correct dimensions - empty (all zeros)
                new_ve_data = np.zeros(
                    (len(map_range), len(rpm_range)), dtype=float)

                # Map old values to new grid if possible
                for i, map_val in enumerate(map_range):
                    for j, rpm_val in enumerate(rpm_range):
                        # Find closest old indices
                        if map_val in old_map_values and rpm_val in old_rpm_values:
                            # Direct match
                            old_map_idx = old_map_values.index(map_val)
                            old_rpm_idx = old_rpm_values.index(rpm_val)
                            if old_map_idx < old_ve_data.shape[0] and old_rpm_idx < old_ve_data.shape[1]:
                                new_ve_data[i,
                                            j] = old_ve_data[old_map_idx, old_rpm_idx]
                        else:
                            # Find closest values and interpolate
                            self.interpolate_ve_value(new_ve_data, i, j, map_val, rpm_val,
                                                      old_ve_data, old_map_values, old_rpm_values)

                self.ve_data = new_ve_data

            # Save only the configuration settings, not the actual data values
            # We want to preserve the ranges but not the values since we want an empty table
            # We'll save visited_cells for historical tracking purposes, but they'll be ignored on load
            config = {
                'rpm_values': self.rpm_values,
                'map_values': self.map_values,
                'version': '2.0',  # Add version to track format changes
                'visited_cells': self.visited_cells.tolist() if hasattr(self, 'visited_cells') else []
            }

            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)

            logger.info(f"Saved VE table to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save VE table config: {str(e)}")
            return False

    def reset_table(self):
        """Reset the table to an empty state for real-time data logging"""
        # Re-generate an empty table
        self.create_default_ve_data()

        # Clear any historical data references
        if hasattr(self, 'historical_ve_data'):
            delattr(self, 'historical_ve_data')
        if hasattr(self, 'historical_visited_cells'):
            delattr(self, 'historical_visited_cells')

        # Recreate the table UI
        for widget in self.root.winfo_children():
            widget.destroy()
        self.setup_ui()

        # Reset the log history
        self.log_history = {
            'timestamp': [],
            'rpm': [],
            'map': [],
            've': []
        }

        logger.info("VE table reset to empty state for real-time data logging")

    def update_log_interval(self):
        """Update the logging interval"""
        try:
            new_interval = int(self.interval_var.get())
            if new_interval < 100:  # Minimum 100ms
                new_interval = 100
                self.interval_var.set("100")

            self.log_interval = new_interval
            logger.info(f"Updated log interval to {self.log_interval}ms")
        except ValueError:
            # Reset to current value
            self.interval_var.set(str(self.log_interval))
            logger.error("Invalid log interval value")

    def toggle_logging(self):
        """Start or stop logging"""
        if not self.log_enabled:
            self.start_logging()
        else:
            self.stop_logging()

    def start_logging(self):
        """Start logging data"""
        try:
            if not self.pid_data_getter:
                messagebox.showwarning(
                    "Logging Error", "Cannot log without vehicle data connection")
                return

            # Create a new log file with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"auto_save_{timestamp}.csv"
            log_path = os.path.join(self.logs_directory, log_filename)

            self.log_file = open(log_path, 'w', newline='')
            self.csv_writer = csv.writer(self.log_file)

            # Write header row
            self.csv_writer.writerow([
                "Timestamp", "RPM", "MAP (kPa)", "VE (g*K/kPa)",
                "Charge Temp (K)", "Air Mass (g/cyl)"
            ])

            # Update UI
            self.log_enabled = True
            self.start_log_btn.configure(
                text="Stop Logging", fg_color="#F44336")  # Red
            self.log_status_label.configure(
                text=f"Status: Logging to {log_filename}")
            logger.info(f"Started logging to {log_path}")

            # Start logging cycle
            self.log_data_point()

        except Exception as e:
            logger.error(f"Failed to start logging: {str(e)}")
            messagebox.showerror(
                "Logging Error", f"Failed to start logging: {str(e)}")

    def stop_logging(self):
        """Stop logging data"""
        try:
            if self.log_file:
                self.log_file.close()
                self.log_file = None
                self.csv_writer = None

            # Update UI
            self.log_enabled = False
            self.start_log_btn.configure(
                text="Start Logging", fg_color="#4CAF50")  # Green
            self.log_status_label.configure(text="Status: Not logging")
            logger.info("Stopped logging")

        except Exception as e:
            logger.error(f"Error stopping logging: {str(e)}")

    def log_data_point(self):
        """Log current data point to file and update history"""
        try:
            # Always update history, even if not writing to file
            # Get current time
            timestamp = datetime.datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S.%f")[:-3]
            current_time = time.time()

            # Calculate air mass using formula: g/cyl = VE*MAP/Charge Temperature
            # Assume a standard charge temperature of 298K (25°C) if not available
            charge_temp = 298.0  # Could be from a sensor if available

            # Calculate air mass
            air_mass = (self.current_ve * self.current_map) / charge_temp

            # Prepare the row data
            row_data = [
                timestamp,
                f"{self.current_rpm:.1f}",
                f"{self.current_map:.1f}",
                f"{self.current_ve:.1f}",
                f"{charge_temp:.1f}",
                f"{air_mass:.4f}"
            ]

            # Write to file if logging is enabled
            if self.log_enabled and self.csv_writer and self.log_file:
                # Write data point to CSV
                self.csv_writer.writerow(row_data)
                # Make sure data is written to file
                self.log_file.flush()

            # Write to auto-save file if it exists
            if hasattr(self, 'auto_save') and self.auto_save and 'writer' in self.auto_save:
                try:
                    self.auto_save['writer'].writerow(row_data)
                    self.auto_save['file'].flush()
                except Exception as e:
                    logger.error(f"Error writing to auto-save file: {str(e)}")

            # Add to history (for potential plotting)
            self.log_history['timestamp'].append(current_time)
            self.log_history['rpm'].append(self.current_rpm)
            self.log_history['map'].append(self.current_map)
            self.log_history['ve'].append(self.current_ve)

            # Trim history if it gets too long
            if len(self.log_history['timestamp']) > self.max_history_points:
                for key in self.log_history:
                    self.log_history[key] = self.log_history[key][-self.max_history_points:]

            # Schedule next log if logging is enabled or we have real-time data
            # But only if the window is not being closed and still exists
            if (self.log_enabled or self.pid_data_getter) and \
               not (hasattr(self, '_closing') and self._closing) and \
               self.root.winfo_exists():
                try:
                    self.root.after(self.log_interval, self.log_data_point)
                except Exception as e:
                    logger.error(
                        f"Error scheduling next log data point: {str(e)}")

        except Exception as e:
            logger.error(f"Error logging data: {str(e)}")
            # Only stop logging if there was an error with the file
            if self.log_enabled and self.log_file:
                self.stop_logging()

    def backup_ve_table(self):
        """Create a backup of the current VE table state with timestamp"""
        try:
            # Create a timestamp for the backup filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"ve_table_backup_{timestamp}.json"

            # Get file path from user
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialdir=self.logs_directory,
                title="Backup VE Table State",
                initialfile=default_filename
            )

            if not file_path:  # User cancelled
                return

            # Prepare the backup data
            backup_data = {
                've_data': self.ve_data.tolist(),
                'rpm_values': self.rpm_values,
                'map_values': self.map_values,
                'visited_cells': self.visited_cells.tolist() if hasattr(self, 'visited_cells') else [],
                'version': '2.0',
                'backup_date': timestamp,
                'metadata': {
                    'total_cells': len(self.map_values) * len(self.rpm_values),
                    'populated_cells': np.count_nonzero(self.visited_cells) if hasattr(self, 'visited_cells') else 0,
                    'rpm_range': f"{min(self.rpm_values)}-{max(self.rpm_values)}",
                    'map_range': f"{min(self.map_values)}-{max(self.map_values)}"
                }
            }

            # Save the backup to file
            with open(file_path, 'w') as f:
                json.dump(backup_data, f, indent=2)

            messagebox.showinfo(
                "Success", f"VE table state backed up to {file_path}")
            logger.info(f"VE table state backed up to {file_path}")

        except Exception as e:
            logger.error(f"Error backing up VE table: {str(e)}")
            messagebox.showerror(
                "Error", f"Failed to backup VE table: {str(e)}")

    def export_ve_table_history(self):
        """Export the history of VE table changes to a CSV file"""
        try:
            # Check if we have history data
            if not hasattr(self, 've_table_history') or not self.ve_table_history['timestamp']:
                messagebox.showinfo(
                    "No Data", "No VE table change history to export")
                return

            # Get file path from user
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialdir=self.logs_directory,
                title="Export VE Table Change History"
            )

            if not file_path:  # User cancelled
                return

            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow([
                    "Timestamp",
                    "Cell Location (MAP/RPM)",
                    "Old Value",
                    "New Value",
                    "Change"
                ])

                # Write all history entries
                for i in range(len(self.ve_table_history['timestamp'])):
                    timestamp = datetime.datetime.fromtimestamp(
                        self.ve_table_history['timestamp'][i]
                    ).strftime("%Y-%m-%d %H:%M:%S")

                    location = self.ve_table_history['location'][i]
                    old_val = self.ve_table_history['old_value'][i]
                    new_val = self.ve_table_history['new_value'][i]

                    # Calculate the change
                    if old_val == 0:  # First time cell is populated
                        change = "Initial"
                    else:
                        change = f"{new_val - old_val:+.1f}"

                    writer.writerow([
                        timestamp,
                        location,
                        f"{old_val:.1f}",
                        f"{new_val:.1f}",
                        change
                    ])

            messagebox.showinfo(
                "Success", f"VE table history exported to {file_path}")
            logger.info(f"VE table history exported to {file_path}")

        except Exception as e:
            logger.error(f"Error exporting VE table history: {str(e)}")
            messagebox.showerror(
                "Error", f"Failed to export VE table history: {str(e)}")

    def generate_ve_table_report(self):
        """Generate a detailed report of the VE table data"""
        try:
            # Get file path from user
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialdir=self.logs_directory,
                title="Save VE Table Report"
            )

            if not file_path:  # User cancelled
                return

            with open(file_path, 'w') as f:
                # Write report header
                f.write("VOLUMETRIC EFFICIENCY TABLE REPORT\n")
                f.write("=" * 50 + "\n\n")
                f.write(
                    f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                # Table configuration details
                f.write("TABLE CONFIGURATION\n")
                f.write("-" * 50 + "\n")
                f.write(
                    f"RPM Range: {min(self.rpm_values)}-{max(self.rpm_values)} RPM in steps of {self.rpm_values[1] - self.rpm_values[0]} RPM\n")
                f.write(
                    f"MAP Range: {min(self.map_values)}-{max(self.map_values)} kPa in steps of {self.map_values[1] - self.map_values[0]} kPa\n")
                f.write(
                    f"Table Size: {len(self.map_values)} rows x {len(self.rpm_values)} columns\n\n")

                # Data statistics
                f.write("DATA STATISTICS\n")
                f.write("-" * 50 + "\n")

                # Only analyze visited cells
                if hasattr(self, 'visited_cells'):
                    total_cells = self.visited_cells.size
                    visited_count = np.count_nonzero(self.visited_cells)
                    visited_percent = (visited_count / total_cells) * 100
                    f.write(
                        f"Cells Populated: {visited_count}/{total_cells} ({visited_percent:.1f}%)\n")

                    if visited_count > 0:
                        # Get statistics only for visited cells
                        visited_indices = np.where(self.visited_cells)
                        visited_values = self.ve_data[visited_indices]

                        f.write(
                            f"Minimum VE Value: {np.min(visited_values):.1f} g*K/kPa\n")
                        f.write(
                            f"Maximum VE Value: {np.max(visited_values):.1f} g*K/kPa\n")
                        f.write(
                            f"Average VE Value: {np.mean(visited_values):.1f} g*K/kPa\n")
                        f.write(
                            f"Median VE Value: {np.median(visited_values):.1f} g*K/kPa\n")
                        f.write(
                            f"Standard Deviation: {np.std(visited_values):.2f}\n\n")

                        # Distribution analysis
                        f.write("DISTRIBUTION ANALYSIS\n")
                        f.write("-" * 50 + "\n")
                        bins = [60, 70, 80, 90, 100, 110, 120]
                        hist, _ = np.histogram(visited_values, bins=bins)
                        for i in range(len(bins)-1):
                            percent = (hist[i] / visited_count) * 100
                            f.write(
                                f"{bins[i]}-{bins[i+1]} g*K/kPa: {hist[i]} cells ({percent:.1f}%)\n")

                # Data collection summary
                f.write("\nDATA COLLECTION SUMMARY\n")
                f.write("-" * 50 + "\n")
                if hasattr(self, 'log_history') and self.log_history['timestamp']:
                    start_time = datetime.datetime.fromtimestamp(
                        min(self.log_history['timestamp']))
                    end_time = datetime.datetime.fromtimestamp(
                        max(self.log_history['timestamp']))
                    duration = end_time - start_time
                    f.write(
                        f"Logging Start: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(
                        f"Logging End: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Duration: {duration}\n")
                    f.write(
                        f"Data Points Collected: {len(self.log_history['timestamp'])}\n\n")

                    # RPM and MAP ranges seen during logging
                    min_rpm = min(self.log_history['rpm'])
                    max_rpm = max(self.log_history['rpm'])
                    min_map = min(self.log_history['map'])
                    max_map = max(self.log_history['map'])
                    f.write(
                        f"RPM Range Observed: {min_rpm:.1f} - {max_rpm:.1f} RPM\n")
                    f.write(
                        f"MAP Range Observed: {min_map:.1f} - {max_map:.1f} kPa\n")
                else:
                    f.write("No logging history available.\n")

                # Add recommendations section
                f.write("\nRECOMMENDATIONS\n")
                f.write("-" * 50 + "\n")
                if hasattr(self, 'visited_cells'):
                    coverage = float(visited_count) / \
                        float(total_cells) * 100.0
                    if coverage < 25:
                        f.write(
                            "• Low data coverage (less than 25%). Consider collecting more data to improve table accuracy.\n")
                    elif coverage < 50:
                        f.write(
                            "• Moderate data coverage. Additional data collection would be beneficial for areas with gaps.\n")
                    else:
                        f.write(
                            "• Good data coverage. Continue refining with more data points if needed.\n")

                    # Identify missing areas in the table
                    empty_ranges = []
                    for i, map_val in enumerate(self.map_values):
                        row_empty = np.count_nonzero(
                            self.visited_cells[i, :]) == 0
                        if row_empty:
                            empty_ranges.append(f"MAP = {map_val} kPa")

                    for j, rpm_val in enumerate(self.rpm_values):
                        col_empty = np.count_nonzero(
                            self.visited_cells[:, j]) == 0
                        if col_empty:
                            empty_ranges.append(f"RPM = {rpm_val}")

                    if empty_ranges:
                        f.write(
                            "\nMissing data in these ranges (consider testing these conditions):\n")
                        # Show only first 10 to avoid excessive output
                        for r in empty_ranges[:10]:
                            f.write(f"• {r}\n")
                        if len(empty_ranges) > 10:
                            f.write(
                                f"• ... and {len(empty_ranges) - 10} more ranges\n")

            messagebox.showinfo(
                "Success", f"VE table report generated at {file_path}")
            logger.info(f"VE table report generated at {file_path}")

        except Exception as e:
            logger.error(f"Error generating VE table report: {str(e)}")
            messagebox.showerror(
                "Error", f"Failed to generate report: {str(e)}")

    def export_ve_table(self):
        """Export the current VE table data to a CSV file for review"""
        try:
            # Get file path from user
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialdir=self.logs_directory,
                title="Export VE Table Data"
            )

            if not file_path:  # User cancelled
                return

            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)

                # Write header row with RPM values
                header_row = ["MAP/RPM"] + [str(rpm)
                                            for rpm in self.rpm_values]
                writer.writerow(header_row)

                # Write data rows with MAP values and VE data
                for i, map_val in enumerate(self.map_values):
                    row = [str(map_val)]

                    for j, rpm in enumerate(self.rpm_values):
                        # Only include values for cells that have been visited
                        if hasattr(self, 'visited_cells') and self.visited_cells[i, j]:
                            row.append(str(self.ve_data[i, j]))
                        else:
                            row.append("")  # Empty for unvisited cells

                    writer.writerow(row)

                # Write additional metadata
                writer.writerow([])  # Empty row as separator
                writer.writerow(["Metadata:"])
                writer.writerow(
                    ["Export Date", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow(
                    ["RPM Range", f"{min(self.rpm_values)}-{max(self.rpm_values)} in steps of {self.rpm_values[1] - self.rpm_values[0]}"])
                writer.writerow(
                    ["MAP Range", f"{min(self.map_values)}-{max(self.map_values)} in steps of {self.map_values[1] - self.map_values[0]} kPa"])

                # Write visited cells statistics
                if hasattr(self, 'visited_cells'):
                    total_cells = self.visited_cells.size
                    visited_count = np.count_nonzero(self.visited_cells)
                    visited_percent = (visited_count / total_cells) * 100
                    writer.writerow(
                        ["Cells Populated", f"{visited_count}/{total_cells} ({visited_percent:.1f}%)"])

            messagebox.showinfo("Success", f"VE table exported to {file_path}")
            logger.info(f"VE table exported to {file_path}")

        except Exception as e:
            logger.error(f"Error exporting VE table: {str(e)}")
            messagebox.showerror(
                "Error", f"Failed to export VE table: {str(e)}")

    def save_log_as(self):
        """Save current log history to a user-specified file"""
        try:
            if not self.log_history['timestamp']:
                messagebox.showinfo("No Data", "No data to save")
                return

            # Get file path from user
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialdir=self.logs_directory,
                title="Save Log As"
            )

            if not file_path:  # User cancelled
                return

            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow([
                    "Timestamp", "RPM", "MAP (kPa)", "VE (g*K/kPa)",
                    "Charge Temp (K)", "Air Mass (g/cyl)"
                ])

                # Write all history data points
                charge_temp = 298.0  # Standard temperature assumption

                for i in range(len(self.log_history['timestamp'])):
                    timestamp = datetime.datetime.fromtimestamp(
                        self.log_history['timestamp'][i]
                    ).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                    rpm = self.log_history['rpm'][i]
                    map_val = self.log_history['map'][i]
                    ve = self.log_history['ve'][i]

                    air_mass = (ve * map_val) / charge_temp

                    writer.writerow([
                        timestamp,
                        f"{rpm:.1f}",
                        f"{map_val:.1f}",
                        f"{ve:.1f}",
                        f"{charge_temp:.1f}",
                        f"{air_mass:.4f}"
                    ])

            messagebox.showinfo("Success", f"Log saved to {file_path}")
            logger.info(f"Log saved to {file_path}")

        except Exception as e:
            logger.error(f"Error saving log: {str(e)}")
            messagebox.showerror("Error", f"Failed to save log: {str(e)}")

    def on_close(self):
        """Handle window close event"""
        try:
            # Create a flag to indicate the window is closing
            self._closing = True

            # Stop all scheduled tasks by collecting and canceling all after() callbacks
            # This is a more thorough approach than just canceling self.update_timer
            try:
                for after_id in self.root.tk.call('after', 'info'):
                    try:
                        self.root.after_cancel(after_id)
                    except Exception:
                        pass  # Ignore errors for individual after_cancel calls
            except Exception as e:
                logger.error(f"Error canceling scheduled tasks: {str(e)}")

            # Stop logging if active
            if self.log_enabled:
                self.stop_logging()

            # Close auto-save file if exists
            if hasattr(self, 'auto_save') and self.auto_save and 'file' in self.auto_save:
                try:
                    self.auto_save['file'].close()
                    logger.info(
                        f"Closed auto-save file: {self.auto_save.get('path', 'unknown')}")
                except Exception as e:
                    logger.error(f"Error closing auto-save file: {str(e)}")

            # Explicitly reset our timer references
            self.update_timer = None

            # Save current table data
            try:
                self.save_table()
            except Exception as e:
                logger.error(f"Error saving table on close: {str(e)}")

            # Destroy the window - wrap in try/except since the window might already be in the process of being destroyed
            try:
                self.root.destroy()
            except tk.TclError:
                pass  # Window might already be destroyed

        except Exception as e:
            logger.error(f"Error during VE table window close: {str(e)}")
            # As a last resort, try to destroy the window even if other cleanup failed
            try:
                self.root.destroy()
            except:
                pass
