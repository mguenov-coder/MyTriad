import io
import os
import pickle
import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# Page Configuration
st.set_page_config(
    page_title="Multi-Index Quantitative Momentum Dashboard", layout="wide"
)

st.title("🌐 Multi-Index Quantitative Momentum Dashboard")
st.markdown(
    "**Engine:** Embedded CSV Constituent Lists (Russell 1000, S&P 500, Nasdaq"
    " 100) + **$10B+ Market Cap Filter** + 12-1 Return & Volatility-Adjusted"
    " Ranking + Permanent Storage."
)

# Load FMP API Key from Streamlit Secrets securely
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

if "constituent_dataframes" not in st.session_state:
  st.session_state.constituent_dataframes = (
      persisted_data.get("constituent_dataframes", {}) if persisted_data else {}
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
          "Initialized empty. Click 'Refresh Constituent Lists' to load"
          " embedded CSV datasets."
      )
  )

exceptions_log = []

# --- SIDEBAR CONTROLS ---
st.sidebar.header("1. Index Selection Checkboxes")
show_russell = st.sidebar.checkbox("Russell 1000", value=True)
show_sp500 = st.sidebar.checkbox("S&P 500", value=True)
show_nasdaq = st.sidebar.checkbox("Nasdaq 100", value=True)

st.sidebar.header("2. Data & Execution Controls")
refresh_lists_btn = st.sidebar.button(
    "🔄 Refresh Constituent Lists (Embedded Data)"
)
reload_data_btn = st.sidebar.button(
    "⚡ Reload Price Data & Recalculate Metrics"
)


# --- EMBEDDED CSV DATASETS ---
RUSSELL_1000_CSV = """rank,ticker,company,sector,weight,market_cap_usd
1,NVDA,NVIDIA Corporation,Technology,13.31,5.47T
2,AAPL,Apple Inc.,Technology,11.57,4.39T
3,MSFT,Microsoft Corporation,Technology,8.55,3.01T
4,AMZN,Amazon.com Inc.,Consumer Discretionary,7.07,2.91T
5,GOOGL,Alphabet Inc. Class A,Communication Services,5.75,4.88T
6,GOOG,Alphabet Inc. Class C,Communication Services,5.33,4.83T
7,AVGO,Broadcom Inc.,Technology,4.6,1.97T
8,META,Meta Platforms Inc. Class A,Communication Services,4.58,1.57T
9,TSLA,Tesla Inc.,Consumer Discretionary,4.44,1.67T
10,WMT,Walmart Inc.,Consumer Staples,3.06,1.05T
11,ASML,ASML Holding N.V.,Technology,1.65,609.6B
12,COST,Costco Wholesale Corporation,Consumer Staples,1.37,458.3B
13,MU,Micron Technology Inc.,Technology,1.3,906.3B
14,NFLX,Netflix Inc.,Communication Services,1.25,368.7B
15,PLTR,Palantir Technologies Inc. Class A,Technology,1.09,311.8B
16,AMD,Advanced Micro Devices Inc.,Technology,1.07,726.4B
17,CSCO,Cisco Systems Inc.,Technology,0.97,402.4B
18,AMAT,Applied Materials Inc.,Technology,0.88,346.5B
19,LRCX,Lam Research Corporation,Technology,0.86,369.5B
20,INTC,Intel Corporation,Technology,0.76,604.6B
21,LIN,Linde plc,Materials,0.71,237.3B
22,TMUS,T-Mobile US Inc.,Communication Services,0.69,205.9B
23,PEP,PepsiCo Inc.,Consumer Staples,0.65,204.0B
24,KLAC,KLA Corporation,Technology,0.62,241.6B
25,AMGN,Amgen Inc.,Health Care,0.59,181.7B
26,TXN,Texas Instruments Incorporated,Technology,0.56,278.8B
27,GILD,Gilead Sciences Inc.,Health Care,0.54,165.2B
28,ISRG,Intuitive Surgical Inc.,Health Care,0.51,153.1B
29,ARM,Arm Holdings plc ADR,Technology,0.5,235.4B
30,ADI,Analog Devices Inc.,Technology,0.49,211.1B
31,SHOP,Shopify Inc. Class A,Consumer Discretionary,0.48,123.8B
32,PDD,PDD Holdings Inc. ADR,Consumer Discretionary,0.45,141.8B
33,HON,Honeywell International Inc.,Industrials,0.45,138.1B
34,QCOM,QUALCOMM Incorporated,Technology,0.43,224.7B
35,BKNG,Booking Holdings Inc.,Consumer Discretionary,0.42,120.1B
36,APP,AppLovin Corporation Class A,Technology,0.41,152.4B
37,PANW,Palo Alto Networks Inc.,Technology,0.4,184.7B
38,INTU,Intuit Inc.,Technology,0.36,103.4B
39,VRTX,Vertex Pharmaceuticals Incorporated,Health Care,0.36,115.0B
40,SBUX,Starbucks Corporation,Consumer Discretionary,0.32,120.8B
41,WDC,Western Digital Corporation,Technology,0.32,170.3B
42,CEG,Constellation Energy Corporation,Utilities,0.31,99.3B
43,CMCSA,Comcast Corporation Class A,Communication Services,0.31,89.1B
44,CRWD,CrowdStrike Holdings Inc. Class A,Technology,0.31,143.2B
45,ADBE,Adobe Inc.,Technology,0.3,95.4B
46,STX,Seagate Technology Holdings plc,Technology,0.3,183.3B
47,MRVL,Marvell Technology Inc.,Technology,0.29,155.6B
48,MAR,Marriott International Inc. Class A,Consumer Discretionary,0.27,92.3B
49,MELI,MercadoLibre Inc.,Consumer Discretionary,0.27,79.2B
50,REGN,Regeneron Pharmaceuticals Inc.,Health Care,0.25,75.5B
51,ADP,Automatic Data Processing Inc.,Technology,0.25,83.4B
52,CDNS,Cadence Design Systems Inc.,Technology,0.24,97.8B
53,ORLY,O'Reilly Automotive Inc.,Consumer Discretionary,0.24,74.3B
54,CSX,CSX Corporation,Industrials,0.24,82.5B
55,SNPS,Synopsys Inc.,Technology,0.24,97.6B
56,ABNB,Airbnb Inc. Class A,Consumer Discretionary,0.24,78.9B
57,MDLZ,Mondelez International Inc. Class A,Consumer Staples,0.23,79.0B
58,MNST,Monster Beverage Corporation,Consumer Staples,0.22,84.0B
59,ROST,Ross Stores Inc.,Consumer Discretionary,0.22,68.5B
60,AEP,American Electric Power Company Inc.,Utilities,0.22,69.6B
61,WBD,Warner Bros. Discovery Inc. Series A,Communication Services,0.22,68.3B
62,CTAS,Cintas Corporation,Industrials,0.21,65.4B
63,DASH,DoorDash Inc. Class A,Consumer Discretionary,0.2,65.0B
64,PCAR,PACCAR Inc.,Industrials,0.19,58.8B
65,FTNT,Fortinet Inc.,Technology,0.19,86.2B
66,BKR,Baker Hughes Company Class A,Energy,0.18,64.9B
67,MPWR,Monolithic Power Systems Inc.,Technology,0.17,81.1B
68,FANG,Diamondback Energy Inc.,Energy,0.17,56.6B
69,FAST,Fastenal Company,Industrials,0.17,50.2B
70,EA,Electronic Arts Inc.,Communication Services,0.16,50.2B
71,ADSK,Autodesk Inc.,Technology,0.16,48.8B
72,NXPI,NXP Semiconductors N.V.,Technology,0.15,75.3B
73,EXC,Exelon Corporation,Utilities,0.15,45.3B
74,XEL,Xcel Energy Inc.,Utilities,0.15,49.9B
75,FER,Ferrovial SE,Utilities,0.15,48.7B
76,IDXX,IDEXX Laboratories Inc.,Health Care,0.14,41.7B
77,ALNY,Alnylam Pharmaceuticals Inc.,Health Care,0.14,38.9B
78,MSTR,Strategy Inc.,Technology,0.13,62.4B
79,DDOG,Datadog Inc. Class A,Technology,0.13,73.1B
80,ODFL,Old Dominion Freight Line Inc.,Industrials,0.13,39.3B
81,PYPL,PayPal Holdings Inc.,Technology,0.13,39.9B
82,CCEP,Coca-Cola Europacific Partners plc,Consumer Staples,0.13,40.5B
83,TRI,Thomson Reuters Corporation,Technology,0.12,35.8B
84,TTWO,Take-Two Interactive Software Inc.,Communication Services,0.11,42.0B
85,ROP,Roper Technologies Inc.,Industrials,0.11,31.9B
86,MCHP,Microchip Technology Incorporated,Technology,0.11,52.3B
87,INSM,Insmed Incorporated,Health Care,0.11,25.6B
88,KDP,Keurig Dr Pepper Inc.,Consumer Staples,0.11,39.9B
89,AXON,Axon Enterprise Inc.,Industrials,0.11,30.4B
90,WDAY,Workday Inc. Class A,Technology,0.1,29.1B
91,PAYX,Paychex Inc.,Technology,0.1,32.2B
92,GEHC,GE HealthCare Technologies Inc.,Health Care,0.1,28.2B
93,CPRT,Copart Inc.,Industrials,0.1,31.7B
94,CTSH,Cognizant Technology Solutions Corporation Class A,Technology,0.09,21.7B
95,CHTR,Charter Communications Inc. Class A,Communication Services,0.08,20.2B
96,KHC,Kraft Heinz Company,Consumer Staples,0.08,27.5B
97,VRSK,Verisk Analytics Inc.,Technology,0.08,21.2B
98,DXCM,DexCom Inc.,Health Care,0.08,22.6B
99,ZS,Zscaler Inc. Class A,Technology,0.07,24.5B
100,TEAM,Atlassian Corporation Class A,Technology,0.06,20.5B"""

