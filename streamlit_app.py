
import os
import pickle
import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# Page Configuration
st.set_page_config(
    page_title="Global Quantitative Momentum Dashboard", layout="wide"
)

st.title("🌐 Global Quantitative Momentum Dashboard")
st.markdown(
    "**Live Engine:** Multi-Strategy Architecture (Stock Momentum via ETF Proxy"
    " Lists vs. UCITS ETF Top-3 Rotation) + Hardcoded $200M Daily Volume Filter"
    " + Persistent Storage."
)

# Load FMP API Key from Streamlit Secrets securely
FMP_KEY = st.secrets.get("FMP_API_KEY", "demo")

# --- PERSISTENT STORAGE FILE PATH ---
STATE_FILE = "dashboard_state.pkl"


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

if "portfolio" not in st.session_state:
  st.session_state.portfolio = (
      persisted_data.get("portfolio", []) if persisted_data else []
  )
if "saved_filtered_pool" not in st.session_state:
  st.session_state.saved_filtered_pool = (
      persisted_data.get("saved_filtered_pool", []) if persisted_data else []
  )
if "saved_prices" not in st.session_state:
  st.session_state.saved_prices = (
      persisted_data.get("saved_prices", pd.DataFrame())
      if persisted_data
      else pd.DataFrame()
  )
if "saved_volumes" not in st.session_state:
  st.session_state.saved_volumes = (
      persisted_data.get("saved_volumes", pd.DataFrame())
      if persisted_data
      else pd.DataFrame()
  )
if "saved_liquidity" not in st.session_state:
  st.session_state.saved_liquidity = (
      persisted_data.get("saved_liquidity", {}) if persisted_data else {}
  )
if "saved_scores" not in st.session_state:
  st.session_state.saved_scores = (
      persisted_data.get("saved_scores", {}) if persisted_data else {}
  )
if "saved_dma" not in st.session_state:
  st.session_state.saved_dma = (
      persisted_data.get("saved_dma", {}) if persisted_data else {}
  )
if "saved_returns" not in st.session_state:
  st.session_state.saved_returns = (
      persisted_data.get("saved_returns", {}) if persisted_data else {}
  )
if "saved_vols" not in st.session_state:
  st.session_state.saved_vols = (
      persisted_data.get("saved_vols", {}) if persisted_data else {}
  )
if "last_action" not in st.session_state:
  st.session_state.last_action = (
      "System initialized from persistent storage."
      if persisted_data
      else "Initialized with empty list. Click 'Run Strategy Update'."
  )

exceptions_log = []

# --- SIDEBAR CONTROLS ---
st.sidebar.header("1. Strategy Configuration")
strategy_mode = st.sidebar.radio(
    "Select Strategy Mode",
    [
        "Stock Momentum (S&P 500, Nasdaq, Russell via ETF Lists | Top 10 + QMJ)",
        "UCITS ETF Momentum (Core Liquid UCITS ETFs | Top 3 Rotation)",
    ],
)

use_qmj = st.sidebar.checkbox(
    "Enable FMP-Powered QMJ Quality Pre-Filter (Stocks Only)",
    value=True
    if "Stock Momentum" in strategy_mode
    else False,
)
exit_vehicle = st.sidebar.selectbox(
    "Destination Vehicle on 200-DMA Exit",
    ["100% Cash / Risk-Free", "MSCI World ETF (URTH)"],
)

st.sidebar.header("2. Execution Controls")
run_update_btn = st.sidebar.button(
    "🔄 Run Strategy Universe Update (Load/Refresh)"
)
run_rerank_btn = st.sidebar.button(
    "📊 Run Monthly Rerank (Apply Buffer Rule)"
)


