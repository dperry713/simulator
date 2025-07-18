# OBD Monitor Pro - Enhanced

A comprehensive OBD-II (On-Board Diagnostics) monitoring application built with Python and CustomTkinter. This application provides real-time vehicle diagnostics, data logging, visualization, and analysis capabilities.

## Features

### 🚗 Enhanced Real-time Vehicle Monitoring

- **Live Dashboard**: Digital gauges for key metrics (RPM, Speed, Engine Load, etc.)
- **Enhanced Interface**: Modern UI with 1600x1000 window size for better visibility
- **Session Timer**: Track monitoring session duration
- **PID Monitoring**: Real-time Parameter ID data collection and display
- **Auto-refresh**: Configurable update intervals (default: 500ms)
- **Connection Status**: Real-time visual indicators for OBD connection status

### 📊 Data Visualization

- **Real-time Charts**: Live plotting of selected PIDs using matplotlib
- **Historical Data**: Track parameter changes over time
- **Customizable Displays**: Configurable gauge layouts and themes
- **Color-coded Alerts**: Visual indicators for warning and critical values

### 🔧 Diagnostic Tools

- **DTC Reading**: Read and display Diagnostic Trouble Codes
- **DTC Clearing**: Clear fault codes from the vehicle's ECU
- **Error Analysis**: Detailed error reporting and logging
- **Export Functions**: Save diagnostic data for analysis

### 📝 Data Logging & Export

- **Session Logging**: Automatic data collection during monitoring sessions
- **CSV Export**: Export data in CSV format for external analysis
- **Enhanced Logs**: Detailed logging with timestamps and search functionality
- **Auto-save**: Configurable automatic data saving

### ⚙️ Advanced Configuration & Interface

- **Tabbed Interface**: Seven specialized tabs for different functions
  - **Dashboard**: Real-time gauge display with color-coded alerts
  - **PIDs**: Detailed parameter monitoring with filtering and search
  - **Charts**: Live plotting and historical data visualization
  - **DTCs**: Diagnostic trouble code management
  - **Alerts**: Configurable threshold-based warning system
  - **Logs**: Enhanced logging with search and export capabilities
  - **Settings**: Comprehensive application configuration
- **Connection Settings**: COM port selection and baudrate configuration
- **Alert Thresholds**: Customizable warning and critical value alerts
- **Theme Support**: Dark/light theme switching
- **Persistent Settings**: Configuration saved between sessions

## Requirements

### System Requirements

- Windows 10/11 (primary support)
- Python 3.8 or higher
- OBD-II compatible vehicle (1996+ for most vehicles)
- ELM327 OBD-II adapter (USB, Bluetooth Classic, or BLE)

### Python Dependencies

```python
tkinter (usually included with Python)
customtkinter>=5.2.0
obd>=0.7.1
pyserial>=3.5
matplotlib>=3.5.0
numpy>=1.21.0
bleak>=0.19.0  # For Bluetooth BLE connectivity
asyncio        # For asynchronous Bluetooth operations
```

## Installation

### 1. Clone or Download

```bash
git clone <repository-url>
cd obd-monitor
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install customtkinter obd pyserial matplotlib numpy bleak
```

### 3. Hardware Setup

1. Connect your OBD-II adapter to your vehicle's OBD port
2. Choose your connection method:
   - **USB/Serial**: Connect to your computer and note the COM port
   - **Bluetooth Classic**: Pair the adapter with your computer and note the COM port
   - **Bluetooth Low Energy (BLE)**: Ensure BLE is enabled on your computer
3. For J1850 VPW protocol, ensure your adapter supports this standard

## Quick Start

### Prerequisites

1. **OBD-II Adapter**: ELM327 or compatible adapter
2. **Python 3.8+**: Installed and configured
3. **Vehicle**: 1996+ with OBD-II port

### Installation & Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Connect OBD adapter to vehicle and computer
# 3. Note the COM port (typically COM3)