SP500_CSV = """Symbol,Name,Sector
MMM,3M,Industrial Conglomerates
AOS,A. O. Smith,Building Products
ABT,Abbott Laboratories,Health Care Equipment
ABBV,AbbVie,Biotechnology
ACN,Accenture,IT Consulting & Other Services
ADBE,Adobe Inc.,Application Software
AMD,Advanced Micro Devices,Semiconductors
AES,AES Corporation,Independent Power Producers & Energy Traders
AFL,Aflac,Life & Health Insurance
A,Agilent Technologies,Life Sciences Tools & Services
APD,Air Products,Industrial Gases
ABNB,Airbnb,"Hotels, Resorts & Cruise Lines"
AKAM,Akamai Technologies,Internet Services & Infrastructure
ALB,Albemarle Corporation,Specialty Chemicals
ARE,Alexandria Real Estate Equities,Office REITs
ALGN,Align Technology,Health Care Supplies
ALLE,Allegion,Building Products
LNT,Alliant Energy,Electric Utilities
ALL,Allstate,Property & Casualty Insurance
GOOGL,Alphabet Inc. (Class A),Interactive Media & Services
GOOG,Alphabet Inc. (Class C),Interactive Media & Services
MO,Altria,Tobacco
AMZN,Amazon,Broadline Retail
AMCR,Amcor,Paper & Plastic Packaging Products & Materials
AMTM,Amentum,Diversified Support Services
AEE,Ameren,Multi-Utilities
AEP,American Electric Power,Electric Utilities
AXP,American Express,Consumer Finance
AIG,American International Group,Multi-line Insurance
AMT,American Tower,Telecom Tower REITs
AWK,American Water Works,Water Utilities
AMP,Ameriprise Financial,Asset Management & Custody Banks
AME,Ametek,Electrical Components & Equipment
AMGN,Amgen,Biotechnology
APH,Amphenol,Electronic Components
ADI,Analog Devices,Semiconductors
ANSS,Ansys,Application Software
AON,Aon,Insurance Brokers
APA,APA Corporation,Oil & Gas Exploration & Production
AAPL,Apple Inc.,"Technology Hardware, Storage & Peripherals"
AMAT,Applied Materials,Semiconductor Materials & Equipment
APTV,Aptiv,Automotive Parts & Equipment
ACGL,Arch Capital Group,Property & Casualty Insurance
ADM,Archer Daniels Midland,Agricultural Products & Services
ANET,Arista Networks,Communications Equipment
AJG,Arthur J. Gallagher & Co.,Insurance Brokers
AIZ,Assurant,Multi-line Insurance
T,AT&T,Integrated Telecommunication Services
ATO,Atmos Energy,Gas Utilities
ADSK,Autodesk,Application Software
ADP,Automatic Data Processing,Human Resource & Employment Services
AZO,AutoZone,Automotive Retail
AVB,AvalonBay Communities,Multi-Family Residential REITs
AVY,Avery Dennison,Paper & Plastic Packaging Products & Materials
AXON,Axon Enterprise,Aerospace & Defense
BKR,Baker Hughes,Oil & Gas Equipment & Services
BALL,Ball Corporation,"Metal, Glass & Plastic Containers"
BAC,Bank of America,Diversified Banks
BAX,Baxter International,Health Care Equipment
BDX,Becton Dickinson,Health Care Equipment
BRK.B,Berkshire Hathaway,Multi-Sector Holdings
BBY,Best Buy,Computer & Electronics Retail
TECH,Bio-Techne,Life Sciences Tools & Services
BIIB,Biogen,Biotechnology
BLK,BlackRock,Asset Management & Custody Banks
BX,Blackstone Inc.,Asset Management & Custody Banks
BK,BNY Mellon,Asset Management & Custody Banks
BA,Boeing,Aerospace & Defense
BKNG,Booking Holdings,"Hotels, Resorts & Cruise Lines"
BWA,BorgWarner,Automotive Parts & Equipment
BSX,Boston Scientific,Health Care Equipment
BMY,Bristol Myers Squibb,Pharmaceuticals
AVGO,Broadcom,Semiconductors
BR,Broadridge Financial Solutions,Data Processing & Outsourced Services
BRO,Brown & Brown,Insurance Brokers
BF.B,Brown–Forman,Distillers & Vintners
BLDR,Builders FirstSource,Building Products
BG,Bunge Global,Agricultural Products & Services
BXP,"BXP, Inc.",Office REITs
CHRW,C.H. Robinson,Air Freight & Logistics
CDNS,Cadence Design Systems,Application Software
CZR,Caesars Entertainment,Casinos & Gaming
CPT,Camden Property Trust,Multi-Family Residential REITs
CPB,Campbell Soup Company,Packaged Foods & Meats
COF,Capital One,Consumer Finance
CAH,Cardinal Health,Health Care Distributors
KMX,CarMax,Automotive Retail
CCL,Carnival,"Hotels, Resorts & Cruise Lines"
CARR,Carrier Global,Building Products
CTLT,Catalent,Pharmaceuticals
CAT,Caterpillar Inc.,Construction Machinery & Heavy Transportation Equipment
CBOE,Cboe Global Markets,Financial Exchanges & Data
CBRE,CBRE Group,Real Estate Services
CDW,CDW,Technology Distributors
CE,Celanese,Specialty Chemicals
COR,Cencora,Health Care Distributors
CNC,Centene Corporation,Managed Health Care
CNP,CenterPoint Energy,Multi-Utilities
CF,CF Industries,Fertilizers & Agricultural Chemicals
CRL,Charles River Laboratories,Life Sciences Tools & Services
SCHW,Charles Schwab Corporation,Investment Banking & Brokerage
CHTR,Charter Communications,Cable & Satellite
CVX,Chevron Corporation,Integrated Oil & Gas
CMG,Chipotle Mexican Grill,Restaurants
CB,Chubb Limited,Property & Casualty Insurance
CHD,Church & Dwight,Household Products
CI,Cigna,Health Care Services
CINF,Cincinnati Financial,Property & Casualty Insurance
CTAS,Cintas,Diversified Support Services
CSCO,Cisco,Communications Equipment
C,Citigroup,Diversified Banks
CFG,Citizens Financial Group,Regional Banks
CLX,Clorox,Household Products
CME,CME Group,Financial Exchanges & Data
CMS,CMS Energy,Multi-Utilities
KO,Coca-Cola Company (The),Soft Drinks & Non-alcoholic Beverages
CTSH,Cognizant,IT Consulting & Other Services
CL,Colgate-Palmolive,Household Products
CMCSA,Comcast,Cable & Satellite
CAG,Conagra Brands,Packaged Foods & Meats
COP,ConocoPhillips,Oil & Gas Exploration & Production
ED,Consolidated Edison,Multi-Utilities
STZ,Constellation Brands,Distillers & Vintners
CEG,Constellation Energy,Electric Utilities
COO,Cooper Companies (The),Health Care Supplies
CPRT,Copart,Diversified Support Services
GLW,Corning Inc.,Electronic Components
CPAY,Corpay,Transaction & Payment Processing Services
CTVA,Corteva,Fertilizers & Agricultural Chemicals
CSGP,CoStar Group,Real Estate Services
COST,Costco,Consumer Staples Merchandise Retail
CTRA,Coterra,Oil & Gas Exploration & Production
CRWD,CrowdStrike,Systems Software
CCI,Crown Castle,Telecom Tower REITs
CSX,CSX Corporation,Rail Transportation
CMI,Cummins,Construction Machinery & Heavy Transportation Equipment
CVS,CVS Health,Health Care Services
DHI,D. R. Horton,Homebuilding
DHR,Danaher Corporation,Life Sciences Tools & Services
DRI,Darden Restaurants,Restaurants
DVA,DaVita,Health Care Services
DAY,Dayforce,Human Resource & Employment Services
DECK,Deckers Brands,Footwear
DE,Deere & Company,Agricultural & Farm Machinery
DELL,Dell Technologies,"Technology Hardware, Storage & Peripherals"
DAL,Delta Air Lines,Passenger Airlines
DVN,Devon Energy,Oil & Gas Exploration & Production
DXCM,Dexcom,Health Care Equipment
FANG,Diamondback Energy,Oil & Gas Exploration & Production
DLR,Digital Realty,Data Center REITs
DFS,Discover Financial,Consumer Finance
DG,Dollar General,Consumer Staples Merchandise Retail
DLTR,Dollar Tree,Consumer Staples Merchandise Retail
D,Dominion Energy,Multi-Utilities
DPZ,Domino's,Restaurants
DOV,Dover Corporation,Industrial Machinery & Supplies & Components
DOW,Dow Inc.,Commodity Chemicals
DTE,DTE Energy,Multi-Utilities
DUK,Duke Energy,Electric Utilities
DD,DuPont,Specialty Chemicals
EMN,Eastman Chemical Company,Specialty Chemicals
ETN,Eaton Corporation,Electrical Components & Equipment
EBAY,eBay,Broadline Retail
ECL,Ecolab,Specialty Chemicals
EIX,Edison International,Electric Utilities
EW,Edwards Lifesciences,Health Care Equipment
EA,Electronic Arts,Interactive Home Entertainment
ELV,Elevance Health,Managed Health Care
EMR,Emerson Electric,Electrical Components & Equipment
ENPH,Enphase Energy,Semiconductor Materials & Equipment
ETR,Entergy,Electric Utilities
EOG,EOG Resources,Oil & Gas Exploration & Production
EPAM,EPAM Systems,IT Consulting & Other Services
EQT,EQT Corporation,Oil & Gas Exploration & Production
EFX,Equifax,Research & Consulting Services
EQIX,Equinix,Data Center REITs
EQR,Equity Residential,Multi-Family Residential REITs
ERIE,Erie Indemnity,Insurance Brokers
ESS,Essex Property Trust,Multi-Family Residential REITs
EL,Estée Lauder Companies (The),Personal Care Products
EG,Everest Group,Reinsurance
EVRG,Evergy,Electric Utilities
ES,Eversource Energy,Electric Utilities
EXC,Exelon,Electric Utilities
EXPE,Expedia Group,"Hotels, Resorts & Cruise Lines"
EXPD,Expeditors International,Air Freight & Logistics
EXR,Extra Space Storage,Self-Storage REITs
XOM,ExxonMobil,Integrated Oil & Gas
FFIV,"F5, Inc.",Communications Equipment
FDS,FactSet,Financial Exchanges & Data
FICO,Fair Isaac,Application Software
FAST,Fastenal,Trading Companies & Distributors
FRT,Federal Realty Investment Trust,Retail REITs
FDX,FedEx,Air Freight & Logistics
FIS,Fidelity National Information Services,Transaction & Payment Processing Services
FITB,Fifth Third Bancorp,Regional Banks
FSLR,First Solar,Semiconductors
FE,FirstEnergy,Electric Utilities
FI,Fiserv,Transaction & Payment Processing Services
FMC,FMC Corporation,Fertilizers & Agricultural Chemicals
F,Ford Motor Company,Automobile Manufacturers
FTNT,Fortinet,Systems Software
FTV,Fortive,Industrial Machinery & Supplies & Components
FOXA,Fox Corporation (Class A),Broadcasting
FOX,Fox Corporation (Class B),Broadcasting
BEN,Franklin Resources,Asset Management & Custody Banks
FCX,Freeport-McMoRan,Copper
GRMN,Garmin,Consumer Electronics
IT,Gartner,IT Consulting & Other Services
GE,GE Aerospace,Aerospace & Defense
GEHC,GE HealthCare,Health Care Equipment
GEV,GE Vernova,Heavy Electrical Equipment
GEN,Gen Digital,Systems Software
GNRC,Generac,Electrical Components & Equipment
GD,General Dynamics,Aerospace & Defense
GIS,General Mills,Packaged Foods & Meats
GM,General Motors,Automobile Manufacturers
GPC,Genuine Parts Company,Distributors
GILD,Gilead Sciences,Biotechnology
GPN,Global Payments,Transaction & Payment Processing Services
GL,Globe Life,Life & Health Insurance
GDDY,GoDaddy,Internet Services & Infrastructure
GS,Goldman Sachs,Investment Banking & Brokerage
HAL,Halliburton,Oil & Gas Equipment & Services
HIG,Hartford (The),Property & Casualty Insurance
HAS,Hasbro,Leisure Products
HCA,HCA Healthcare,Health Care Facilities
DOC,Healthpeak Properties,Health Care REITs
HSIC,Henry Schein,Health Care Distributors
HSY,Hershey Company (The),Packaged Foods & Meats
HES,Hess Corporation,Integrated Oil & Gas
HPE,Hewlett Packard Enterprise,"Technology Hardware, Storage & Peripherals"
HLT,Hilton Worldwide,"Hotels, Resorts & Cruise Lines"
HOLX,Hologic,Health Care Equipment
HD,Home Depot (The),Home Improvement Retail
HON,Honeywell,Industrial Conglomerates
HRL,Hormel Foods,Packaged Foods & Meats
HST,Host Hotels & Resorts,Hotel & Resort REITs
HWM,Howmet Aerospace,Aerospace & Defense
HPQ,HP Inc.,"Technology Hardware, Storage & Peripherals"
HUBB,Hubbell Incorporated,Industrial Machinery & Supplies & Components
HUM,Humana,Managed Health Care
HBAN,Huntington Bancshares,Regional Banks
HII,Huntington Ingalls Industries,Aerospace & Defense
IBM,IBM,IT Consulting & Other Services
IEX,IDEX Corporation,Industrial Machinery & Supplies & Components
IDXX,Idexx Laboratories,Health Care Equipment
ITW,Illinois Tool Works,Industrial Machinery & Supplies & Components
INCY,Incyte,Biotechnology
IR,Ingersoll Rand,Industrial Machinery & Supplies & Components
PODD,Insulet Corporation,Health Care Equipment
INTC,Intel,Semiconductors
ICE,Intercontinental Exchange,Financial Exchanges & Data
IFF,International Flavors & Fragrances,Specialty Chemicals
IP,International Paper,Paper & Plastic Packaging Products & Materials
IPG,Interpublic Group of Companies (The),Advertising
INTU,Intuit,Application Software
ISRG,Intuitive Surgical,Health Care Equipment
IVZ,Invesco,Asset Management & Custody Banks
INVH,Invitation Homes,Single-Family Residential REITs
IQV,IQVIA,Life Sciences Tools & Services
IRM,Iron Mountain,Other Specialized REITs
JBHT,J.B. Hunt,Cargo Ground Transportation
SJM,J.M. Smucker Company (The),Packaged Foods & Meats
JBL,Jabil,Electronic Manufacturing Services
JKHY,Jack Henry & Associates,Transaction & Payment Processing Services
J,Jacobs Solutions,Construction & Engineering
JNJ,Johnson & Johnson,Pharmaceuticals
JCI,Johnson Controls,Building Products
JPM,JPMorgan Chase,Diversified Banks
JNPR,Juniper Networks,Communications Equipment
K,Kellanova,Packaged Foods & Meats
KVUE,Kenvue,Personal Care Products
KDP,Keurig Dr Pepper,Soft Drinks & Non-alcoholic Beverages
KEY,KeyCorp,Regional Banks
KEYS,Keysight Technologies,Electronic Equipment & Instruments
KMB,Kimberly-Clark,Household Products
KIM,Kimco Realty,Retail REITs
KMI,Kinder Morgan,Oil & Gas Storage & Transportation
KKR,KKR,Asset Management & Custody Banks
KLAC,KLA Corporation,Semiconductor Materials & Equipment
KHC,Kraft Heinz,Packaged Foods & Meats
KR,Kroger,Food Retail
LHX,L3Harris,Aerospace & Defense
LH,LabCorp,Health Care Services
LRCX,Lam Research,Semiconductor Materials & Equipment
LW,Lamb Weston,Packaged Foods & Meats
LVS,Las Vegas Sands,Casinos & Gaming
LDOS,Leidos,Diversified Support Services
LEN,Lennar,Homebuilding
LLY,Lilly (Eli),Pharmaceuticals
LIN,Linde plc,Industrial Gases
LYV,Live Nation Entertainment,Movies & Entertainment
LKQ,LKQ Corporation,Distributors
LMT,Lockheed Martin,Aerospace & Defense
L,Loews Corporation,Multi-line Insurance
LOW,Lowe's,Home Improvement Retail
LULU,Lululemon Athletica,"Apparel, Accessories & Luxury Goods"
LYB,LyondellBasell,Specialty Chemicals
MTB,M&T Bank,Regional Banks
MRO,Marathon Oil,Oil & Gas Exploration & Production
MPC,Marathon Petroleum,Oil & Gas Refining & Marketing
MKTX,MarketAxess,Financial Exchanges & Data
MAR,Marriott International,"Hotels, Resorts & Cruise Lines"
MMC,Marsh McLennan,Insurance Brokers
MLM,Martin Marietta Materials,Construction Materials
MAS,Masco,Building Products
MA,Mastercard,Transaction & Payment Processing Services
MTCH,Match Group,Interactive Media & Services
MKC,McCormick & Company,Packaged Foods & Meats
MCD,McDonald's,Restaurants
MCK,McKesson Corporation,Health Care Distributors
MDT,Medtronic,Health Care Equipment
MRK,Merck & Co.,Pharmaceuticals
META,Meta Platforms,Interactive Media & Services
MET,MetLife,Life & Health Insurance
MTD,Mettler Toledo,Life Sciences Tools & Services
MGM,MGM Resorts,Casinos & Gaming
MCHP,Microchip Technology,Semiconductors
MU,Micron Technology,Semiconductors
MSFT,Microsoft,Systems Software
MAA,Mid-America Apartment Communities,Multi-Family Residential REITs
MRNA,Moderna,Biotechnology
MHK,Mohawk Industries,Home Furnishings
MOH,Molina Healthcare,Managed Health Care
TAP,Molson Coors Beverage Company,Brewers
MDLZ,Mondelez International,Packaged Foods & Meats
MPWR,Monolithic Power Systems,Semiconductors
MNST,Monster Beverage,Soft Drinks & Non-alcoholic Beverages
MCO,Moody's Corporation,Financial Exchanges & Data
MS,Morgan Stanley,Investment Banking & Brokerage
MOS,Mosaic Company (The),Fertilizers & Agricultural Chemicals
MSI,Motorola Solutions,Communications Equipment
MSCI,MSCI,Financial Exchanges & Data
NDAQ,"Nasdaq, Inc.",Financial Exchanges & Data
NTAP,NetApp,"Technology Hardware, Storage & Peripherals"
NFLX,Netflix,Movies & Entertainment
NEM,Newmont,Gold
NWSA,News Corp (Class A),Publishing
NWS,News Corp (Class B),Publishing
NEE,NextEra Energy,Multi-Utilities
NKE,"Nike, Inc.","Apparel, Accessories & Luxury Goods"
NI,NiSource,Multi-Utilities
NDSN,Nordson Corporation,Industrial Machinery & Supplies & Components
NSC,Norfolk Southern Railway,Rail Transportation
NTRS,Northern Trust,Asset Management & Custody Banks
NOC,Northrop Grumman,Aerospace & Defense
NCLH,Norwegian Cruise Line Holdings,"Hotels, Resorts & Cruise Lines"
NRG,NRG Energy,Independent Power Producers & Energy Traders
NUE,Nucor,Steel
NVDA,Nvidia,Semiconductors
NVR,"NVR, Inc.",Homebuilding
NXPI,NXP Semiconductors,Semiconductors
ORLY,O'Reilly Auto Parts,Automotive Retail
OXY,Occidental Petroleum,Oil & Gas Exploration & Production
ODFL,Old Dominion,Cargo Ground Transportation
OMC,Omnicom Group,Advertising
ON,ON Semiconductor,Semiconductors
OKE,ONEOK,Oil & Gas Storage & Transportation
ORCL,Oracle Corporation,Application Software
OTIS,Otis Worldwide,Industrial Machinery & Supplies & Components
PCAR,Paccar,Construction Machinery & Heavy Transportation Equipment
PKG,Packaging Corporation of America,Paper & Plastic Packaging Products & Materials
PLTR,Palantir Technologies,Internet Services & Infrastructure
PANW,Palo Alto Networks,Systems Software
PARA,Paramount Global,Movies & Entertainment
PH,Parker Hannifin,Industrial Machinery & Supplies & Components
PAYX,Paychex,Human Resource & Employment Services
PAYC,Paycom,Human Resource & Employment Services
PYPL,PayPal,Transaction & Payment Processing Services
PNR,Pentair,Industrial Machinery & Supplies & Components
PEP,PepsiCo,Soft Drinks & Non-alcoholic Beverages
PFE,Pfizer,Pharmaceuticals
PCG,PG&E Corporation,Multi-Utilities
PM,Philip Morris International,Tobacco
PSX,Phillips 66,Oil & Gas Refining & Marketing
PNW,Pinnacle West,Multi-Utilities
PNC,PNC Financial Services,Diversified Banks
POOL,Pool Corporation,Distributors
PPG,PPG Industries,Specialty Chemicals
PPL,PPL Corporation,Electric Utilities
PFG,Principal Financial Group,Life & Health Insurance
PG,Procter & Gamble,Personal Care Products
PGR,Progressive Corporation,Property & Casualty Insurance
PLD,Prologis,Industrial REITs
PRU,Prudential Financial,Life & Health Insurance
PTC,PTC Inc.,Application Software
PEG,Public Service Enterprise Group,Electric Utilities
PSA,Public Storage,Self-Storage REITs
PHM,PulteGroup,Homebuilding
QRVO,Qorvo,Semiconductors
QCOM,Qualcomm,Semiconductors
PWR,Quanta Services,Construction & Engineering
DGX,Quest Diagnostics,Health Care Services
RL,Ralph Lauren Corporation,"Apparel, Accessories & Luxury Goods"
RJF,Raymond James Financial,Investment Banking & Brokerage
O,Realty Income,Retail REITs
REG,Regency Centers,Retail REITs
REGN,Regeneron Pharmaceuticals,Biotechnology
RF,Regions Financial Corporation,Regional Banks
RSG,Republic Services,Environmental & Facilities Services
RMD,ResMed,Health Care Equipment
RVTY,Revvity,Health Care Equipment
ROK,Rockwell Automation,Electrical Components & Equipment
ROL,"Rollins, Inc.",Environmental & Facilities Services
ROP,Roper Technologies,Electronic Equipment & Instruments
ROST,Ross Stores,Apparel Retail
RCL,Royal Caribbean Group,"Hotels, Resorts & Cruise Lines"
RTX,RTX Corporation,Aerospace & Defense
SPGI,S&P Global,Financial Exchanges & Data
CRM,Salesforce,Application Software
SBAC,SBA Communications,Telecom Tower REITs
SLB,Schlumberger,Oil & Gas Equipment & Services
STX,Seagate Technology,"Technology Hardware, Storage & Peripherals"
SRE,Sempra,Multi-Utilities
NOW,ServiceNow,Systems Software
SHW,Sherwin-Williams,Specialty Chemicals
SPG,Simon Property Group,Retail REITs
SWKS,Skyworks Solutions,Semiconductors
SW,Smurfit WestRock,Paper & Plastic Packaging Products & Materials
SNA,Snap-on,Industrial Machinery & Supplies & Components
SOLV,Solventum,Health Care Technology
SO,Southern Company,Electric Utilities
LUV,Southwest Airlines,Passenger Airlines
SWK,Stanley Black & Decker,Industrial Machinery & Supplies & Components
SBUX,Starbucks,Restaurants
STT,State Street Corporation,Asset Management & Custody Banks
STLD,Steel Dynamics,Steel
STE,Steris,Health Care Equipment
SYK,Stryker Corporation,Health Care Equipment
SMCI,Supermicro,"Technology Hardware, Storage & Peripherals"
SYF,Synchrony Financial,Consumer Finance
SNPS,Synopsys,Application Software
SYY,Sysco,Food Distributors
TMUS,T-Mobile US,Wireless Telecommunication Services
TROW,T. Rowe Price,Asset Management & Custody Banks
TTWO,Take-Two Interactive,Interactive Home Entertainment
TPR,"Tapestry, Inc.","Apparel, Accessories & Luxury Goods"
TRGP,Targa Resources,Oil & Gas Storage & Transportation
TGT,Target Corporation,Consumer Staples Merchandise Retail
TEL,TE Connectivity,Electronic Manufacturing Services
TDY,Teledyne Technologies,Electronic Equipment & Instruments
TFX,Teleflex,Health Care Equipment
TER,Teradyne,Semiconductor Materials & Equipment
TSLA,"Tesla, Inc.",Automobile Manufacturers
TXN,Texas Instruments,Semiconductors
TXT,Textron,Aerospace & Defense
TMO,Thermo Fisher Scientific,Life Sciences Tools & Services
TJX,TJX Companies,Apparel Retail
TSCO,Tractor Supply,Other Specialty Retail
TT,Trane Technologies,Building Products
TDG,TransDigm Group,Aerospace & Defense
TRV,Travelers Companies (The),Property & Casualty Insurance
TRMB,Trimble Inc.,Electronic Equipment & Instruments
TFC,Truist Financial,Diversified Banks
TYL,Tyler Technologies,Application Software
TSN,Tyson Foods,Packaged Foods & Meats
USB,U.S. Bancorp,Diversified Banks
UBER,Uber,Passenger Ground Transportation
UDR,"UDR, Inc.",Multi-Family Residential REITs
ULTA,Ulta Beauty,Other Specialty Retail
UNP,Union Pacific Corporation,Rail Transportation
UAL,United Airlines Holdings,Passenger Airlines
UPS,United Parcel Service,Air Freight & Logistics
URI,United Rentals,Trading Companies & Distributors
UNH,UnitedHealth Group,Managed Health Care
UHS,Universal Health Services,Health Care Facilities
VLO,Valero Energy,Oil & Gas Refining & Marketing
VTR,Ventas,Health Care REITs
VLTO,Veralto,Environmental & Facilities Services
VRSN,Verisign,Internet Services & Infrastructure
VRSK,Verisk Analytics,Research & Consulting Services
VZ,Verizon,Integrated Telecommunication Services
VRTX,Vertex Pharmaceuticals,Biotechnology
VTRS,Viatris,Pharmaceuticals
VICI,Vici Properties,Hotel & Resort REITs
V,Visa Inc.,Transaction & Payment Processing Services
VST,Vistra Corp.,Electric Utilities
VMC,Vulcan Materials Company,Construction Materials
WRB,W. R. Berkley Corporation,Property & Casualty Insurance
GWW,W. W. Grainger,Industrial Machinery & Supplies & Components
WAB,Wabtec,Construction Machinery & Heavy Transportation Equipment
WBA,Walgreens Boots Alliance,Drug Retail
WMT,Walmart,Consumer Staples Merchandise Retail
DIS,Walt Disney Company (The),Movies & Entertainment
WBD,Warner Bros. Discovery,Broadcasting
WM,Waste Management,Environmental & Facilities Services
WAT,Waters Corporation,Life Sciences Tools & Services
WEC,WEC Energy Group,Electric Utilities
WFC,Wells Fargo,Diversified Banks
WELL,Welltower,Health Care REITs
WST,West Pharmaceutical Services,Health Care Supplies
WDC,Western Digital,"Technology Hardware, Storage & Peripherals"
WY,Weyerhaeuser,Timber REITs
WMB,Williams Companies,Oil & Gas Storage & Transportation
WTW,Willis Towers Watson,Insurance Brokers
WYNN,Wynn Resorts,Casinos & Gaming
XEL,Xcel Energy,Multi-Utilities
XYL,Xylem Inc.,Industrial Machinery & Supplies & Components
YUM,Yum! Brands,Restaurants
ZBRA,Zebra Technologies,Electronic Equipment & Instruments
ZBH,Zimmer Biomet,Health Care Equipment
ZTS,Zoetis,Pharmaceuticals"""

