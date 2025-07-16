# OBD Monitor Pro - Plotly Integration Setup

## Overview
This enhanced version of OBD Monitor Pro integrates Plotly for advanced, interactive real-time charts and dashboards, providing a modern visualization experience for OBD data.

## New Dependencies

### Required packages:
- `plotly>=6.2.0` - Interactive plotting library
- `tkinterweb>=4.3.0` - HTML widget for embedding Plotly charts in tkinter
- `matplotlib>=3.10.0` - Legacy chart support (kept for reference)
- `numpy>=1.24.0` - Numerical operations

### Installation:
```bash
pip install -r requirements.txt
```

## New Features

### 1. Interactive Charts Tab
- **Multi-PID Selection**: Select multiple PIDs to overlay on the same chart
- **Interactive Features**: 
  - Zoom and pan with mouse
  - Hover tooltips showing precise values
  - Dynamic legend with click-to-hide functionality
  - Real-time data streaming

### 2. Advanced Dashboard Tab
- **Live Gauges**: Real-time gauge displays for key metrics
- **Trend Analysis**: Combined trend charts with min/max envelopes
- **Sparklines**: Compact mini-charts for quick visualization
- **Dark/Light Mode**: Theme support for all visualizations

### 3. Enhanced Data Management
- **Real-time Data Cache**: Efficient storage of time-series data
- **Theme Synchronization**: Automatic theme updates across all charts
- **Performance Optimization**: Limited data points for smooth rendering

## Usage

### Starting Interactive Charts:
1. Connect to OBD device
2. Go to "Charts" tab
3. Select desired PIDs from the listbox (multiple selection with Ctrl+Click)
4. Click "Start Plotly Chart"
5. Interactive chart will display with real-time updates

### Using Advanced Dashboard:
1. Go to "Advanced Dashboard" tab
2. View live gauges for key metrics
3. Analyze trends in the trend analysis section
4. Monitor sparklines for quick overviews
5. Toggle theme using the dropdown

### Theme Management:
- Use the Settings tab to change overall theme
- Dashboard has its own theme toggle for quick switching
- All Plotly charts automatically update with theme changes

## Technical Implementation

### PlotlyChartManager Class
- Manages all Plotly chart creation and updates
- Handles theme switching and data caching
- Provides multiple chart types (line, gauge, sparkline)
- Generates HTML for embedding in tkinterweb widgets

### Integration Points
- Charts are embedded using tkinterweb.HtmlFrame
- Data updates are synchronized through the monitoring loop
- Theme changes propagate through the PlotlyChartManager
- Temporary HTML files are managed and cleaned up

## Error Handling
- Graceful fallback if tkinterweb fails to load
- Error messages displayed in place of charts
- Logging for debugging chart-related issues
- Safe cleanup of temporary files on exit

## Legacy Support
- Original matplotlib code is commented out but preserved
- Can be re-enabled if needed for reference
- All existing functionality remains intact

## Performance Considerations
- Data cache limited to 100 points per PID for smooth rendering
- HTML charts are regenerated only when necessary
- Temporary files are cleaned up automatically
- Threading used for non-blocking chart updates

## Troubleshooting

### Common Issues:
1. **Charts not displaying**: Check tkinterweb installation
2. **Theme not updating**: Ensure PlotlyChartManager is initialized
3. **Performance issues**: Reduce update frequency or selected PIDs
4. **Memory usage**: Charts auto-limit data points to 100

### Debug Mode:
Set logging level to DEBUG for detailed chart operation logs.

## Future Enhancements
- Additional chart types (bar, scatter, histogram)
- Data export functionality from charts
- Chart layout customization
- Advanced statistical analysis
- Data replay functionality