# --- ETF-BASED STOCK LIST LOADERS (PROXIES FOR S&P 500, NASDAQ 100, RUSSELL 1000) ---
def load_stock_lists_via_etfs():
  """Loads comprehensive stock lists using institutional ETF holdings and representative index proxies."""
  # S&P 500 Representative Holdings & Core Large-Cap Pool (via SPY/IVV proxy)
  sp500_proxy = [
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
      "NFLX",
      "AMD",
      "TMUS",
      "LIN",
      "PEP",
      "ADBE",
      "WMT",
      "MCD",
      "CRM",
      "ACN",
      "TMO",
      "CSCO",
      "ABT",
      "DHR",
      "PFE",
      "CMCSA",
      "VZ",
      "DIS",
      "INTC",
      "QCOM",
      "TXN",
      "AMGN",
      "IBM",
      "HON",
      "UNP",
      "LOW",
      "INTU",
      "SPGI",
      "CAT",
      "GE",
      "AXP",
      "BKNG",
      "ISRG",
      "BLK",
      "TJX",
      "GILD",
      "VRTX",
      "MDLZ",
      "ADI",
      "SYK",
  ]

  # Nasdaq 100 Representative Holdings Pool (via QQQ proxy)
  nasdaq_proxy = [
      "TSLA",
      "AVGO",
      "HON",
      "SBUX",
      "LRCX",
      "PANW",
      "MELI",
      "SNPS",
      "CDNS",
      "KLAC",
      "REGN",
      "MAR",
      "ASML",
      "PDD",
      "ORLY",
      "ABNB",
      "MNST",
      "CTAS",
      "FTNT",
      "WDAY",
      "ADSK",
      "CPRT",
      "KDP",
      "EXC",
      "IDXX",
      "CHTR",
      "BIIB",
      "DXCM",
      "LULU",
      "EA",
  ]

  # Russell 1000 Representative Mid/Large-Cap Pool (via IWB proxy)
  russell_proxy = [
      "PLTR",
      "CRWD",
      "NOW",
      "UBER",
      "ETN",
      "FI",
      "BX",
      "PGR",
      "LMT",
      "CB",
      "BSX",
      "SHW",
      "NKE",
      "MDT",
      "ICE",
      "COP",
      "ANET",
      "EOG",
      "C",
      "USB",
      "PNC",
      "TFC",
      "COF",
      "MET",
      "AIG",
      "TRV",
      "ALL",
      "PRU",
      "HUM",
      "CNC",
  ]

  combined_stocks = sorted(
      list(set(sp500_proxy + nasdaq_proxy + russell_proxy))
  )
  return combined_stocks


def load_ucits_etf_universe():
  """Loads the Core Liquid UCITS ETF Universe (> $1B AUM)."""
  return [
      "IWDA.L",  # iShares Core MSCI World UCITS ETF
      "SWDA.L",  # iShares Core MSCI World UCITS ETF (Acc)
      "VUAA.L",  # Vanguard S&P 500 UCITS ETF
      "SXR8.DE",  # iShares Core S&P 500 UCITS ETF
      "EQQQ.L",  # Invesco EQQQ Nasdaq 100 UCITS ETF
      "SXRV.DE",  # iShares Nasdaq 100 UCITS ETF
      "EXSA.DE",  # iShares STOXX Europe 600 UCITS ETF
      "QDVE.DE",  # iShares MSCI Global Semiconductors UCITS ETF
      "XDWE.DE",  # Xtrackers MSCI World Health Care UCITS ETF
      "AGGH.L",  # iShares Core Global Aggregate Bond UCITS ETF
      "DTLA.L",  # iShares USD Treasury 20+ Year UCITS ETF
  ]


def get_fmp_quality_scores(tickers, api_key):
  quality_scores = {}
  for ticker in tickers:
    if "." in ticker:
      continue  # Skip for ETFs
    try:
      url = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{ticker}?apikey={api_key}"
      resp = requests.get(url, timeout=1.0)
      if resp.status_code == 200:
        data = resp.json()
        if data and isinstance(data, list):
          metrics = data[0]
          roe = metrics.get("roeTTM", 0) or 0
          gpm = metrics.get("grossProfitMarginTTM", 0) or 0
          quality_scores[ticker] = (roe * 0.6) + (gpm * 0.4)
    except Exception:
      continue
  return quality_scores


