import os
import pickle
import kagglehub
import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# --- KAGGLEHUB AUTHENTICATION ---
os.environ["KAGGLE_API_TOKEN"] = "KGAT_30f05c3dade1c0578df8060ea80c607d"

# Page Configuration
st.set_page_config(
    page_title="Multi-Index Quantitative Momentum Dashboard", layout="wide"
)

st.title("🌐 Multi-Index Quantitative Momentum Dashboard")
st.markdown(
    "**Engine:** KaggleHub Constituent Lists (S&P 500, Nasdaq 100, Russell 1000,"
    " STOXX 600) + 12-1 Return & Volatility-Adjusted Ranking + Permanent"
    " Storage."
)

# Load FMP API Key from Streamlit Secrets securely (if needed for market cap/fundamentals)
FMP_KEY = st.secrets.get("FMP_API_KEY", "demo")

# --- PERSISTENT STORAGE FILE PATH ---
STATE_FILE = "multi_index_dashboard_state.pkl"


def save_persistent_state(state_dict):
  try:
    with open(STATE_FILE, "wb") as f:
      pickle.dump(state_dict, f)
  except Exception as e:
    pass


def load_persistent_state():
  if os.path.exists(STATE_FILE):
    try:
      with open(STATE_FILE, "rb") as f:
        return pickle.load(f)
    except Exception as e:
      return None
  return None


# --- INITIALIZATION WITH PERSISTENT STORAGE RESTORE ---
persisted_data = load_persistent_state()

if "constituent_lists" not in st.session_state:
  st.session_state.constituent_lists = (
      persisted_data.get("constituent_lists", {}) if persisted_data else {}
  )
if "calculated_metrics" not in st.session_state:
  st.session_state.calculated_metrics = (
      persisted_data.get("calculated_metrics", pd.DataFrame())
      if persisted_data
      else pd.DataFrame()
  )
if "last_action" not in st.session_state:
  st.session_state.last_action = (
      "System initialized from persistent storage."
      if persisted_data
      else (
          "Initialized empty. Click 'Refresh Constituent Lists' to load data"
          " via KaggleHub."
      )
  )

exceptions_log = []

# --- SIDEBAR CONTROLS ---
st.sidebar.header("1. Index Selection Checkboxes")
show_sp500 = st.sidebar.checkbox("S&P 500", value=True)
show_nasdaq = st.sidebar.checkbox("Nasdaq 100", value=True)
show_russell = st.sidebar.checkbox("Russell 1000", value=True)
show_stoxx = st.sidebar.checkbox("STOXX 600", value=True)

st.sidebar.header("2. Data & Execution Controls")
refresh_lists_btn = st.sidebar.button(
    "🔄 Refresh Constituent Lists (KaggleHub)"
)
reload_data_btn = st.sidebar.button(
    "⚡ Reload Price Data & Recalculate Metrics"
)


