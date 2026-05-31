import os

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import psycopg2
import streamlit as st
import torch
import torch.nn as nn
from dotenv import load_dotenv
from plotly.subplots import make_subplots

load_dotenv()

# ── Constants (must match training) ───────────────────────────────────────────
FEATURES = ["light", "humidity", "temperature", "pressure"]
TARGETS  = ["temperature", "humidity"]
WINDOW   = 72   # 6 h input
HORIZON  = 12   # 1 h forecast

# ── Model definition ──────────────────────────────────────────────────────────
class WeatherLSTM(nn.Module):
    def __init__(self, n_features, n_targets, horizon,
                 hidden=64, hidden2=32, dropout=0.2):
        super().__init__()
        self.lstm1 = nn.LSTM(n_features, hidden,  batch_first=True)
        self.drop1 = nn.Dropout(dropout)
        self.lstm2 = nn.LSTM(hidden,     hidden2, batch_first=True)
        self.drop2 = nn.Dropout(dropout)
        self.head  = nn.Linear(hidden2, horizon * n_targets)
        self.horizon, self.n_targets = horizon, n_targets

    def forward(self, x):
        x, _ = self.lstm1(x)
        x     = self.drop1(x)
        x, _ = self.lstm2(x)
        x     = self.drop2(x[:, -1, :])
        return self.head(x).view(-1, self.horizon, self.n_targets)


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Weather Station", page_icon="🌤️", layout="wide")

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 2.5rem; }
    .main .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)


# ── Cached resources ──────────────────────────────────────────────────────────
@st.cache_resource
def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
    )


@st.cache_resource
def load_model_and_scaler():
    try:
        scaler = joblib.load("models/scaler.pkl")
        model  = WeatherLSTM(len(FEATURES), len(TARGETS), HORIZON)
        model.load_state_dict(torch.load("models/weather_lstm.pt", map_location="cpu"))
        model.eval()
        return model, scaler
    except Exception:
        return None, None