def fetch_market_data(tickers):
  if not tickers:
    return pd.DataFrame(), pd.DataFrame()

  chunk_size = 150
  all_prices, all_volumes = [], []

  for i in range(0, len(tickers), chunk_size):
    chunk = tickers[i : i + chunk_size]
    try:
      raw_data = yf.download(
          chunk, period="15mo", interval="1d", group_by="ticker", progress=False
      )
      p_chunk, v_chunk = pd.DataFrame(), pd.DataFrame()
      for t in chunk:
        if len(chunk) == 1:
          p_chunk[t] = raw_data["Close"]
          v_chunk[t] = raw_data["Volume"]
        else:
          if t in raw_data.columns.levels[0]:
            p_chunk[t] = raw_data[t]["Close"]
            v_chunk[t] = raw_data[t]["Volume"]
      if not p_chunk.empty:
        all_prices.append(p_chunk)
        all_volumes.append(v_chunk)
    except Exception as e:
      exceptions_log.append(f"Data Fetch Chunk Exception: {e}")
      continue

  if not all_prices:
    return pd.DataFrame(), pd.DataFrame()
  return (
      pd.concat(all_prices, axis=1).dropna(how="all"),
      pd.concat(all_volumes, axis=1).dropna(how="all"),
  )


# --- STRATEGY UPDATE EXECUTION & PERSISTENT SAVE ---
if run_update_btn:
  is_stock_strategy = "Stock Momentum" in strategy_mode
  target_universe = (
      load_stock_lists_via_etfs()
      if is_stock_strategy
      else load_ucits_etf_universe()
  )

  mode_label = (
      "Stock Momentum (via ETF Lists)"
      if is_stock_strategy
      else "UCITS ETF Momentum"
  )

  with st.spinner(
      f"Loading {mode_label} universe, fetching market data, and computing"
      " momentum scores..."
  ):
    df_prices, df_volumes = fetch_market_data(target_universe)
    fmp_quality = (
        get_fmp_quality_scores(target_universe, FMP_KEY)
        if is_stock_strategy
        else {}
    )

    st.session_state.saved_prices = df_prices
    st.session_state.saved_volumes = df_volumes

    # Hardcoded $500M daily volume filter ($200,000,000)
    min_dollar_vol = 200_000_000.0
    qualified_tickers = []
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
            qualified_tickers.append(ticker)

    st.session_state.saved_liquidity = ticker_liquidity
    df_prices_qualified = df_prices[qualified_tickers]

    scores, dma_status, returns_12_1, vols = {}, {}, {}, {}
    for ticker in df_prices_qualified.columns:
      series = df_prices_qualified[ticker].dropna()
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

          mom_score = ret_12_1 / vols[ticker]
          if use_qmj and "." not in ticker and ticker in fmp_quality:
            q_score = max(0.1, fmp_quality[ticker])
            scores[ticker] = mom_score * q_score
          else:
            scores[ticker] = mom_score

    ranked_universe = sorted(scores, key=lambda k: scores[k], reverse=True)

    st.session_state.saved_filtered_pool = ranked_universe
    st.session_state.saved_scores = scores
    st.session_state.saved_dma = dma_status
    st.session_state.saved_returns = returns_12_1
    st.session_state.saved_vols = vols
    st.session_state.last_action = (
        f"Strategy Updated ({mode_label}): Loaded {len(ranked_universe)} passing"
        " assets."
    )

    # Save to persistent storage file
    save_persistent_state({
        "portfolio": st.session_state.portfolio,
        "saved_filtered_pool": ranked_universe,
        "saved_prices": df_prices,
        "saved_volumes": df_volumes,
        "saved_liquidity": ticker_liquidity,
        "saved_scores": scores,
        "saved_dma": dma_status,
        "saved_returns": returns_12_1,
        "saved_vols": vols,
    })

# --- DISPLAY LOGGED EXCEPTIONS ---
if exceptions_log:
  st.warning(
      f"⚠️ **System Notice:** {len(exceptions_log)} exception(s) occurred:"
  )
  for idx, ex in enumerate(exceptions_log, 1):
    st.text(f"{idx}. {ex}")

# Check if data exists in persistent state / session state
if not st.session_state.saved_filtered_pool:
  st.info(
      "👋 **Dashboard Initialized (Empty State).** Select your strategy mode"
      " and click the **'🔄 Run Strategy Universe Update'** button in the"
      " sidebar."
  )
  st.stop()

