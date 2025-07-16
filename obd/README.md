# OBD Monitor Pro - Enhanced

A comprehensive OBD-II (On-Board Diagnostics) monitoring application built with Python and CustomTkinter. This application provides real-time vehicle diagnostics, data logging, visualization, and analysis capabilities.

## Features

### 🚗 Real-time Vehicle Monitoring

- **Live Dashboard**: Digital gauges for key metrics (RPM, Speed, Engine Load, etc.)
- **PID Monitoring**: Real-time Parameter ID data collection and display
- **Auto-refresh**: Configurable update intervals for continuous monitoring
- **Connection Status**: Visual indicators for OBD connection status

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

### ⚙️ Advanced Configuration

- **Connection Settings**: COM port selection and baudrate configuration
- **Alert Thresholds**: Customizable warning and critical value alerts
- **Theme Support**: Dark/light theme switching
- **Persistent Settings**: Configuration saved between sessions

## Requirements

### System Requirements

- Windows 10/11 (primary support)
- Python 3.8 or higher
- OBD-II compatible vehicle (1996+ for most vehicles)
- ELM327 OBD-II adapter (USB or Bluetooth)

### Python Dependencies

```
tkinter (usually included with Python)
customtkinter>=5.0.0
python-obd>=0.7.0
pyserial>=3.4
matplotlib>=3.5.0
numpy>=1.21.0
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
pip install customtkinter python-obd pyserial matplotlib numpy
```

### 3. Hardware Setup

1. Connect your ELM327 OBD-II adapter to your vehicle's OBD port
2. If using USB adapter, connect to your computer
3. If using Bluetooth, pair the adapter with your computer
4. Note the COM port assigned to your adapter

## Usage

### Starting the Application

```bash
python obd1.py
```

### Basic Operation

1. **Connect to Vehicle**:

   - Select your OBD adapter's COM port (defaults to COM3)
   - Choose appropriate baudrate (38400 recommended)
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

### Configuration Options

#### Connection Settings

- **Port**: COM port for OBD adapter (default: COM3)
- **Baudrate**: Communication speed (9600/38400/115200)
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

```
obd/
├── obd1.py              # Main application file
├── config.json          # Configuration settings (auto-generated)
├── requirements.txt     # Python dependencies
├── install_requirements.py # Dependency installer
├── logs/               # Log files directory
│   ├── session_*.csv   # Session data exports
│   └── debug_*.log     # Debug logs
└── README.md           # This file
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
- ELM327 Bluetooth adapters
- OBDLink adapters
- Generic OBD-II adapters

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

- **EnhancedOBDMonitor**: Main application class
- **UI Components**: Tabbed interface with specialized panels
- **Data Handlers**: PID processing and storage
- **Export Functions**: Data formatting and file operations

### Key Methods

- `connect_obd()`: Establishes OBD connection
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
