#!/usr/bin/env python3
"""
Demo script to generate sample Plotly charts for OBD Monitor Pro
This creates standalone HTML files to show what the charts would look like
"""

import sys
import os
import datetime
import random
import math

# Add the obd directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'obd'))

import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_demo_data():
    """Create demo OBD data"""
    now = datetime.datetime.now()
    timestamps = [now - datetime.timedelta(minutes=i) for i in range(60, 0, -1)]
    
    # Generate realistic OBD data patterns
    rpm_data = [1000 + 3000 * math.sin(i * 0.1) + random.randint(-200, 200) for i in range(60)]
    speed_data = [max(0, 60 + 40 * math.sin(i * 0.05) + random.randint(-10, 10)) for i in range(60)]
    engine_load_data = [max(0, min(100, 30 + 40 * math.sin(i * 0.08) + random.randint(-5, 5))) for i in range(60)]
    coolant_temp_data = [85 + 5 * math.sin(i * 0.02) + random.randint(-2, 2) for i in range(60)]
    
    return {
        'timestamps': timestamps,
        'RPM': rpm_data,
        'SPEED': speed_data,
        'ENGINE_LOAD': engine_load_data,
        'COOLANT_TEMP': coolant_temp_data
    }

def create_multi_pid_chart(data, theme='dark'):
    """Create a multi-PID interactive chart"""
    colors = get_theme_colors(theme)
    chart_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
    
    fig = go.Figure()
    
    pid_names = ['RPM', 'SPEED', 'ENGINE_LOAD', 'COOLANT_TEMP']
    units = ['RPM', 'km/h', '%', '°C']
    
    for i, (pid, unit) in enumerate(zip(pid_names, units)):
        fig.add_trace(go.Scatter(
            x=data['timestamps'],
            y=data[pid],
            mode='lines+markers',
            name=f"{pid} ({unit})",
            line=dict(color=chart_colors[i % len(chart_colors)], width=2),
            marker=dict(size=4),
            hovertemplate=f'<b>{pid}</b><br>Value: %{{y}}<br>Time: %{{x}}<extra></extra>'
        ))
    
    fig.update_layout(
        title=dict(
            text="Multi-PID Real-time OBD Data",
            font=dict(color=colors['text'], size=18, family=colors['font_family']),
            x=0.5
        ),
        plot_bgcolor=colors['background'],
        paper_bgcolor=colors['paper'],
        font=dict(color=colors['text'], family=colors['font_family']),
        xaxis=dict(
            title="Time",
            gridcolor=colors['grid'],
            color=colors['text'],
            showgrid=True
        ),
        yaxis=dict(
            title="Value",
            gridcolor=colors['grid'],
            color=colors['text'],
            showgrid=True
        ),
        height=600,
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

def create_gauge_dashboard(data, theme='dark'):
    """Create a gauge dashboard"""
    colors = get_theme_colors(theme)
    
    # Create subplots for multiple gauges
    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{'type': 'indicator'}, {'type': 'indicator'}],
               [{'type': 'indicator'}, {'type': 'indicator'}]],
        subplot_titles=('RPM', 'Speed', 'Engine Load', 'Coolant Temp'),
        vertical_spacing=0.25
    )
    
    # Current values (last data point)
    current_rpm = data['RPM'][-1]
    current_speed = data['SPEED'][-1]
    current_load = data['ENGINE_LOAD'][-1]
    current_temp = data['COOLANT_TEMP'][-1]
    
    # RPM Gauge
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=current_rpm,
        title={'text': "RPM"},
        gauge={
            'axis': {'range': [None, 8000]},
            'bar': {'color': "#FF6B6B"},
            'steps': [
                {'range': [0, 3000], 'color': "lightgray"},
                {'range': [3000, 6000], 'color': "yellow"},
                {'range': [6000, 8000], 'color': "red"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 6500
            }
        }
    ), row=1, col=1)
    
    # Speed Gauge
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=current_speed,
        title={'text': "Speed (km/h)"},
        gauge={
            'axis': {'range': [None, 200]},
            'bar': {'color': "#4ECDC4"},
            'steps': [
                {'range': [0, 60], 'color': "lightgray"},
                {'range': [60, 120], 'color': "yellow"},
                {'range': [120, 200], 'color': "red"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 130
            }
        }
    ), row=1, col=2)
    
    # Engine Load Gauge
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=current_load,
        title={'text': "Engine Load (%)"},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': "#45B7D1"},
            'steps': [
                {'range': [0, 50], 'color': "lightgray"},
                {'range': [50, 80], 'color': "yellow"},
                {'range': [80, 100], 'color': "red"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 85
            }
        }
    ), row=2, col=1)
    
    # Coolant Temperature Gauge
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=current_temp,
        title={'text': "Coolant Temp (°C)"},
        gauge={
            'axis': {'range': [None, 120]},
            'bar': {'color': "#96CEB4"},
            'steps': [
                {'range': [0, 80], 'color': "lightgray"},
                {'range': [80, 100], 'color': "yellow"},
                {'range': [100, 120], 'color': "red"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 105
            }
        }
    ), row=2, col=2)
    
    fig.update_layout(
        title=dict(
            text="OBD Live Dashboard",
            font=dict(color=colors['text'], size=20, family=colors['font_family']),
            x=0.5
        ),
        paper_bgcolor=colors['paper'],
        font=dict(color=colors['text'], family=colors['font_family']),
        height=700
    )
    
    return fig

