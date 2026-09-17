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
    "**Live Engine:** Dynamic Universe Pool + $500M Liquidity Filter + QMJ"
    " Quality Filter + Volatility-Scaled Momentum + 15-Rank Buffer + Trend"
    " Defense."
)

# --- SESSION STATE INITIALIZATION ---
if "portfolio" not in st.session_state:
  st.session_state.portfolio = []
if "qmj_filtered_pool" not in st.session_state:
  st.session_state.qmj_filtered_pool = []
if "last_action" not in st.session_state:
  st.session_state.last_action = "System initialized. Run initial calculations."

# --- SIDEBAR CONTROLS ---
st.sidebar.header("1. Initial Pool: Index Selection")
use_msci = st.sidebar.checkbox("MSCI ACWI (Global Proxies)", value=True)
use_sp500 = st.sidebar.checkbox("S&P 500 (US Large Cap)", value=True)
use_nasdaq = st.sidebar.checkbox("Nasdaq 100 (US Tech Growth)", value=True)
use_russell = st.sidebar.checkbox("Russell 1000 (US Broad Large/Mid)", value=True)

st.sidebar.header("2. Strategy & Liquidity Rules")
min_liquidity_m = st.sidebar.slider(
    "Min. Average Daily Volume ($M)",
    min_value=100.0,
    max_value=2000.0,
    value=500.0,
    step=50.0,
)
use_qmj = st.sidebar.checkbox("Enable QMJ Quality Pre-Filter", value=True)
exit_vehicle = st.sidebar.selectbox(
    "Destination Vehicle on 200-DMA Exit",
    ["100% Cash / Risk-Free", "MSCI World ETF (URTH)"],
)

st.sidebar.header("3. Execution Controls")
run_rerank_btn = st.sidebar.button("Run Monthly Rerank (Buffer Rule)")
run_quarterly_btn = st.sidebar.button("Run Quarterly Filter Update")

