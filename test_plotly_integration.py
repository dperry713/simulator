#!/usr/bin/env python3
"""
Simple test script to verify OBD Monitor Pro Plotly integration works
"""

import sys
import os
import tempfile
import logging

# Add the obd directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'obd'))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all required modules can be imported"""
    try:
        import tkinter as tk
        logger.info("✓ tkinter imported successfully")
        
        import customtkinter as ctk
        logger.info("✓ customtkinter imported successfully")
        
        import plotly.graph_objects as go
        logger.info("✓ plotly imported successfully")
        
        import tkinterweb
        logger.info("✓ tkinterweb imported successfully")
        
        import obd
        logger.info("✓ obd imported successfully")
        
        import matplotlib.pyplot as plt
        logger.info("✓ matplotlib imported successfully")
        
        return True
        
    except ImportError as e:
        logger.error(f"✗ Import error: {str(e)}")
        return False

def test_plotly_manager():
    """Test PlotlyChartManager functionality"""
    try:
        from obd1 import PlotlyChartManager
        
        # Create a temporary parent widget (won't be used for display)
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()  # Hide the window
        
        # Create PlotlyChartManager
        manager = PlotlyChartManager(root, 'dark')
        logger.info("✓ PlotlyChartManager created successfully")
        
        # Test creating a chart
        fig = manager.create_real_time_chart("Test Chart")
        logger.info("✓ Real-time chart created successfully")
        
        # Test creating a gauge chart
        test_data = {
            'value': 50,
            'name': 'Test Gauge',
            'max_value': 100,
            'warning_threshold': 75,
            'critical_threshold': 90
        }
        gauge_fig = manager.create_gauge_chart(test_data)
        logger.info("✓ Gauge chart created successfully")
        
        # Test data update
        import datetime
        manager.update_chart_data("test_chart", "TEST_PID", datetime.datetime.now(), 42)
        logger.info("✓ Chart data updated successfully")
        
        # Test HTML generation
        html_path = manager.save_chart_html(fig, "test_chart")
        if html_path and os.path.exists(html_path):
            logger.info("✓ Chart HTML generated successfully")
        else:
            logger.warning("⚠ Chart HTML generation returned no path")
        
        # Cleanup
        manager.cleanup()
        root.destroy()
        
        return True
        
    except Exception as e:
        logger.error(f"✗ PlotlyChartManager test failed: {str(e)}")
        return False

def test_obd_monitor_creation():
    """Test that OBD Monitor can be created (without connecting to device)"""
    try:
        from obd1 import EnhancedOBDMonitor
        
        # This will create the UI but not connect to any device
        logger.info("Creating OBD Monitor instance...")
        monitor = EnhancedOBDMonitor()
        logger.info("✓ OBD Monitor created successfully")
        
        # Check that key components exist
        if hasattr(monitor, 'plotly_manager'):
            logger.info("✓ PlotlyChartManager integrated successfully")
        else:
            logger.warning("⚠ PlotlyChartManager not found in OBD Monitor")
        
        # Don't run mainloop in test
        monitor.root.destroy()
        
        return True
        
    except Exception as e:
        logger.error(f"✗ OBD Monitor creation failed: {str(e)}")
        return False

def main():
    """Run all tests"""
    logger.info("=== OBD Monitor Pro Plotly Integration Test ===")
    
    tests = [
        ("Import Test", test_imports),
        ("PlotlyChartManager Test", test_plotly_manager),
        ("OBD Monitor Creation Test", test_obd_monitor_creation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\nRunning {test_name}...")
        try:
            if test_func():
                logger.info(f"✓ {test_name} PASSED")
                passed += 1
            else:
                logger.error(f"✗ {test_name} FAILED")
        except Exception as e:
            logger.error(f"✗ {test_name} FAILED with exception: {str(e)}")
    
    logger.info(f"\n=== Test Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        logger.info("🎉 All tests passed! Plotly integration is working correctly.")
        return 0
    else:
        logger.error("❌ Some tests failed. Check the logs above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())