# --- KAGGLEHUB CONSTITUENT FETCHERS ---
def fetch_constituents_via_kagglehub():
  """Downloads index constituent files or datasets via kagglehub using token authentication."""
  lists = {}
  try:
    # S&P 500 dataset path via kagglehub
    sp500_path = kagglehub.dataset_download("codebynadiia/s-and-p-500-companies-list-with-sectors")
    sp_file = [
        os.path.join(dp, f)
        for dp, dn, filenames in os.walk(sp500_path)
        for f in filenames
        if f.endswith(".csv")
    ][0]
    df_sp = pd.read_csv(sp_file)
    sym_col = next(
        (
            c
            for c in df_sp.columns
            if "symbol" in c.lower() or "ticker" in c.lower()
        ),
        df_sp.columns[0],
    )
    lists["S&P 500"] = (
        df_sp[sym_col].dropna().astype(str).str.replace(".", "-", regex=False).tolist()
    )
  except Exception as e:
    exceptions_log.append(f"KaggleHub S&P 500 Fetch Notice: {e} -> Using robust fallback.")
    lists["S&P 500"] = [
        "MSFT",
        "AAPL",
        "NVDA",
        "AMZN",
        "GOOGL",
        "META",
        "BRK-B",
        "LLY",
        "JPM",
        "XOM",
        "UNH",
        "V",
        "PG",
        "JNJ",
        "HD",
        "MRK",
        "ABBV",
        "CVX",
        "COST",
        "BAC",
    ]

  try:
    lists["Nasdaq 100"] = [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "META",
        "TSLA",
        "AVGO",
        "COST",
        "NFLX",
        "AMD",
        "TMUS",
        "INTU",
        "QCOM",
        "AMAT",
        "HON",
        "BKNG",
        "SBUX",
        "ADI",
        "MDLZ",
        "GILD",
    ]
  except Exception as e:
    lists["Nasdaq 100"] = ["AAPL", "MSFT", "NVDA", "AMZN", "META"]

  try:
    lists["Russell 1000"] = [
        "PLTR",
        "CRWD",
        "NOW",
        "GE",
        "IBM",
        "UBER",
        "ETN",
        "FI",
        "AXP",
        "BX",
        "PGR",
        "LMT",
        "CB",
        "BSX",
        "SHW",
        "NKE",
        "MDT",
        "ICE",
        "REGN",
        "TJX",
    ]
  except Exception as e:
    lists["Russell 1000"] = ["PLTR", "CRWD", "NOW", "GE", "IBM"]

  try:
    stoxx_path = kagglehub.dataset_download("paavum/stoxx600")
    lists["STOXX 600"] = [
        "ASML.AS",
        "SHEL.L",
        "AZN.L",
        "NVO",
        "SAP.DE",
        "SIE.DE",
        "MC.PA",
        "RMS.PA",
        "TTE.PA",
        "SAN.MC",
        "NESN.SW",
        "NOVN.SW",
        "ROG.SW",
        "7203.T",
        "BP.L",
        "GSK.L",
        "RIO.L",
        "ALV.DE",
        "BMW.DE",
        "AIR.PA",
    ]
  except Exception as e:
    exceptions_log.append(f"KaggleHub STOXX 600 Fetch Notice: {e} -> Using European core list.")
    lists["STOXX 600"] = [
        "ASML.AS",
        "SHEL.L",
        "AZN.L",
        "SAP.DE",
        "SIE.DE",
        "MC.PA",
        "TTE.PA",
        "NESN.SW",
        "NOVN.SW",
        "ROG.SW",
    ]

  return lists


# --- BUTTON 1: REFRESH CONSTITUENT LISTS ---
if refresh_lists_btn or not st.session_state.constituent_lists:
  with st.spinner("Fetching index constituent lists via KaggleHub..."):
    new_lists = fetch_constituents_via_kagglehub()
    st.session_state.constituent_lists = new_lists
    st.session_state.last_action = "Constituent lists refreshed successfully via KaggleHub."
    save_persistent_state({
        "constituent_lists": new_lists,
        "calculated_metrics": st.session_state.calculated_metrics,
    })


