import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Binance Futures Screener", layout="wide", page_icon="🚀")

@st.cache_data(ttl=60)
def load_market_data():
    try:
        # Binance Futures API
        tickers_url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
        funding_url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        
        r1 = requests.get(tickers_url, headers=headers, timeout=10)
        r2 = requests.get(funding_url, headers=headers, timeout=10)
        
        tickers = r1.json()
        funding = r2.json()
        
        df_t = pd.DataFrame(tickers)
        df_f = pd.DataFrame(funding)
        
        # Merge
        df = pd.merge(df_t, df_f[['symbol', 'lastFundingRate']], on='symbol', how='inner')
        df = df[df['symbol'].str.endswith('USDT')]
        
        # Convert
        for col in ['quoteVolume', 'priceChangePercent', 'lastFundingRate']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['Funding %'] = df['lastFundingRate'] * 100
        df['Change 24h %'] = df['priceChangePercent']
        df['Volume USDT'] = df['quoteVolume']
        df['Impulse Score'] = abs(df['Change 24h %']) * (df['Volume USDT'] / 1_000_000)
        
        return df[['symbol', 'lastPrice', 'Change 24h %', 'Volume USDT', 'Funding %', 'Impulse Score']]
        
    except Exception as e:
        st.error(f"Ошибка: {e}")
        return pd.DataFrame()

st.title("🚀 Binance Futures Screener")
st.caption("Binance USDT-M Perpetual Contracts")

if st.button("🔄 Обновить"):
    st.cache_data.clear()
    st.rerun()

df = load_market_data()

if not df.empty:
    st.sidebar.header("Фильтры")
    min_vol = st.sidebar.number_input("Мин. объем", value=20_000_000, step=5_000_000)
    
    if st.sidebar.checkbox("Применить", value=True):
        df = df[df['Volume USDT'] >= min_vol]
    
    col1, col2 = st.columns(2)
    col1.metric("Пар", len(df))
    col2.metric("Средний Funding", f"{df['Funding %'].mean():.4f}%")
    
    df = df.sort_values('Impulse Score', ascending=False)
    
    st.dataframe(
        df.style.format({
            'Volume USDT': '${:,.0f}',
            'Change 24h %': '{:.2f}%',
            'Funding %': '{:.4f}%',
            'lastPrice': '${:.4f}'
        }),
        use_container_width=True,
        height=600
    )
    
    st.info("💡 **Funding > 0.01%** = long squeeze возможен | **Funding < -0.01%** = short squeeze")
else:
    st.warning("Нет данных")

st.caption(f"Обновлено: {datetime.now().strftime('%H:%M:%S')}")
