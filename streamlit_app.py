import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# 1. Настройка страницы
st.set_page_config(page_title="Финансы Холдинга", layout="wide")
st.title("💰 Управление финансами: ПП / Ш / Д")

# 2. Подключение к Google Таблице (Кэшируем, чтобы не грузить каждый раз)
@st.cache_resource
def get_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # Берем секреты из настроек облака Streamlit
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # Вставьте сюда ИМЯ вашей таблицы (как оно написано сверху в браузере)
    sheet = client.open("Finance_DB").worksheet("data") 
    return sheet

try:
    sheet = get_connection()
except Exception as e:
    st.error(f"Ошибка подключения к Гугл Таблице. Проверьте имя файла и доступы. Детали: {e}")
    st.stop()

# 3. Боковая панель для ввода данных
with st.sidebar:
    st.header("📝 Новая операция")
    with st.form("entry_form", clear_on_submit=True):
        date = st.date_input("Дата", datetime.now())
        company = st.selectbox("Юрлицо", ["ООО ПП", "ИП Ш", "ИП Д", "Наличные"])
        category = st.selectbox("Категория", [
            "Приход (Выручка)", 
            "Закуп товара (Китай)", 
            "Закуп (РФ)",
            "Маркетинг (Директ/Авито)", 
            "ФОТ (Зарплаты)", 
            "Аренда/Офис",
            "Налоги",
            "Внутренний перевод",
            "Вывод средств/Личное"
        ])
        project = st.text_input("Проект / Клиент (опционально)")
        amount = st.number_input("Сумма (₽)", min_value=0, step=1000)
        comms = st.text_area("Комментарий")
        
        # Логика: Приход или Расход
        op_type = st.radio("Тип операции", ["Расход", "Приход"])
        
        submitted = st.form_submit_button("✅ ЗАПИСАТЬ")
        
        if submitted:
            income = amount if op_type == "Приход" else 0
            expense = amount if op_type == "Расход" else 0
            
            # Запись в Гугл Таблицу
            new_row = [str(date), company, category, project, income, expense, comms]
            sheet.append_row(new_row)
            st.success("Сохранено!")
            # Сброс кэша данных, чтобы таблица обновилась
            st.cache_data.clear()

# 4. Основной экран - Дашборд
st.subheader("📊 Текущая ситуация (Весь холдинг)")

def load_data():
    data = sheet.get_all_records()
    return pd.DataFrame(data)

df = load_data()

if not df.empty:
    # Преобразуем числа
    df['Приход'] = pd.to_numeric(df['Приход'], errors='coerce').fillna(0)
    df['Расход'] = pd.to_numeric(df['Расход'], errors='coerce').fillna(0)

    # Исключаем внутренние переводы из расчета ПРИБЫЛИ, 
    # но оставляем их для расчета ОСТАТКА (Cash)
    real_income = df[df['Категория'] != "Внутренний перевод"]['Приход'].sum()
    real_expense = df[df['Категория'] != "Внутренний перевод"]['Расход'].sum()
    
    # Остаток в кассе (включая все движения денег)
    cash_on_hand = df['Приход'].sum() - df['Расход'].sum()
    
    # Чистая прибыль (только коммерческие операции)
    net_profit = real_income - real_expense

    col1, col2, col3 = st.columns(3)
    col1.metric("Общая выручка", f"{real_income:,.0f} ₽")
    col2.metric("Чистая прибыль", f"{net_profit:,.0f} ₽")
    col3.metric("Остаток в кассе (Cash)", f"{cash_on_hand:,.0f} ₽")

    st.divider()

    # Таблица последних операций
    st.write("Последние 5 операций:")
    st.dataframe(df.tail(5))

else:
    st.info("В таблице пока нет данных. Добавьте первую запись слева!")
