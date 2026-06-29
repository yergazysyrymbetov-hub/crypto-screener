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
        
        if r1.status_code != 200 or r2.status_code != 200:
            st.error(f"HTTP ошибка: {r1.status_code}, {r2.status_code}")
            return pd.DataFrame()
        
        tickers = r1.json()
        funding = r2.json()
        
        # Проверка что это списки
        if not isinstance(tickers, list) or not isinstance(funding, list):
            st.error("Неверный формат данных")
            return pd.DataFrame()
        
        df_t = pd.DataFrame(tickers)
        df_f = pd.DataFrame(funding)
        
        # Merge по symbol
        df = pd.merge(df_t, df_f[['symbol', 'lastFundingRate']], on='symbol', how='inner')
        
        # Фильтр USDT
        df = df[df['symbol'].str.endswith('USDT')].copy()
        
        if df.empty:
            st.warning("Нет USDT пар")
            return pd.DataFrame()
        
        # Конвертация числовых полей
        numeric_cols = ['quoteVolume', 'priceChangePercent', 'lastFundingRate', 'lastPrice']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Метрики
        df['Funding %'] = df['lastFundingRate'] * 100
        df['Change 24h %'] = df['priceChangePercent']
        df['Volume USDT'] = df['quoteVolume']
        df['Impulse Score'] = abs(df['Change 24h %']) * (df['Volume USDT'] / 1_000_000)
        
        # Выбираем нужные колонки
        result_df = pd.DataFrame({
            'symbol': df['symbol'],
            'lastPrice': df['lastPrice'],
            'Change 24h %': df['Change 24h %'],
            'Volume USDT': df['Volume USDT'],
            'Funding %': df['Funding %'],
            'Impulse Score': df['Impulse Score']
        })
        
        return result_df
        
    except Exception as e:
        st.error(f"Ошибка: {type(e).__name__}: {e}")
        return pd.DataFrame()

st.title("🚀 Binance Futures Screener")
st.caption("Binance USDT-M Perpetual Contracts")

if st.button("🔄 Обновить"):
    st.cache_data.clear()
    st.rerun()

df = load_market_data()

if not df.empty:
    st.sidebar.header("⚙️ Фильтры")
    min_vol = st.sidebar.number_input("Мин. объем (USDT)", value=20_000_000, step=5_000_000)
    
    apply_filter = st.sidebar.checkbox("Применить фильтр объема", value=True)
    
    if apply_filter:
        df_filtered = df[df['Volume USDT'] >= min_vol].copy()
    else:
        df_filtered = df.copy()
    
    if df_filtered.empty:
        st.warning("Нет данных по выбранным фильтрам")
    else:
        col1, col2 = st.columns(2)
        col1.metric("Всего пар", len(df_filtered))
        col2.metric("Средний Funding", f"{df_filtered['Funding %'].mean():.4f}%")
        
        # Сортировка
        df_sorted = df_filtered.sort_values('Impulse Score', ascending=False)
        
        # Таблица
        st.dataframe(
            df_sorted.style.format({
                'Volume USDT': '${:,.0f}',
                'Change 24h %': '{:.2f}%',
                'Funding %': '{:.4f}%',
                'lastPrice': '${:.4f}',
                'Impulse Score': '{:.2f}'
            }),
            use_container_width=True,
            height=600
        )
        
        st.info("💡 **Funding > 0.01%** = long squeeze возможен | **Funding < -0.01%** = short squeeze")
else:
    st.warning("⚠️ Нет данных. Попробуйте обновить через минуту.")

st.caption(f"Обновлено: {datetime.now().strftime('%H:%M:%S')} | Binance API")
