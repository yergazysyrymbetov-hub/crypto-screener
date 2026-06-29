import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Настройки страницы
st.set_page_config(page_title="Bybit Futures Screener", layout="wide", page_icon="🚀")

# Функция загрузки данных
@st.cache_data(ttl=60)
def load_market_data():
    try:
        # Bybit API v5
        url = "https://api.bybit.com/v5/market/tickers"
        params = {
            "category": "linear",
            "limit": "1000"
        }
        
        # Заголовки обязательны для Bybit
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        # Проверяем статус код
        if response.status_code != 200:
            st.error(f"HTTP ошибка: {response.status_code}")
            st.error(f"Ответ: {response.text[:200]}")
            return pd.DataFrame()
        
        # Пробуем распарсить JSON
        try:
            data = response.json()
        except Exception as json_err:
            st.error(f"Ошибка JSON: {json_err}")
            st.error(f"Получен текст: {response.text[:300]}")
            return pd.DataFrame()
        
        # Проверяем код ответа Bybit
        ret_code = data.get('retCode')
        if ret_code != 0:
            st.error(f"Bybit API ошибка: {data.get('retMsg', 'Неизвестная ошибка')}")
            return pd.DataFrame()
        
        tickers = data.get('result', {}).get('list', [])
        
        if not tickers:
            st.warning("Нет данных от API")
            return pd.DataFrame()
        
        # Создаем DataFrame
        df = pd.DataFrame(tickers)
        
        # Фильтруем USDT пары и активные
        df = df[df['symbol'].str.endswith('USDT')]
        df = df[df['status'] == 'Trading']
        
        # Конвертируем числовые поля
        numeric_cols = ['lastPrice', 'price24hPcnt', 'volume24h', 'turnover24h', 'fundingRate', 'openInterest']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Метрики
        df['Funding %'] = df['fundingRate'] * 100
        df['Change 24h %'] = df['price24hPcnt'] * 100
        df['Volume USDT'] = df['turnover24h']
        df['Open Interest'] = df['openInterest']
        df['Impulse Score'] = abs(df['Change 24h %']) * (df['Volume USDT'] / 1_000_000)
        
        # Убираем лишние колонки
        df = df.drop(columns=['status', 'price24hPcnt', 'fundingRate', 'turnover24h', 'openInterest'], errors='ignore')
        
        return df
        
    except requests.exceptions.Timeout:
        st.error("Превышено время ожидания ответа от Bybit")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"Ошибка подключения: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Неизвестная ошибка: {type(e).__name__}: {e}")
        return pd.DataFrame()

# Интерфейс
st.title("🚀 Bybit Perpetual Futures Screener")
st.caption("Данные обновляются каждые 60 секунд | Bybit USDT Perpetual Contracts")

if st.button("🔄 Обновить данные сейчас"):
    st.cache_data.clear()
    st.rerun()

df = load_market_data()

if not df.empty:
    # Фильтры
    st.sidebar.header("⚙️ Фильтры")
    min_vol = st.sidebar.number_input("Мин. объем (USDT)", value=10_000_000, step=5_000_000)
    min_oi = st.sidebar.number_input("Мин. OI (USDT)", value=5_000_000, step=2_000_000)
    
    if st.sidebar.checkbox("Применить фильтры", value=True):
        df = df[(df['Volume USDT'] >= min_vol) & (df['Open Interest'] >= min_oi)]
    
    # Метрики
    col1, col2, col3 = st.columns(3)
    col1.metric("Всего пар", len(df))
    col2.metric("Средний Funding", f"{df['Funding %'].mean():.4f}%")
    col3.metric("Топ Volume", f"${df['Volume USDT'].max()/1_000_000:.1f}M")
    
    st.markdown("---")
    
    # Таблица
    display_df = df[['symbol', 'lastPrice', 'Change 24h %', 'Volume USDT', 'Open Interest', 'Funding %', 'Impulse Score']].copy()
    display_df = display_df.sort_values('Impulse Score', ascending=False)
    
    st.dataframe(
        display_df.style.format({
            'Volume USDT': '${:,.0f}',
            'Open Interest': '${:,.0f}',
            'Change 24h %': '{:.2f}%',
            'Funding %': '{:.4f}%',
            'lastPrice': '${:.4f}'
        }),
        use_container_width=True,
        height=600
    )
    
    st.info("💡 **Funding > 0.01%** = перегретые лонги | **Funding < -0.01%** = перегретые шорты")
else:
    st.warning("⚠️ Данные не загружены. Попробуйте обновить через минуту.")

st.caption(f"Обновлено: {datetime.now().strftime('%H:%M:%S')} | Bybit API v5")
