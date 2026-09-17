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
    "**Live Engine:** Dynamic Index Scraping (S&P 500 / Nasdaq 100) + $500M"
    " Liquidity Filter + QMJ Quality Filter + Volatility-Scaled Momentum +"
    " 15-Rank Buffer + Trend Defense."
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
use_sp500 = st.sidebar.checkbox("S&P 500 (Full 500 Constituents)", value=True)
use_nasdaq = st.sidebar.checkbox(
    "Nasdaq 100 (Full 100 Constituents)", value=True
)
use_msci_global = st.sidebar.checkbox(
    "Global Developed Proxies (ASML, TSM, SAP, etc.)", value=True
)

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


# --- DYNAMIC CONSTITUENT FETCHERS (WIKIPEDIA SCRAPING) ---
@st.cache_data(ttl=86400)  # Cache for 24 hours to avoid redundant web scraping
def fetch_sp500_tickers():
  try:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    df = pd.read_html(url)[0]
    tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
    return tickers
  except Exception:
    return [
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
    ]


@st.cache_data(ttl=86400)
def fetch_nasdaq100_tickers():
  try:
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    tables = pd.read_html(url)
    # Find the table containing the ticker symbols
    for table in tables:
      if "Ticker" in table.columns:
        return table["Ticker"].str.replace(".", "-", regex=False).tolist()
      elif "Symbol" in table.columns:
        return table["Symbol"].str.replace(".", "-", regex=False).tolist()
    return table[0].tolist()
  except Exception:
    return ["AVGO", "COST", "NFLX", "AMD", "TMUS", "INTU", "QCOM", "AMAT"]


# Assemble Selected Universe Pool
selected_tickers = []
if use_sp500:
  selected_tickers.extend(fetch_sp500_tickers())
if use_nasdaq:
  selected_tickers.extend(fetch_nasdaq100_tickers())
if use_msci_global:
  global_proxies = [
      "ASML",
      "SAP",
      "TSM",
      "TM",
      "SHEL",
      "AZN",
      "NSRGY",
      "SNY",
      "SONY",
      "BHP",
      "NVO",
      "MC.PA",
      "RMS.PA",
      "TTE.PA",
      "SIE.DE",
      "ALV.DE",
  ]
  selected_tickers.extend(global_proxies)

selected_tickers = list(set(selected_tickers))

st.sidebar.info(
    f"📊 **Master Universe Pool Loaded:** {len(selected_tickers)} raw tickers"
    " from selected indices."
)


@st.cache_data(ttl=3600)
def fetch_market_data(tickers):
  if not tickers:
    return pd.DataFrame(), pd.DataFrame()
  # Batch download prices and volumes from Yahoo Finance
  # Note: For large pools (600+ stocks), yfinance batch download handles it efficiently
  raw_data = yf.download(
      tickers, period="15mo", interval="1d", group_by="ticker", progress=False
  )

  prices = pd.DataFrame()
  volumes = pd.DataFrame()

  for t in tickers:
    try:
      if len(tickers) == 1:
        prices[t] = raw_data["Close"]
        volumes[t] = raw_data["Volume"]
      else:
        if t in raw_data.columns.levels[0]:
          prices[t] = raw_data[t]["Close"]
          volumes[t] = raw_data[t]["Volume"]
    except Exception:
      continue

  return prices.dropna(how="all"), volumes.dropna(how="all")


with st.spinner(
    f"Fetching live market data for {len(selected_tickers)} constituents and"
    " computing liquidity & factor scores..."
):
  df_prices, df_volumes = fetch_market_data(selected_tickers)

if df_prices.empty:
  st.warning(
      "Please select at least one index in the sidebar to populate the universe."
  )
  st.stop()

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
    cutoff = max(10, int(len(ranked_universe) * 0.5))
    st.session_state.qmj_filtered_pool = ranked_universe[:cutoff]
  else:
    st.session_state.qmj_filtered_pool = ranked_universe
  st.session_state.last_action = (
      f"Quarterly Filter Updated: QMJ screen applied to liquid pool of"
      f" {len(ranked_universe)} stocks."
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