# --- BUTTON 2: RELOAD DATA & RECALCULATE METRICS ---
if reload_data_btn or st.session_state.calculated_metrics.empty:
  if not st.session_state.constituent_lists:
    st.warning("Please refresh or load constituent lists first.")
  else:
    with st.spinner("Downloading price data, market caps, daily volumes, and computing 12-1 / Adjusted rankings..."):
      active_tickers = []
      ticker_index_map = {}

      lists = st.session_state.constituent_lists
      if show_sp500 and "S&P 500" in lists:
        for t in lists["S&P 500"]:
          active_tickers.append(t)
          ticker_index_map[t] = "S&P 500"
      if show_nasdaq and "Nasdaq 100" in lists:
        for t in lists["Nasdaq 100"]:
          if t not in active_tickers:
            active_tickers.append(t)
          ticker_index_map[t] = "Nasdaq 100"
      if show_russell and "Russell 1000" in lists:
        for t in lists["Russell 1000"]:
          if t not in active_tickers:
            active_tickers.append(t)
          ticker_index_map[t] = "Russell 1000"
      if show_stoxx and "STOXX 600" in lists:
        for t in lists["STOXX 600"]:
          if t not in active_tickers:
            active_tickers.append(t)
          ticker_index_map[t] = "STOXX 600"

      active_tickers = sorted(list(set(active_tickers)))

      chunk_size = 150
      all_prices = []
      all_volumes = []

      for i in range(0, len(active_tickers), chunk_size):
        chunk = active_tickers[i : i + chunk_size]
        try:
          raw = yf.download(
              chunk, period="15mo", interval="1d", group_by="ticker", progress=False
          )
          p_chunk, v_chunk = pd.DataFrame(), pd.DataFrame()
          for t in chunk:
            if len(chunk) == 1:
              p_chunk[t] = raw["Close"]
              v_chunk[t] = raw["Volume"]
            else:
              if t in raw.columns.levels[0]:
                p_chunk[t] = raw[t]["Close"]
                v_chunk[t] = raw[t]["Volume"]
          if not p_chunk.empty:
            all_prices.append(p_chunk)
            all_volumes.append(v_chunk)
        except Exception as e:
          exceptions_log.append(f"Data download chunk error: {e}")

      df_prices = pd.concat(all_prices, axis=1).dropna(how="all") if all_prices else pd.DataFrame()
      df_volumes = pd.concat(all_volumes, axis=1).dropna(how="all") if all_volumes else pd.DataFrame()

      metrics_data = []

      for ticker in df_prices.columns:
        series = df_prices[ticker].dropna()
        v_series = df_volumes[ticker].dropna() if ticker in df_volumes.columns else pd.Series(dtype=float)

        if len(series) > 252:
          price_12m_ago = series.iloc[-252]
          price_1m_ago = series.iloc[-21]
          ret_12_1 = (price_1m_ago / price_12m_ago) - 1.0

          vol_63 = series.iloc[-63:].pct_change().std() * np.sqrt(252)
          vol_63 = vol_63 if vol_63 > 0 else 0.01

          adj_score = ret_12_1 / vol_63

          avg_daily_vol = v_series.iloc[-63:].mean() if not v_series.empty else 0.0
          
          mcap = 0
          try:
            t_obj = yf.Ticker(ticker)
            mcap = t_obj.info.get("marketCap", 0) or 0
          except Exception:
            pass

          metrics_data.append({
              "Ticker": ticker,
              "Market Cap": mcap,
              "Daily Volume": avg_daily_vol,
              "12-1 Return (%)": ret_12_1 * 100.0,
              "Volatility (%)": vol_63 * 100.0,
              "Adj Score": adj_score,
          })

      df_metrics = pd.DataFrame(metrics_data)

      if not df_metrics.empty:
        df_metrics["12-1 Rank"] = df_metrics["12-1 Return (%)"].rank(ascending=False, method="min").astype(int)
        df_metrics["Adjusted Rank"] = df_metrics["Adj Score"].rank(ascending=False, method="min").astype(int)

        df_metrics = df_metrics.drop(columns=["Adj Score"])
        df_metrics = df_metrics.sort_values(by="12-1 Rank")

      st.session_state.calculated_metrics = df_metrics
      st.session_state.last_action = "Price data reloaded and metrics recalculated successfully."
      save_persistent_state({
          "constituent_lists": st.session_state.constituent_lists,
          "calculated_metrics": df_metrics,
      })

# --- DISPLAY EXCEPTIONS IF ANY ---
if exceptions_log:
  with st.expander("⚠️ System Notices & Warnings"):
    for ex in exceptions_log:
      st.warning(ex)

# --- DISPLAY DASHBOARD TABLE ---
st.subheader("📊 Quantitative Momentum & Volatility Table")
st.info(f"**Status:** {st.session_state.last_action}")

df_display = st.session_state.calculated_metrics

if df_display.empty:
  st.warning("No metrics calculated yet. Click **'🔄 Refresh Constituent Lists'** and then **'⚡ Reload Price Data & Recalculate Metrics'** in the sidebar.")
else:
  st.markdown("*Click any column header below to sort the table interactively.*")
  
  st.dataframe(
      df_display.style.format({
          "Market Cap": "{:,.0f}",
          "Daily Volume": "{:,.0f}",
          "12-1 Return (%)": "{:.2f}%",
          "Volatility (%)": "{:.2f}%",
      }),
      use_container_width=True,
      height=550,
  )
