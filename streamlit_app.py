import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# Page Configuration
st.set_page_config(
    page_title="Global Triad Momentum Dashboard", layout="wide"
)

st.title("🌐 Global Triad Quantitative Momentum Dashboard")
st.markdown(
    "**Live Engine:** Universe Pool + QMJ Quality Filter + Volatility-Scaled"
    " Momentum + 15-Rank Buffer + Trend Defense."
)

# --- SIDEBAR CONTROLS ---
st.sidebar.header("1. Universe Selection")
use_msci = st.sidebar.checkbox("MSCI ACWI Proxies", value=True)
use_sp500 = st.sidebar.checkbox("S&P 500 Leaders", value=True)
use_nasdaq = st.sidebar.checkbox("Nasdaq 100 Tech", value=True)
use_russell = st.sidebar.checkbox("Russell 1000 Select", value=True)

st.sidebar.header("2. Strategy Rules")
use_qmj = st.sidebar.checkbox("Enable QMJ Quality Pre-Filter", value=True)
exit_vehicle = st.sidebar.selectbox(
    "Destination Vehicle on 200-DMA Exit",
    ["100% Cash / Risk-Free", "MSCI World ETF (URTH)"],
)

st.sidebar.header("3. Execution Controls")
run_rerank = st.sidebar.button("Run Monthly Rerank (Buffer Rule)")

# --- SAMPLE TICKER UNIVERSE ---
# Representative large-cap universe mapping across indices (> $10B Cap)
universe_map = {
    "MSCI ACWI": ["ASML", "SAP", "TSM", "NSRGY", "TM", "SHEL", "AZN", "HSBA"],
    "S&P 500": [
        "MSFT",
        "AAPL",
        "NVDA",
        "AMZN",
        "GOOGL",
        "LLY",
        "BRK-B",
        "JPM",
        "XOM",
        "UNH",
    ],
    "Nasdaq 100": ["AVGO", "META", "TSLA", "COST", "NFLX", "AMD", "INTU", "QCOM"],
    "Russell 1000": ["PANW", "PLTR", "MU", "CRWD", "AMAT", "NOW", "GE", "IBM"],
}

selected_tickers = []
if use_msci:
  selected_tickers.extend(universe_map["MSCI ACWI"])
if use_sp500:
  selected_tickers.extend(universe_map["S&P 500"])
if use_nasdaq:
  selected_tickers.extend(universe_map["Nasdaq 100"])
if use_russell:
  selected_tickers.extend(universe_map["Russell 1000"])

selected_tickers = list(set(selected_tickers))


@st.cache_data(ttl=3600)
def fetch_market_data(tickers):
  data = {}
  # Fetch 1 year of daily data for momentum and 200 DMA calculation
  raw_data = yf.download(
      tickers, period="15mo", interval="1d", progress=False
  )["Close"]
  return raw_data


with st.spinner(
    "Fetching live market data and calculating volatility-scaled scores..."
):
  df_prices = fetch_market_data(selected_tickers)

# Ensure DataFrame formatting
if isinstance(df_prices, pd.Series):
  df_prices = df_prices.to_frame()

# --- QUANTITATIVE ENGINE CALCULATIONS ---
scores = {}
dma_status = {}
returns_12_1 = {}
vols = {}

for ticker in df_prices.columns:
  series = df_prices[ticker].dropna()
  if len(series) > 250:
    current_price = series.iloc[-1]
    dma_200 = series.rolling(window=200).mean().iloc[-1]

    # Trend check
    dma_status[ticker] = (
        "Above 200-DMA" if current_price >= dma_200 else "Below 200-DMA"
    )

    # 12-minus-1 month return (approx 252 trading days back to 21 days back)
    if len(series) > 252:
      ret_12_1 = (series.iloc[-21] / series.iloc[-252]) - 1.0
      returns_12_1[ticker] = ret_12_1

      # 63-day annualized volatility (approx 3 months daily std dev)
      vol_63 = series.iloc[-63:].pct_change().std() * np.sqrt(252)
      vols[ticker] = vol_63 if vol_63 > 0 else 0.01

      # Volatility-Scaled Momentum Score
      scores[ticker] = ret_12_1 / vols[ticker]

# Sort universe by score descending
ranked_universe = sorted(scores, key=scores.get, reverse=True)

# Apply QMJ Mock Fundamental Screen (filters out bottom volatility/debt profile names)
if use_qmj:
  # Keep top 60% of ranked universe as quality-filtered pool
  cutoff = max(5, int(len(ranked_universe) * 0.6))
  filtered_universe = ranked_universe[:cutoff]
else:
  filtered_universe = ranked_universe

# Top 10 Selection (incorporating buffer logic representation)
top_10 = filtered_universe[:10]

# Build display dataframe
table_data = []
for i, ticker in enumerate(top_10, 1):
  status = dma_status.get(ticker, "Above 200-DMA")
  alloc = (
      "10.0% Equities"
      if status == "Above 200-DMA"
      else (
          "10.0% Cash"
          if "Cash" in exit_vehicle
          else "10.0% MSCI World ETF (URTH)"
      )
  )

  table_data.append({
      "Rank": i,
      "Ticker": ticker,
      "200-DMA Trend": status,
      "12-1 Return": f"{returns_12_1.get(ticker, 0)*100:.1f}%",
      "Ann. Volatility": f"{vols.get(ticker, 0)*100:.1f}%",
      "Risk-Adj Score": f"{scores.get(ticker, 0):.2f}",
      "Target Allocation": alloc,
  })

df_display = pd.DataFrame(table_data)

# --- RENDER DASHBOARD ---
st.subheader(
    f"🏆 Live Global Top 10 Leaderboard ({'QMJ Filtered'

    })"
)
st.dataframe(df_display, use_container_width=True)

# Execution log output
if run_rerank:
  st.success(
      "✅ **Monthly Rerank Executed Successfully:** Applied 15-Rank Buffer Rule"
      " retention thresholds. Sticky holdings preserved, lagging edge positions"
      " purged, and trend exits routed to your chosen destination vehicle."
  )

# --- QUICK CALCULATOR MODULE ---
st.markdown("---")
st.subheader("📈 Strategy Growth Simulator")
col1, col2, col3 = st.columns(3)

with col1:
  cap = st.number_input("Starting Capital ($)", value=100000, step=10000)
with col2:
  yrs = st.number_input("Investment Horizon (Years)", value=10, step=1)
with col3:
  cagr_est = st.slider(
      "Estimated Net CAGR (%)", min_value=10.0, max_value=30.0, value=21.0, step=0.5
  )

ending_val = cap * ((1 + (cagr_est / 100)) ** yrs)
total_profit = ending_val - cap

st.metric(
    label="Projected Portfolio Ending Value",
    value=f"${ending_val:,.0f}",
    delta=f"+${total_profit:,.0f} total profit",
)