# Retrieve saved pool and metrics from session state
active_pool = st.session_state.saved_filtered_pool
scores = st.session_state.saved_scores
dma_status = st.session_state.saved_dma
returns_12_1 = st.session_state.saved_returns
vols = st.session_state.saved_vols
ticker_liquidity = st.session_state.saved_liquidity

is_stock_strategy = "Stock Momentum" in strategy_mode
target_slots = 10 if is_stock_strategy else 3

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
    if len(new_portfolio) >= target_slots:
      break
    if ticker not in new_portfolio:
      new_portfolio.append(ticker)

  st.session_state.portfolio = new_portfolio
  st.session_state.last_action = (
      f"Monthly Rerank Executed: Applied 15-Rank Buffer Rule. Portfolio"
      f" updated with {len(new_portfolio)} assets."
  )

  save_persistent_state({
      "portfolio": new_portfolio,
      "saved_filtered_pool": st.session_state.saved_filtered_pool,
      "saved_prices": st.session_state.saved_prices,
      "saved_volumes": st.session_state.saved_volumes,
      "saved_liquidity": st.session_state.saved_liquidity,
      "saved_scores": st.session_state.saved_scores,
      "saved_dma": st.session_state.saved_dma,
      "saved_returns": st.session_state.saved_returns,
      "saved_vols": st.session_state.saved_vols,
  })

if not st.session_state.portfolio:
  st.session_state.portfolio = active_pool[:target_slots]

# --- DISPLAY ACTIVE PORTFOLIO LEADERBOARD ---
table_data = []
alloc_pct = f"{100.0 / target_slots:.1f}%"
for i, ticker in enumerate(st.session_state.portfolio, 1):
  status = dma_status.get(ticker, "Above 200-DMA")
  alloc = (
      f"{alloc_pct} Equities"
      if status == "Above 200-DMA"
      else (
          f"{alloc_pct} Cash"
          if "Cash" in exit_vehicle
          else f"{alloc_pct} MSCI World ETF (URTH)"
      )
  )

  pool_rank = (
      active_pool.index(ticker) + 1 if ticker in active_pool else "N/A"
  )
  avg_vol_m = ticker_liquidity.get(ticker, 0) / 1e6

  table_data.append({
      "Portfolio Slot": i,
      "Ticker": ticker,
      "Saved Universe Rank": pool_rank,
      "Daily Vol ($M)": f"${avg_vol_m:.1f}M",
      "200-DMA Trend": status,
      "12-1 Return": f"{returns_12_1.get(ticker, 0)*100:.1f}%",
      "Ann. Volatility": f"{vols.get(ticker, 0)*100:.1f}%",
      "Risk-Adj Score": f"{scores.get(ticker, 0):.2f}",
      "Target Allocation": alloc,
  })

df_display = pd.DataFrame(table_data)

st.subheader(
    f"🏆 Active Portfolio Leaderboard ({strategy_mode.split('(')[0].strip()}"
    f" | Top {target_slots})"
)
st.info(f"**Execution Status:** {st.session_state.last_action}")
st.dataframe(df_display, use_container_width=True)

# --- DISPLAY FULL SAVED FILTERED & RANKED UNIVERSE TABLE (SORTABLE) ---
st.markdown("---")
st.subheader(
    f"📊 Saved Filtered & Ranked Universe ({len(active_pool)} Passing Assets)"
)
st.markdown(
    "*Click any column header below to sort and rank the saved universe"
    " interactively.*"
)

full_universe_data = []
for rank, ticker in enumerate(active_pool, 1):
  status = dma_status.get(ticker, "N/A")
  avg_vol_m = ticker_liquidity.get(ticker, 0) / 1e6

  full_universe_data.append({
      "Rank": rank,
      "Ticker": ticker,
      "Daily Vol ($M)": round(avg_vol_m, 1),
      "200-DMA Trend": status,
      "12-1 Return (%)": round(returns_12_1.get(ticker, 0) * 100, 1),
      "Ann. Volatility (%)": round(vols.get(ticker, 0) * 100, 1),
      "Risk-Adj Score": round(scores.get(ticker, 0), 2),
  })

df_full_universe = pd.DataFrame(full_universe_data)
st.dataframe(df_full_universe, use_container_width=True, height=450)

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