def create_trend_analysis(data, theme='dark'):
    """Create trend analysis chart"""
    colors = get_theme_colors(theme)
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('RPM Trend', 'Speed Trend', 'Engine Load Trend', 'Coolant Temp Trend'),
        vertical_spacing=0.1,
        horizontal_spacing=0.1
    )
    
    # RPM trend with min/max envelope
    rpm_min = [min(data['RPM'][:i+1]) for i in range(len(data['RPM']))]
    rpm_max = [max(data['RPM'][:i+1]) for i in range(len(data['RPM']))]
    
    fig.add_trace(go.Scatter(
        x=data['timestamps'], y=data['RPM'],
        mode='lines', name='RPM',
        line=dict(color='#FF6B6B', width=2)
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=data['timestamps'], y=rpm_max,
        mode='lines', name='RPM Max',
        line=dict(color='#FF6B6B', width=1),
        showlegend=False
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=data['timestamps'], y=rpm_min,
        mode='lines', name='RPM Min',
        line=dict(color='#FF6B6B', width=1),
        fill='tonexty', fillcolor='rgba(255, 107, 107, 0.2)',
        showlegend=False
    ), row=1, col=1)
    
    # Speed trend
    fig.add_trace(go.Scatter(
        x=data['timestamps'], y=data['SPEED'],
        mode='lines', name='Speed',
        line=dict(color='#4ECDC4', width=2)
    ), row=1, col=2)
    
    # Engine Load trend
    fig.add_trace(go.Scatter(
        x=data['timestamps'], y=data['ENGINE_LOAD'],
        mode='lines', name='Load',
        line=dict(color='#45B7D1', width=2)
    ), row=2, col=1)
    
    # Coolant Temp trend
    fig.add_trace(go.Scatter(
        x=data['timestamps'], y=data['COOLANT_TEMP'],
        mode='lines', name='Coolant',
        line=dict(color='#96CEB4', width=2)
    ), row=2, col=2)
    
    fig.update_layout(
        title=dict(
            text="Trend Analysis with Min/Max Envelopes",
            font=dict(color=colors['text'], size=18, family=colors['font_family']),
            x=0.5
        ),
        paper_bgcolor=colors['paper'],
        plot_bgcolor=colors['background'],
        font=dict(color=colors['text'], family=colors['font_family']),
        height=600,
        showlegend=True
    )
    
    fig.update_xaxes(gridcolor=colors['grid'], color=colors['text'])
    fig.update_yaxes(gridcolor=colors['grid'], color=colors['text'])
    
    return fig

def get_theme_colors(theme):
    """Get theme-specific colors"""
    if theme == 'dark':
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

def save_demo_charts():
    """Save demo charts to HTML files"""
    print("Creating demo OBD data...")
    data = create_demo_data()
    
    # Create output directory
    output_dir = "demo_charts"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create charts for both themes
    themes = ['dark', 'light']
    
    for theme in themes:
        print(f"Creating {theme} theme charts...")
        
        # Multi-PID chart
        multi_pid_fig = create_multi_pid_chart(data, theme)
        multi_pid_path = os.path.join(output_dir, f'multi_pid_chart_{theme}.html')
        multi_pid_fig.write_html(multi_pid_path, include_plotlyjs='cdn')
        print(f"✓ Multi-PID chart saved: {multi_pid_path}")
        
        # Gauge dashboard
        gauge_fig = create_gauge_dashboard(data, theme)
        gauge_path = os.path.join(output_dir, f'gauge_dashboard_{theme}.html')
        gauge_fig.write_html(gauge_path, include_plotlyjs='cdn')
        print(f"✓ Gauge dashboard saved: {gauge_path}")
        
        # Trend analysis
        trend_fig = create_trend_analysis(data, theme)
        trend_path = os.path.join(output_dir, f'trend_analysis_{theme}.html')
        trend_fig.write_html(trend_path, include_plotlyjs='cdn')
        print(f"✓ Trend analysis saved: {trend_path}")
    
    print(f"\n🎉 Demo charts created successfully!")
    print(f"Open the HTML files in {output_dir}/ to see the interactive charts.")
    print("Features to try:")
    print("- Hover over data points for tooltips")
    print("- Click legend items to show/hide traces")
    print("- Use zoom and pan tools")
    print("- Drag to select areas for zooming")

if __name__ == "__main__":
    save_demo_charts()