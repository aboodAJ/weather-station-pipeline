import streamlit as st
import pandas as pd
import psycopg2
import os
import plotly.express as px
from dotenv import load_dotenv

# Page Configuration
st.set_page_config(
    page_title="Weather Station",
    page_icon="🌤️",
    layout="wide",
)

# Load environment variables
load_dotenv()

# Custom CSS for spacing
st.markdown("""
<style>
    [data-testid="stMetricValue"] {
        font-size: 2.5rem;
    }
    .main .block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Database Connection (Cached)
@st.cache_resource
def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

# Data Fetching
def get_data(limit=500):
    try:
        conn = get_db_connection()
        if conn.closed:
            st.cache_resource.clear()
            conn = get_db_connection()

        cursor = conn.cursor()
        query = f"""
            SELECT recorded_at, temperature, humidity, light, pressure 
            FROM sensors_data 
            ORDER BY recorded_at DESC 
            LIMIT {limit};
        """
        cursor.execute(query)
        data = cursor.fetchall()
        colnames = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(data, columns=colnames)
        cursor.close()
        return df
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

# --- DASHBOARD LAYOUT ---

st.title("🌤️ Weather Station Dashboard")
st.markdown("Real-time monitoring of local sensor data.")

# Refresh Button
if st.button('🔄 Refresh Data'):
    st.cache_data.clear()

# Fetch Data
df = get_data(limit=2000)

if not df.empty:
    latest = df.iloc[0]
    previous = df.iloc[1] if len(df) > 1 else latest

    # --- TOP METRICS (KPIs) ---
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

    with col_kpi1:
        st.metric("Temperature", f"{latest['temperature']} °C", f"{latest['temperature'] - previous['temperature']:.1f} °C")
    with col_kpi2:
        st.metric("Humidity", f"{latest['humidity']}%", f"{latest['humidity'] - previous['humidity']:.1f}%")
    with col_kpi3:
        st.metric("Pressure", f"{latest['pressure']} hPa", f"{latest['pressure'] - previous['pressure']:.1f}")
    with col_kpi4:
        st.metric("Light Level", f"{latest['light']}", f"{latest['light'] - previous['light']:.0f}")

    st.markdown("---")

    # --- CHARTS (2x2 Grid) ---
    
    # ROW 1: Temperature & Humidity
    row1_col1, row1_col2 = st.columns(2)
    
    with row1_col1:
        fig_temp = px.line(df, x='recorded_at', y='temperature', title='Temperature (°C)', line_shape='spline')
        fig_temp.update_traces(line_color='#FF4B4B') # Red
        fig_temp.update_layout(xaxis_title=None, yaxis_title=None, height=350)
        st.plotly_chart(fig_temp, key="temp_chart", on_select="ignore") 
        # Note: If 'width' parameter gives errors, remove it. Streamlit handles column width automatically.

    with row1_col2:
        fig_hum = px.line(df, x='recorded_at', y='humidity', title='Humidity (%)', line_shape='spline')
        fig_hum.update_traces(line_color='#1E90FF') # Blue
        fig_hum.update_layout(xaxis_title=None, yaxis_title=None, height=350)
        st.plotly_chart(fig_hum, key="hum_chart", on_select="ignore")

    # ROW 2: Pressure & Light
    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        fig_pres = px.area(df, x='recorded_at', y='pressure', title='Pressure (hPa)', line_shape='hv')
        fig_pres.update_traces(line_color='#FFA500') # Orange
        fig_pres.update_layout(xaxis_title=None, yaxis_title=None, height=350)
        st.plotly_chart(fig_pres, key="pres_chart", on_select="ignore")

    with row2_col2:
        # Added the missing Light Chart here!
        fig_light = px.area(df, x='recorded_at', y='light', title='Light Level', line_shape='hv')
        fig_light.update_traces(line_color='#F7DC6F') # Yellow
        fig_light.update_layout(xaxis_title=None, yaxis_title=None, height=350)
        st.plotly_chart(fig_light, key="light_chart", on_select="ignore")

else:
    st.warning("No data found in the database yet.")