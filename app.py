import streamlit as st
import requests
import pandas as pd
import numpy as np

# Настройки страницы
st.set_page_config(page_title="Crypto Futures Screener", layout="wide", page_icon="🚀")

# Функция загрузки данных с кэшированием (обновление раз в 60 сек)
@st.cache_data(ttl=60)
def load_market_data():
    try:
        # 1. Тикеры (Цена, Объем, Изменение)
        tickers = requests.get('https://fapi.binance.com/fapi/v1/ticker/24hr', timeout=10).json()
        # 2. Ставки финансирования
        funding = requests.get('https://fapi.binance.com/fapi/v1/premiumIndex', timeout=10).json()
        
        df_t = pd.DataFrame(tickers)
        df_f = pd.DataFrame(funding)
        
        # Объединяем и фильтруем только пары к USDT
        df = pd.merge(df_t, df_f[['symbol', 'lastFundingRate']], on='symbol')
        df = df[df['symbol'].str.endswith('USDT')]
        
        # Конвертируем типы данных
        for col in ['quoteVolume', 'priceChangePercent', 'lastFundingRate', 'weightedAvgPrice']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # Переводим фандинг в проценты
        df['Funding %'] = df['lastFundingRate'] * 100 
        
        # Расчет Индекса Импульса (Абсолютное изменение цены * Объем в млн)
        # Чем выше индекс, тем сильнее движение, подкрепленное деньгами
        df['Impulse Score'] = abs(df['priceChangePercent']) * (df['quoteVolume'] / 1_000_000)
        
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки данных с Binance: {e}")
        return pd.DataFrame()

# Интерфейс
st.title("🚀 Фьючерсный Скринер (Binance Perps)")
st.caption("Данные обновляются каждые 60 секунд. Фильтр по ликвидности и аномалиям фандинга.")

# Кнопка ручного обновления
if st.button("🔄 Обновить данные сейчас"):
    st.cache_data.clear()
    st.rerun()

df = load_market_data()

if not df.empty:
    # Боковая панель с фильтрами
    st.sidebar.header("⚙️ Фильтры")
    min_vol = st.sidebar.number_input("Мин. объем за 24ч (USDT)", value=20_000_000, step=5_000_000)
    show_all = st.sidebar.checkbox("Показать все (игнорировать фильтры объема)")
    
    if not show_all:
        df = df[df['quoteVolume'] >= min_vol]

    # Верхние метрики
    col1, col2, col3 = st.columns(3)
    col1.metric("Всего монет в скринере", len(df))
    col2.metric("Средний Фандинг", f"{df['Funding %'].mean():.4f}%")
    col3.metric("Макс. Импульс", f"{df['Impulse Score'].max():.2f}")

    st.markdown("---")

    # Форматирование и сортировка
    display_df = df[['symbol', 'lastPrice', 'priceChangePercent', 'quoteVolume', 'Funding %', 'Impulse Score']].copy()
    display_df = display_df.sort_values(by='Impulse Score', ascending=False)

    # Отображение таблицы с подсветкой
    st.dataframe(
        display_df.style.format({
            'quoteVolume': '${:,.0f}',
            'priceChangePercent': '{:.2f}%',
            'Funding %': '{:.4f}%',
            'Impulse Score': '{:.2f}'
        })
        # Подсветка аномального фандинга (красный - перегретые лонги, зеленый - перегретые шорты)
        .highlight_max(color='#ffcccc', subset=['Funding %'])
        .highlight_min(color='#ccffcc', subset=['Funding %'])
        # Подсветка максимального импульса
        .highlight_max(color='#ffffcc', subset=['Impulse Score']),
        use_container_width=True,
        height=600,
        column_config={
            "symbol": "Пара",
            "lastPrice": st.column_config.NumberColumn("Цена", format="%.4f"),
            "priceChangePercent": st.column_config.NumberColumn("Изменение 24ч", format="%.2f%%"),
            "quoteVolume": st.column_config.NumberColumn("Объем 24ч", format="$%d"),
            "Funding %": st.column_config.NumberColumn("Фандинг", format="%.4f%%", help="Отрицательный = шорт-сквиз, Высокий = лонг-сквиз"),
            "Impulse Score": st.column_config.NumberColumn("Индекс Импульса", format="%.2f", help="Сила движения * Объем")
        }
    )
    
    st.info("💡 **Как пользоваться:** Ищите монеты с высоким **Impulse Score** (начало тренда). Если **Фандинг** экстремально высокий (>0.03%) — ждите отката (лонг-сквиз). Если сильно отрицательный (<-0.03%) — ищите точку для лонга (шорт-сквиз).")