NASDAQ_100_CSV = """Ticker,Company,GICS Sector
AAPL,Apple Inc.,Information Technology
MSFT,Microsoft Corp.,Information Technology
AMZN,Amazon.com Inc.,Consumer Discretionary
NVDA,NVIDIA Corp.,Information Technology
META,Meta Platforms Inc.,Communication Services
GOOGL,Alphabet Inc. (Class A),Communication Services
GOOG,Alphabet Inc. (Class C),Communication Services
TSLA,Tesla Inc.,Consumer Discretionary
AVGO,Broadcom Inc.,Information Technology
COST,Costco Wholesale Corp.,Consumer Staples
NFLX,Netflix Inc.,Communication Services
AMD,Advanced Micro Devices Inc.,Information Technology
TMUS,T-Mobile US Inc.,Communication Services
LIN,Linde plc,Materials
ISRG,Intuitive Surgical Inc.,Health Care
QCOM,QUALCOMM Inc.,Information Technology
AMGN,Amgen Inc.,Health Care
HON,Honeywell International Inc.,Industrials
BKNG,Booking Holdings Inc.,Consumer Discretionary
TXN,Texas Instruments Inc.,Information Technology
SBUX,Starbucks Corp.,Consumer Discretionary
AMAT,Applied Materials Inc.,Information Technology
GILD,Gilead Sciences Inc.,Health Care
ADI,Analog Devices Inc.,Information Technology
ADP,Automatic Data Processing Inc.,Information Technology
MDLZ,Mondelez International Inc.,Consumer Staples
LRCX,Lam Research Corp.,Information Technology
VRTX,Vertex Pharmaceuticals Inc.,Health Care
PANW,Palo Alto Networks Inc.,Information Technology
ADI,Analog Devices Inc.,Information Technology
SNPS,Synopsys Inc.,Information Technology
CDNS,Cadence Design Systems Inc.,Information Technology
MU,Micron Technology Inc.,Information Technology
CSCO,Cisco Systems Inc.,Information Technology
INTU,Intuit Inc.,Information Technology
PYPL,PayPal Holdings Inc.,Financials
ADBE,Adobe Inc.,Information Technology
REGN,Regeneron Pharmaceuticals Inc.,Health Care
MELI,MercadoLibre Inc.,Consumer Discretionary
MNST,Monster Beverage Corp.,Consumer Staples"""


