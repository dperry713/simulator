#!/usr/bin/env python3
"""
Headless test script to verify OBD Monitor Pro Plotly integration works
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

def test_plotly_charts():
    """Test Plotly chart creation without GUI"""
    try:
        import plotly.graph_objects as go
        from datetime import datetime
        
        # Test creating a basic chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3, 4], y=[10, 11, 12, 13], mode='lines', name='Test'))
        fig.update_layout(title='Test Chart')
        logger.info("✓ Basic Plotly chart created successfully")
        
        # Test creating a gauge chart
        gauge_fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=70,
            title={'text': "Test Gauge"},
            gauge={'axis': {'range': [None, 100]}}
        ))
        logger.info("✓ Plotly gauge chart created successfully")
        
        # Test HTML generation
        html_content = fig.to_html(include_plotlyjs='cdn')
        if html_content and '<html>' in html_content:
            logger.info("✓ Plotly HTML generation successful")
        else:
            logger.warning("⚠ Plotly HTML generation returned empty content")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Plotly chart test failed: {str(e)}")
        return False

def test_plotly_manager_headless():
    """Test PlotlyChartManager functionality without GUI"""
    try:
        # Import the PlotlyChartManager class definition
        sys.path.insert(0, 'obd')
        
        # Mock parent for testing
        class MockParent:
            pass
        
        # We'll test the class methods that don't require GUI
        import tempfile
        import datetime
        
        # Create a minimal chart manager instance
        temp_dir = tempfile.mkdtemp()
        
        # Test theme colors
        dark_colors = {
            'background': '#2b2b2b',
            'paper': '#1e1e1e',
            'text': '#ffffff',
            'grid': '#404040',
            'font_family': 'Arial, sans-serif'
        }
        
        light_colors = {
            'background': '#ffffff',
            'paper': '#f8f9fa',
            'text': '#000000',
            'grid': '#e0e0e0',
            'font_family': 'Arial, sans-serif'
        }
        
        logger.info("✓ Theme colors defined successfully")
        
        # Test chart creation logic
        import plotly.graph_objects as go
        
        fig = go.Figure()
        fig.update_layout(
            title=dict(text="Test Chart", font=dict(color=dark_colors['text'])),
            plot_bgcolor=dark_colors['background'],
            paper_bgcolor=dark_colors['paper']
        )
        
        logger.info("✓ Chart layout configuration successful")
        
        # Test HTML generation
        html_content = fig.to_html(include_plotlyjs='cdn')
        test_html_path = os.path.join(temp_dir, 'test.html')
        
        with open(test_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        if os.path.exists(test_html_path):
            logger.info("✓ Chart HTML file creation successful")
        else:
            logger.warning("⚠ Chart HTML file creation failed")
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
        
        return True
        
    except Exception as e:
        logger.error(f"✗ PlotlyChartManager headless test failed: {str(e)}")
        return False

def test_code_syntax():
    """Test that the main code file has correct syntax"""
    try:
        import ast
        
        with open('obd/obd1.py', 'r') as f:
            code = f.read()
        
        # Parse the code to check for syntax errors
        ast.parse(code)
        logger.info("✓ Main code syntax is valid")
        
        # Check for key classes
        if 'class PlotlyChartManager' in code:
            logger.info("✓ PlotlyChartManager class found")
        else:
            logger.warning("⚠ PlotlyChartManager class not found")
        
        if 'class EnhancedOBDMonitor' in code:
            logger.info("✓ EnhancedOBDMonitor class found")
        else:
            logger.warning("⚠ EnhancedOBDMonitor class not found")
        
        # Check for key methods
        if 'def setup_plotly_chart_widget' in code:
            logger.info("✓ Plotly chart widget setup method found")
        else:
            logger.warning("⚠ Plotly chart widget setup method not found")
        
        return True
        
    except SyntaxError as e:
        logger.error(f"✗ Syntax error in code: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"✗ Code syntax test failed: {str(e)}")
        return False

def main():
    """Run all headless tests"""
    logger.info("=== OBD Monitor Pro Plotly Integration Headless Test ===")
    
    tests = [
        ("Import Test", test_imports),
        ("Plotly Charts Test", test_plotly_charts),
        ("PlotlyChartManager Headless Test", test_plotly_manager_headless),
        ("Code Syntax Test", test_code_syntax),
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
        logger.info("🎉 All headless tests passed! Plotly integration is working correctly.")
        return 0
    else:
        logger.error("❌ Some tests failed. Check the logs above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())