# 4. Run the application
python obd1.py
```

### First Connection

1. **Select Port**: Choose your adapter's COM port (defaults to COM3)
2. **Connect**: Click "Connect" button
3. **Start Monitoring**: Click "Start" to begin data collection
4. **Explore**: Check different tabs for various features

## Usage

### Starting the Application

```bash
python obd1.py
```

### Basic Operation

1. **Connect to Vehicle**:

   - **For Serial Connection**:
     - Select your OBD adapter's COM port (defaults to COM3)
     - Choose appropriate baudrate (38400 recommended)
   - **For Bluetooth BLE Connection**:
     - Select "Bluetooth (BLE)" as connection type
     - Select your protocol (J1850 VPW)
     - Click scan/refresh to discover devices
     - Select your BLE device from the list
   - Click "Connect"

2. **Start Monitoring**:

   - Click "Start" to begin real-time data collection
   - Monitor live data on the Dashboard tab
   - View detailed PIDs in the PIDs tab

3. **View Charts**:

   - Go to Charts tab
   - Select a PID to chart
   - Click "Start Chart" for real-time visualization

4. **Check Diagnostics**:

   - Visit DTCs tab to view trouble codes
   - Use "Refresh DTCs" to get latest codes
   - Clear codes with "Clear DTCs" (if supported)

5. **Configure Alerts**:

   - Go to Alerts tab to set custom thresholds
   - Enable/disable audio and visual alerts
   - Set warning and critical values for each parameter

6. **View Historical Data**:

   - Check Logs tab for session history
   - Use search functionality to find specific entries
   - Export data in CSV or text format

### Key Features Overview

#### Dashboard Tab

- **Real-time Gauges**: RPM, Speed, Engine Load with color-coded displays
- **Active Alerts Panel**: Shows current warnings and critical alerts
- **Session Timer**: Track monitoring session duration
- **Progress Bars**: Visual representation of parameter values

#### PIDs Tab

- **Comprehensive PID Display**: All available parameters in table format
- **Real-time Filtering**: Search and filter PIDs by name or value
- **Min/Max Tracking**: Automatic tracking of parameter ranges
- **Export Functionality**: Save PID data to CSV format

#### Charts Tab

- **Live Plotting**: Real-time matplotlib charts for any PID
- **Historical View**: Track parameter changes over time
- **Configurable Display**: Choose which parameters to chart
- **Data Export**: Save chart data for analysis

#### Enhanced Interface

- **Modern UI**: CustomTkinter-based interface with dark/light themes
- **Large Window**: 1600x1000 default size for better visibility
- **Responsive Design**: Adapts to different screen sizes
- **Tabbed Navigation**: Easy access to all features

### Configuration Options

#### Connection Settings

- **Connection Type**: Choose between Serial or Bluetooth BLE
- **Protocol**: Select communication protocol (J1850 VPW supported)
- **Port**: COM port for Serial adapter (default: COM3)
- **Bluetooth Device**: Select from discovered BLE devices
- **Baudrate**: Communication speed (Serial: 9600/38400/115200, J1850 VPW: 10416)
- **Timeout**: Connection timeout in seconds
- **Auto-connect**: Automatically connect on startup

#### Monitoring Settings

- **Update Interval**: Data refresh rate in milliseconds
- **Max Log Entries**: Maximum number of log entries to keep
- **Auto-save**: Automatically save data during sessions

#### Alert Configuration

- **Audio Alerts**: Sound notifications for threshold breaches
- **Visual Alerts**: On-screen warnings and notifications
- **Custom Thresholds**: Set warning and critical values for each parameter

## File Structure

```text
obd/
├── obd1.py                  # Main application file (Enhanced OBD Monitor)
├── config.json              # Configuration settings (auto-generated)
├── requirements.txt         # Python dependencies
├── install_requirements.py  # Dependency installer helper
├── logs/                    # Log files directory
│   ├── session_*.csv        # Session data exports
│   └── debug_*.log          # Debug logs
├── protocols/               # OBD communication protocols
│   └── j1850_vpw.py         # J1850 VPW protocol implementation
├── bluetooth/               # Bluetooth connectivity modules
│   └── bluetooth_interface.py # BLE interface implementation
├── __pycache__/             # Python cache files
└── README.md                # This documentation file
```

## Configuration File

The application automatically creates a `config.json` file with your settings:

```json
{
  "appearance": {
    "mode": "dark",
    "theme": "blue"
  },
  "connection": {
    "port": "COM3",
    "baudrate": 38400,
    "timeout": 10
  },
  "monitoring": {
    "update_interval": 1,
    "max_log_entries": 1000,
    "log_directory": "logs"
  },
  "alerts": {
    "audio_enabled": true,
    "visual_enabled": true,
    "thresholds": {}
  }
}
```

## Common Issues & Troubleshooting

### Connection Issues

- **"No response from OBD device"**: Check adapter connection and COM port
- **"Permission denied"**: Ensure no other applications are using the COM port
- **"Timeout"**: Try different baudrate or increase timeout value
- **"BLE device not found"**: Ensure Bluetooth is enabled and the device is in range
- **"BLE connection failed"**: Check if the device is already connected to another application
- **"Protocol error"**: Verify your vehicle supports the selected protocol

### Data Issues

- **"No PIDs available"**: Vehicle may not support standard PIDs
- **"Invalid response"**: Check adapter compatibility with your vehicle
- **"Intermittent data"**: Check cable connections and adapter quality

### Application Issues

- **Slow performance**: Increase update interval or reduce log entries
- **Memory usage**: Clear logs periodically or reduce max log entries
- **UI freezing**: Ensure adequate system resources

## Supported Vehicles

This application works with most vehicles that support OBD-II standard:

- **1996+ vehicles** (US mandate)
- **2001+ vehicles** (EU mandate)
- **2008+ vehicles** (Most other regions)

### Tested Adapters

- ELM327 USB adapters
- ELM327 Bluetooth Classic adapters
- ELM327 Bluetooth Low Energy (BLE) adapters
- OBDLink adapters
- Generic OBD-II adapters
- J1850 VPW compatible adapters

## Data Export Formats

### CSV Export

- Timestamp
- PID identifier
- Parameter name
- Value
- Unit of measurement

### Log Export

- Session information
- Error logs
- Connection history
- Performance metrics

## Development

### Code Structure

- **EnhancedOBDMonitor**: Main application class with extended functionality
- **OBD1App**: Alternative simplified interface with BLE support
- **Protocols**: Modular protocol implementations (J1850_VPW)
- **Connectivity**: Connection handlers (Serial, Bluetooth)
- **UI Components**: Tabbed interface with specialized panels
- **Data Handlers**: PID processing and storage
- **Export Functions**: Data formatting and file operations

### Key Methods

- `connect_obd()`: Establishes OBD serial connection
- `connect_ble()`: Establishes Bluetooth BLE connection
- `send_obd_request()`: Sends commands using the selected protocol
- `receive_obd_response()`: Receives data from the vehicle
- `monitor_loop()`: Main data collection loop
- `update_dashboard()`: Updates real-time displays
- `export_data()`: Handles data export operations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and support:

1. Check the troubleshooting section above
2. Review the logs in the `logs/` directory
3. Create an issue with detailed information about your problem

## Changelog

### Version 3.0.0 (Current)

- **Bluetooth BLE Support**: Connect to BLE-enabled OBD adapters
- **Multiple Connection Methods**: Serial and Bluetooth Low Energy (BLE) connectivity
- **J1850 VPW Protocol**: Support for SAE J1850 Variable Pulse Width protocol
- **Protocol Selection**: Choose the appropriate protocol for your vehicle
- **Modular Architecture**: Separated protocol and connectivity components

### Version 2.0.0

- **Enhanced Interface**: Complete UI redesign with modern tabbed interface
- **Improved Window Size**: Increased to 1600x1000 with minimum 1400x900
- **Session Management**: Added session timer and enhanced status tracking
- **Advanced PID Monitoring**: Enhanced PIDs tab with filtering and search
- **Real-time Charts**: Live matplotlib integration for data visualization
- **Alert System**: Comprehensive threshold-based alert configuration
- **Enhanced Logging**: Advanced log management with search and export
- **Settings Panel**: Comprehensive configuration interface
- **COM3 Default**: Automatic preference for COM3 connection
- **Error Handling**: Improved OBD command error handling and recovery
- **Data Export**: Multiple export formats (CSV, TXT) for different data types

### Version 1.0.0

- Initial release
- Basic OBD-II connectivity
- Real-time monitoring dashboard
- PID data collection and display
- DTC reading and clearing
- Data export functionality
- Configurable alerts and thresholds
- Dark/light theme support

---

**Note**: This application is for educational and diagnostic purposes. Always consult a qualified mechanic for vehicle issues. The developers are not responsible for any damage to vehicles or equipment.