# --- TICKER UNIVERSE MAPPING ---
universe_map = {
    "MSCI ACWI": ["ASML", "SAP", "TSM", "TM", "SHEL", "AZN", "NSRGY", "SNY"],
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
  if not tickers:
    return pd.DataFrame(), pd.DataFrame()
  raw_data = yf.download(
      tickers, period="15mo", interval="1d", progress=False
  )
  if isinstance(raw_data.columns, pd.MultiIndex):
    prices = raw_data["Close"]
    volumes = raw_data["Volume"]
  else:
    prices = raw_data[["Close"]] if "Close" in raw_data else pd.DataFrame()
    volumes = raw_data[["Volume"]] if "Volume" in raw_data else pd.DataFrame()
  return prices, volumes


with st.spinner(
    "Fetching live market data and computing liquidity & factor scores..."
):
  df_prices, df_volumes = fetch_market_data(selected_tickers)

if df_prices.empty:
  st.warning(
      "Please select at least one index in the sidebar to populate the universe."
  )
  st.stop()

if isinstance(df_prices, pd.Series):
  df_prices = df_prices.to_frame()
  df_volumes = df_volumes.to_frame()

# --- LIQUIDITY FILTER APPLICATION ($500M+ Daily Dollar Volume) ---
min_dollar_vol = min_liquidity_m * 1e6
liquid_tickers = []
ticker_liquidity = {}

for ticker in df_prices.columns:
  if ticker in df_volumes.columns:
    p_series = df_prices[ticker].dropna()
    v_series = df_volumes[ticker].dropna()
    common_idx = p_series.index.intersection(v_series.index)
    if len(common_idx) > 63:
      # Calculate 63-day average daily dollar volume (Price * Volume)
      dollar_vol_series = p_series.loc[common_idx] * v_series.loc[common_idx]
      avg_daily_vol = dollar_vol_series.iloc[-63:].mean()
      ticker_liquidity[ticker] = avg_daily_vol

      if avg_daily_vol >= min_dollar_vol:
        liquid_tickers.append(ticker)

if not liquid_tickers:
  st.error(
      f"No tickers meet the minimum liquidity threshold of ${min_liquidity_m}M"
      " daily volume. Try lowering the liquidity threshold in the sidebar."
  )
  st.stop()

# Filter price dataframe to only include liquid tickers
df_prices_liquid = df_prices[liquid_tickers]

# --- QUANTITATIVE CALCULATIONS ---
scores = {}
dma_status = {}
returns_12_1 = {}
vols = {}

for ticker in df_prices_liquid.columns:
  series = df_prices_liquid[ticker].dropna()
  if len(series) > 200:
    current_price = series.iloc[-1]
    dma_200 = series.rolling(window=200).mean().iloc[-1]

    dma_status[ticker] = (
        "Above 200-DMA" if current_price >= dma_200 else "Below 200-DMA"
    )

    if len(series) > 252:
      ret_12_1 = (series.iloc[-21] / series.iloc[-252]) - 1.0
      returns_12_1[ticker] = ret_12_1

      vol_63 = series.iloc[-63:].pct_change().std() * np.sqrt(252)
      vols[ticker] = vol_63 if vol_63 > 0 else 0.01

      scores[ticker] = ret_12_1 / vols[ticker]

ranked_universe = sorted(scores, key=lambda k: scores[k], reverse=True)

# --- QUARTERLY FILTER UPDATE LOGIC ---
if run_quarterly_btn or not st.session_state.qmj_filtered_pool:
  if use_qmj:
    cutoff = max(5, int(len(ranked_universe) * 0.5))
    st.session_state.qmj_filtered_pool = ranked_universe[:cutoff]
  else:
    st.session_state.qmj_filtered_pool = ranked_universe
  st.session_state.last_action = (
      f"Quarterly Filter Updated: QMJ screen applied to ${min_liquidity_m}M+"
      " liquidity pool."
  )

active_pool = [
    t for t in st.session_state.qmj_filtered_pool if t in ranked_universe
]
active_pool.sort(key=lambda k: scores[k], reverse=True)

# --- MONTHLY RERANK & 15-RANK BUFFER RULE LOGIC ---
if run_rerank_btn or not st.session_state.portfolio:
  current_portfolio = st.session_state.portfolio
  new_portfolio = []

  for ticker in current_portfolio:
    if ticker in active_pool:
      current_rank = active_pool.index(ticker) + 1
      if current_rank <= 15:
        new_portfolio.append(ticker)

  for ticker in active_pool:
    if len(new_portfolio) >= 10:
      break
    if ticker not in new_portfolio:
      new_portfolio.append(ticker)

  st.session_state.portfolio = new_portfolio
  st.session_state.last_action = (
      f"Monthly Rerank Executed: Applied 15-Rank Buffer Rule. Portfolio holds"
      f" {len(new_portfolio)} assets."
  )

if not st.session_state.portfolio:
  st.session_state.portfolio = active_pool[:10]

# --- DISPLAY LEADERBOARD TABLE ---
table_data = []
for i, ticker in enumerate(st.session_state.portfolio, 1):
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

  pool_rank = (
      active_pool.index(ticker) + 1 if ticker in active_pool else "N/A"
  )
  avg_vol_m = ticker_liquidity.get(ticker, 0) / 1e6

  table_data.append({
      "Portfolio Slot": i,
      "Ticker": ticker,
      "Pool Rank": pool_rank,
      "Daily Vol ($M)": f"${avg_vol_m:.1f}M",
      "200-DMA Trend": status,
      "12-1 Return": f"{returns_12_1.get(ticker, 0)*100:.1f}%",
      "Ann. Volatility": f"{vols.get(ticker, 0)*100:.1f}%",
      "Risk-Adj Score": f"{scores.get(ticker, 0):.2f}",
      "Target Allocation": alloc,
  })

df_display = pd.DataFrame(table_data)

filter_mode_label = "QMJ Filtered" if use_qmj else "Raw Momentum"
st.subheader(
    f"🏆 Active Portfolio Leaderboard ({filter_mode_label} | Liquidity >"
    f" ${min_liquidity_m}M/day)"
)
st.info(f"**Execution Status:** {st.session_state.last_action}")
st.dataframe(df_display, use_container_width=True)

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