# ── Data fetching ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_data(limit=10_000):
    try:
        conn = get_db_connection()
        if conn.closed:
            st.cache_resource.clear()
            conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f"""
            SELECT recorded_at, temperature, humidity, light, pressure
            FROM sensors_data
            ORDER BY recorded_at DESC
            LIMIT {limit};
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        cur.close()
        df = pd.DataFrame(rows, columns=cols)
        df["recorded_at"] = pd.to_datetime(df["recorded_at"])
        return df.sort_values("recorded_at").reset_index(drop=True)
    except Exception as e:
        st.error(f"DB error: {e}")
        return pd.DataFrame()


# ── Forecast ──────────────────────────────────────────────────────────────────
def run_forecast(df, model, scaler):
    """
    Takes the last WINDOW rows, runs the LSTM, returns a DataFrame with
    HORIZON future rows containing predicted temperature and humidity.
    Returns None if there isn't enough data.
    """
    if len(df) < WINDOW:
        return None

    window_df = df.tail(WINDOW)[FEATURES].copy()
    if window_df.isnull().any().any():
        return None

    x = scaler.transform(window_df).astype(np.float32)
    x_tensor = torch.tensor(x).unsqueeze(0)  # (1, WINDOW, 4)

    with torch.no_grad():
        pred = model(x_tensor).squeeze(0).numpy()  # (HORIZON, 2)

    tgt_idx     = [FEATURES.index(t) for t in TARGETS]
    target_mean = scaler.mean_[tgt_idx]
    target_std  = scaler.scale_[tgt_idx]
    pred_real   = pred * target_std + target_mean

    # Clip humidity to physical range
    hum_col = TARGETS.index("humidity")
    pred_real[:, hum_col] = np.clip(pred_real[:, hum_col], 0, 100)

    last_ts = df["recorded_at"].iloc[-1]
    future_ts = [last_ts + pd.Timedelta(minutes=5 * (i + 1)) for i in range(HORIZON)]

    return pd.DataFrame({
        "recorded_at": future_ts,
        "temperature": pred_real[:, TARGETS.index("temperature")],
        "humidity":    pred_real[:, hum_col],
    })


# ── Plotly helpers ────────────────────────────────────────────────────────────
RANGE_BUTTONS = [
    dict(count=1,  label="1h",  step="hour",  stepmode="backward"),
    dict(count=6,  label="6h",  step="hour",  stepmode="backward"),
    dict(count=1,  label="1d",  step="day",   stepmode="backward"),
    dict(count=7,  label="1w",  step="day",   stepmode="backward"),
    dict(count=1,  label="1M",  step="month", stepmode="backward"),
    dict(step="all", label="All"),
]


def add_range_controls(fig, row=1):
    fig.update_xaxes(
        rangeselector=dict(buttons=RANGE_BUTTONS, bgcolor="#2d2d2d",
                           activecolor="#555", font=dict(color="white")),
        rangeslider=dict(visible=True, thickness=0.05),
        row=row, col=1,
    )


# ── Layout ────────────────────────────────────────────────────────────────────
st.title("🌤️ Weather Station")

col_refresh, col_note = st.columns([1, 8])
with col_refresh:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()

df = get_data()
model, scaler = load_model_and_scaler()

if df.empty:
    st.warning("No data available.")
    st.stop()

latest      = df.iloc[-1]
target_24h  = latest["recorded_at"] - pd.Timedelta(hours=24)
idx_24h     = (df["recorded_at"] - target_24h).abs().idxmin()
previous    = df.loc[idx_24h]

# ── KPIs ──────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("🌡 Temperature", f"{latest['temperature']:.1f} °C",
          f"{latest['temperature'] - previous['temperature']:+.1f} °C")
c2.metric("💧 Humidity",    f"{latest['humidity']:.1f} %",
          f"{latest['humidity'] - previous['humidity']:+.1f} %")
c3.metric("🔵 Pressure",   f"{latest['pressure']:.1f} hPa",
          f"{latest['pressure'] - previous['pressure']:+.1f}")
c4.metric("☀️ Light",      f"{latest['light']:.0f}",
          f"{latest['light'] - previous['light']:+.0f}")

st.markdown("---")

# ── Forecast section ──────────────────────────────────────────────────────────
st.subheader("1-Hour Forecast")

if model is None:
    st.info("Model not found — run the training notebook first.")
else:
    forecast_df = run_forecast(df, model, scaler)

    if forecast_df is None:
        st.warning("Not enough recent data to generate a forecast.")
    else:
        # Show last 6 h of actual + 1 h forecast
        actual_window = df.tail(WINDOW)

        fig_fc = make_subplots(rows=2, cols=1, shared_xaxes=True,
                               subplot_titles=("Temperature (°C)", "Humidity (%)"),
                               vertical_spacing=0.08)

        for row, col, color, fc_color in [
            (1, "temperature", "#FF4B4B", "#FF9999"),
            (2, "humidity",    "#1E90FF", "#87CEEB"),
        ]:
            # Actual line
            fig_fc.add_trace(go.Scatter(
                x=actual_window["recorded_at"], y=actual_window[col],
                name=f"{col} (actual)", line=dict(color=color, width=2),
                showlegend=(row == 1),
            ), row=row, col=1)

            # Forecast — connect smoothly from last actual point
            fc_x = [actual_window["recorded_at"].iloc[-1]] + list(forecast_df["recorded_at"])
            fc_y = [actual_window[col].iloc[-1]]           + list(forecast_df[col])
            fig_fc.add_trace(go.Scatter(
                x=fc_x, y=fc_y,
                name=f"{col} (forecast)",
                line=dict(color=fc_color, width=2, dash="dash"),
                showlegend=(row == 1),
            ), row=row, col=1)

        # Vertical "now" line via add_shape (add_vline has annotation bugs on datetime axes)
        now = df["recorded_at"].iloc[-1]
        fig_fc.add_shape(type="line", x0=now, x1=now, y0=0, y1=1,
                         xref="x", yref="paper",
                         line=dict(dash="dot", color="gray", width=1))
        fig_fc.add_annotation(x=now, y=1, xref="x", yref="paper",
                              text="now", showarrow=False,
                              xanchor="left", yanchor="top",
                              font=dict(color="gray", size=11))

        fig_fc.update_layout(height=420, margin=dict(t=40, b=10),
                             legend=dict(orientation="h", y=-0.12))
        st.plotly_chart(fig_fc, use_container_width=True)

        fc_end = forecast_df["recorded_at"].iloc[-1].strftime("%H:%M")
        st.caption(f"Forecast horizon: next 60 min · up to {fc_end}")

st.markdown("---")

# ── Historical charts ─────────────────────────────────────────────────────────
st.subheader("Historical Data")

fig = make_subplots(
    rows=4, cols=1,
    shared_xaxes=True,
    subplot_titles=("Temperature (°C)", "Humidity (%)", "Pressure (hPa)", "Light"),
    vertical_spacing=0.06,
)

traces = [
    ("temperature", "#FF4B4B"),
    ("humidity",    "#1E90FF"),
    ("pressure",    "#FFA500"),
    ("light",       "#F7DC6F"),
]

for row, (col, color) in enumerate(traces, start=1):
    fig.add_trace(go.Scatter(
        x=df["recorded_at"], y=df[col],
        name=col, line=dict(color=color, width=1.2),
        hovertemplate="%{x|%Y-%m-%d %H:%M}<br>%{y:.2f}<extra></extra>",
    ), row=row, col=1)

# Range selector + slider on top x-axis
fig.update_layout(
    xaxis=dict(
        rangeselector=dict(
            buttons=RANGE_BUTTONS,
            bgcolor="#2d2d2d",
            activecolor="#555",
            font=dict(color="white"),
        ),
    ),
    # Rangeslider on the bottom x-axis (xaxis4)
    xaxis4=dict(rangeslider=dict(visible=True, thickness=0.04)),
    height=900,
    showlegend=False,
    margin=dict(t=40, b=20),
    hovermode="x unified",
)

st.plotly_chart(fig, use_container_width=True)