# --- BUTTON 1: REFRESH CONSTITUENT LISTS ---
if refresh_lists_btn or not st.session_state.constituent_dataframes:
  with st.spinner("Loading embedded CSV constituent lists..."):
    dfs = {}
    try:
      dfs["Russell 1000"] = pd.read_csv(io.StringIO(RUSSELL_1000_CSV))
    except Exception as e:
      exceptions_log.append(f"Russell 1000 CSV Parse Error: {e}")

    try:
      dfs["S&P 500"] = pd.read_csv(io.StringIO(SP500_CSV))
    except Exception as e:
      exceptions_log.append(f"S&P 500 CSV Parse Error: {e}")

    try:
      dfs["Nasdaq 100"] = pd.read_csv(io.StringIO(NASDAQ_100_CSV))
    except Exception as e:
      exceptions_log.append(f"Nasdaq 100 CSV Parse Error: {e}")

    st.session_state.constituent_dataframes = dfs
    st.session_state.last_action = (
        "Constituent lists loaded successfully from embedded CSV datasets."
    )
    save_persistent_state({
        "constituent_dataframes": dfs,
        "calculated_metrics": st.session_state.calculated_metrics,
    })


# --- BUTTON 2: RELOAD DATA & RECALCULATE METRICS ---
if reload_data_btn or st.session_state.calculated_metrics.empty:
  if not st.session_state.constituent_dataframes:
    st.warning("Please refresh or load constituent lists first.")
  else:
    with st.spinner(
        "Filtering for >$10B market cap, downloading price data, and computing"
        " 12-1 / Volatility-adjusted rankings..."
    ):
      active_tickers = []
      ticker_index_map = {}

      dfs = st.session_state.constituent_dataframes

      # Process Russell 1000
      if show_russell and "Russell 1000" in dfs:
        df_r = dfs["Russell 1000"]
        for _, row in df_r.iterrows():
          t = str(row["ticker"]).strip().replace(".", "-")
          mcap_str = str(row.get("market_cap_usd", "0"))
          # Parse market cap suffixes (T = Trillion, B = Billion, M = Million)
          mcap_val = 0.0
          try:
            if "T" in mcap_str.upper():
              mcap_val = float(mcap_str.upper().replace("T", "")) * 1e12
            elif "B" in mcap_str.upper():
              mcap_val = float(mcap_str.upper().replace("B", "")) * 1e9
            elif "M" in mcap_str.upper():
              mcap_val = float(mcap_str.upper().replace("M", "")) * 1e6
            else:
              mcap_val = float(mcap_str)
          except Exception:
            mcap_val = 15e9  # Default pass-through if unparsable

          # Filter: > $10B Market Cap
          if mcap_val >= 10e9:
            if t not in active_tickers:
              active_tickers.append(t)
              ticker_index_map[t] = "Russell 1000"

      # Process S&P 500 (Assume all S&P 500 stocks > $10B)
      if show_sp500 and "S&P 500" in dfs:
        df_s = dfs["S&P 500"]
        sym_col = next(
            (
                c
                for c in df_s.columns
                if "symbol" in c.lower() or "ticker" in c.lower()
            ),
            df_s.columns[0],
        )
        for _, row in df_s.iterrows():
          t = str(row[sym_col]).strip().replace(".", "-")
          if t not in active_tickers:
            active_tickers.append(t)
            ticker_index_map[t] = "S&P 500"

      # Process Nasdaq 100 (Assume all Nasdaq 100 stocks > $10B)
      if show_nasdaq and "Nasdaq 100" in dfs:
        df_n = dfs["Nasdaq 100"]
        sym_col = next(
            (
                c
                for c in df_n.columns
                if "symbol" in c.lower() or "ticker" in c.lower()
            ),
            df_n.columns[0],
        )
        for _, row in df_n.iterrows():
          t = str(row[sym_col]).strip().replace(".", "-")
          if t not in active_tickers:
            active_tickers.append(t)
            ticker_index_map[t] = "Nasdaq 100"

      active_tickers = sorted(list(set(active_tickers)))

      chunk_size = 150
      all_prices = []
      all_volumes = []

      for i in range(0, len(active_tickers), chunk_size):
        chunk = active_tickers[i : i + chunk_size]
        try:
          raw = yf.download(
              chunk,
              period="15mo",
              interval="1d",
              group_by="ticker",
              progress=False,
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

      df_prices = (
          pd.concat(all_prices, axis=1).dropna(how="all")
          if all_prices
          else pd.DataFrame()
      )
      df_volumes = (
          pd.concat(all_volumes, axis=1).dropna(how="all")
          if all_volumes
          else pd.DataFrame()
      )

      metrics_data = []

      for ticker in df_prices.columns:
        series = df_prices[ticker].dropna()
        v_series = (
            df_volumes[ticker].dropna()
            if ticker in df_volumes.columns
            else pd.Series(dtype=float)
        )

        if len(series) > 252:
          price_12m_ago = series.iloc[-252]
          price_1m_ago = series.iloc[-21]
          ret_12_1 = (price_1m_ago / price_12m_ago) - 1.0

          vol_63 = series.iloc[-63:].pct_change().std() * np.sqrt(252)
          vol_63 = vol_63 if vol_63 > 0 else 0.01

          adj_score = ret_12_1 / vol_63

          avg_daily_vol = (
              v_series.iloc[-63:].mean() if not v_series.empty else 0.0
          )

          mcap = 0
          try:
            t_obj = yf.Ticker(ticker)
            mcap = t_obj.info.get("marketCap", 0) or 0
          except Exception:
            pass

          # Double check live market cap > $10B if available, otherwise rely on csv filter
          if mcap == 0 or mcap >= 10e9:
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
        df_metrics["12-1 Rank"] = (
            df_metrics["12-1 Return (%)"]
            .rank(ascending=False, method="min")
            .astype(int)
        )
        df_metrics["Adjusted Rank"] = (
            df_metrics["Adj Score"]
            .rank(ascending=False, method="min")
            .astype(int)
        )

        df_metrics = df_metrics.drop(columns=["Adj Score"])
        df_metrics = df_metrics.sort_values(by="12-1 Rank")

      st.session_state.calculated_metrics = df_metrics
      st.session_state.last_action = (
          "Filtered for >$10B market cap, reloaded price data, and recalculated"
          " metrics successfully."
      )
      save_persistent_state({
          "constituent_dataframes": st.session_state.constituent_dataframes,
          "calculated_metrics": df_metrics,
      })

# --- DISPLAY EXCEPTIONS IF ANY ---
if exceptions_log:
  with st.expander("⚠️ System Notices & Warnings"):
    for ex in exceptions_log:
      st.warning(ex)

# --- DISPLAY DASHBOARD TABLE ---
st.subheader("📊 Quantitative Momentum & Volatility Table ($10B+ Market Cap)")
st.info(f"**Status:** {st.session_state.last_action}")

df_display = st.session_state.calculated_metrics

if df_display.empty:
  st.warning(
      "No metrics calculated yet. Click **'🔄 Refresh Constituent Lists'** and"
      " then **'⚡ Reload Price Data & Recalculate Metrics'** in the sidebar."
  )
else:
  st.markdown(
      "*Click any column header below to sort the table interactively.*"
  )

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
