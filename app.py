import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Binance Futures Screener", layout="wide", page_icon="🚀")

# Список прокси для обхода блокировки
PROXIES = [
    "https://api.allorigins.win/raw?url=",
    "https://api.codetabs.com/v1/proxy?quest=",
]

@st.cache_data(ttl=60)
def load_market_data():
    try:
        tickers_url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
        funding_url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        # Пробуем прямой запрос
        try:
            r1 = requests.get(tickers_url, headers=headers, timeout=10)
            r2 = requests.get(funding_url, headers=headers, timeout=10)
            
            if r1.status_code == 200 and r2.status_code == 200:
                tickers = r1.json()
                funding = r2.json()
            else:
                raise Exception(f"HTTP {r1.status_code}, {r2.status_code}")
                
        except Exception as direct_err:
            st.warning(f"Прямой доступ заблокирован, используем прокси...")
            
            # Пробуем через прокси
            for proxy_base in PROXIES:
                try:
                    proxy_url = f"{proxy_base}{tickers_url}"
                    r1 = requests.get(proxy_url, headers=headers, timeout=15)
                    
                    proxy_url = f"{proxy_base}{funding_url}"
                    r2 = requests.get(proxy_url, headers=headers, timeout=15)
                    
                    if r1.status_code == 200 and r2.status_code == 200:
                        tickers = r1.json()
                        funding = r2.json()
                        break
                except:
                    continue
            else:
                st.error("Не удалось подключиться через прокси")
                return pd.DataFrame()
        
        # Проверка данных
        if not isinstance(tickers, list) or not isinstance(funding, list):
            st.error("Неверный формат данных")
            return pd.DataFrame()
        
        df_t = pd.DataFrame(tickers)
        df_f = pd.DataFrame(funding)
        
        # Merge
        df = pd.merge(df_t, df_f[['symbol', 'lastFundingRate']], on='symbol', how='inner')
        df = df[df['symbol'].str.endswith('USDT')].copy()
        
        if df.empty:
            return pd.DataFrame()
        
        # Конвертация
        for col in ['quoteVolume', 'priceChangePercent', 'lastFundingRate', 'lastPrice']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Метрики
        df['Funding %'] = df['lastFundingRate'] * 100
        df['Change 24h %'] = df['priceChangePercent']
        df['Volume USDT'] = df['quoteVolume']
        df['Impulse Score'] = abs(df['Change 24h %']) * (df['Volume USDT'] / 1_000_000)
        
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
        st.error(f"Ошибка: {type(e).__name__}: {str(e)[:200]}")
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
    
    if st.sidebar.checkbox("Применить", value=True):
        df = df[df['Volume USDT'] >= min_vol].copy()
    
    if not df.empty:
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
        
        st.info("💡 **Funding > 0.01%** = long squeeze | **Funding < -0.01%** = short squeeze")
    else:
        st.warning("Нет данных по фильтру")
else:
    st.warning("⚠️ Нет данных")

st.caption(f"Обновлено: {datetime.now().strftime('%H:%M:%S')}")
