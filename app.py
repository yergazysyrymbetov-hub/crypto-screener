import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# Настройки страницы
st.set_page_config(page_title="Bybit Futures Screener", layout="wide", page_icon="🚀")

# Функция загрузки данных с кэшированием
@st.cache_data(ttl=60)
def load_market_data():
    try:
        # Bybit API v5 - тикеры с объемом и фандингом
        url = "https://api.bybit.com/v5/market/tickers"
        params = {
            "category": "linear",  # USDT perpetual contracts
            "limit": 1000
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('retCode') != 0:
            st.error(f"Ошибка API Bybit: {data.get('retMsg')}")
            return pd.DataFrame()
        
        tickers = data.get('result', {}).get('list', [])
        
        if not tickers:
            st.error("Пустой ответ от API Bybit")
            return pd.DataFrame()
        
        # Создаем DataFrame
        df = pd.DataFrame(tickers)
        
        # Фильтруем только USDT пары и активные
        df = df[df['symbol'].str.endswith('USDT')]
        df = df[df['status'] == 'Trading']
        
        # Конвертируем числовые поля
        numeric_cols = ['lastPrice', 'price24hPcnt', 'volume24h', 'turnover24h', 'fundingRate', 'openInterest']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Расчет метрик
        # Funding Rate в процентах
        df['Funding %'] = df['fundingRate'] * 100
        
        # Изменение цены за 24ч в процентах
        df['Change 24h %'] = df['price24hPcnt'] * 100
        
        # Объем в USDT (turnover)
        df['Volume USDT'] = df['turnover24h']
        
        # Открытый интерес
        df['Open Interest'] = df['openInterest']
        
        # Индекс Импульса: |изменение цены| * объем в миллионах
        df['Impulse Score'] = abs(df['Change 24h %']) * (df['Volume USDT'] / 1_000_000)
        
        # Скрываем ненужные колонки
        df = df.drop(columns=['status', 'price24hPcnt', 'fundingRate', 'turnover24h', 'openInterest'], errors='ignore')
        
        return df
        
    except Exception as e:
        st.error(f"Ошибка загрузки данных с Bybit: {str(e)}")
        return pd.DataFrame()

# Интерфейс
st.title("🚀 Bybit Perpetual Futures Screener")
st.caption("Данные обновляются каждые 60 секунд | Bybit USDT Perpetual Contracts")

# Кнопка ручного обновления
if st.button("🔄 Обновить данные сейчас"):
    st.cache_data.clear()
    st.rerun()

# Загружаем данные
df = load_market_data()

if not df.empty:
    # Боковая панель с фильтрами
    st.sidebar.header("⚙️ Фильтры")
    
    min_vol = st.sidebar.number_input(
        "Мин. объем за 24ч (USDT)", 
        value=10_000_000, 
        step=5_000_000,
        min_value=0
    )
    
    min_oi = st.sidebar.number_input(
        "Мин. открытый интерес (USDT)", 
        value=5_000_000, 
        step=2_000_000,
        min_value=0
    )
    
    funding_threshold = st.sidebar.slider(
        "Порог фандинга (%)", 
        min_value=0.0, 
        max_value=0.1, 
        value=0.01, 
        step=0.001
    )
    
    show_all = st.sidebar.checkbox("Показать все (игнорировать фильтры)")
    
    if not show_all:
        df = df[(df['Volume USDT'] >= min_vol) & (df['Open Interest'] >= min_oi)]
    
    # Верхние метрики
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всего пар", len(df))
    col2.metric("Средний Funding", f"{df['Funding %'].mean():.4f}%")
    col3.metric("Макс. Volume", f"${df['Volume USDT'].max()/1_000_000:.1f}M")
    col4.metric("Макс. Impulse", f"{df['Impulse Score'].max():.2f}")
    
    st.markdown("---")
    
    # Быстрые фильтры
    st.subheader("🎯 Быстрые фильтры")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔥 Высокий Funding", use_container_width=True):
            df = df[df['Funding %'] > funding_threshold]
    
    with col2:
        if st.button("📉 Отрицательный Funding", use_container_width=True):
            df = df[df['Funding %'] < -funding_threshold]
    
    with col3:
        if st.button("💎 Топ по объему", use_container_width=True):
            df = df.sort_values('Volume USDT', ascending=False).head(20)
    
    with col4:
        if st.button("⚡ Топ по импульсу", use_container_width=True):
            df = df.sort_values('Impulse Score', ascending=False).head(20)
    
    st.markdown("---")
    
    # Выбор колонок для отображения
    display_cols = ['symbol', 'lastPrice', 'Change 24h %', 'Volume USDT', 'Open Interest', 'Funding %', 'Impulse Score']
    display_df = df[display_cols].copy()
    
    # Сортировка по умолчанию
    display_df = display_df.sort_values(by='Impulse Score', ascending=False)
    
    # Отображение таблицы с форматированием
    st.dataframe(
        display_df.style.format({
            'Volume USDT': '${:,.0f}',
            'Open Interest': '${:,.0f}',
            'Change 24h %': '{:.2f}%',
            'Funding %': '{:.4f}%',
            'Impulse Score': '{:.2f}',
            'lastPrice': '${:.4f}'
        })
        # Подсветка аномалий
        .applymap(lambda x: 'background-color: #ffcccc' if x > 0.01 else '', subset=['Funding %'])
        .applymap(lambda x: 'background-color: #ccffcc' if x < -0.01 else '', subset=['Funding %'])
        .applymap(lambda x: 'background-color: #ffffcc' if x > 100 else '', subset=['Impulse Score']),
        
        use_container_width=True,
        height=600,
        column_config={
            "symbol": st.column_config.TextColumn("Пара", width="medium"),
            "lastPrice": st.column_config.NumberColumn("Цена", format="$%.4f"),
            "Change 24h %": st.column_config.NumberColumn("24ч", format="%.2f%%"),
            "Volume USDT": st.column_config.NumberColumn("Объем 24ч", format="$%d"),
            "Open Interest": st.column_config.NumberColumn("OI", format="$%d", help="Открытый интерес"),
            "Funding %": st.column_config.NumberColumn("Funding", format="%.4f%%", help="Ставка финансирования"),
            "Impulse Score": st.column_config.NumberColumn("Impulse", format="%.2f", help="Индекс импульса")
        }
    )
    
    # Информация
    st.markdown("---")
    st.info("""
    **💡 Как использовать:**
    
    - **Высокий Funding (>0.01%)** - рынок перегрет лонгами, возможен long squeeze (падение)
    - **Отрицательный Funding (<-0.01%)** - рынок перегрет шортами, возможен short squeeze (рост)
    - **Высокий Impulse Score** - сильное движение с большим объемом (начало тренда)
    - **Открытый интерес (OI)** - количество открытых позиций. Рост OI = усиление тренда
    """)
    
else:
    st.warning("⚠️ Не удалось загрузить данные. Проверьте подключение или попробуйте позже.")

# Footer
st.markdown("---")
st.caption(f"Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Data source: Bybit API v5")
