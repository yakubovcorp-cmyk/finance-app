import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="Финансы Холдинга", layout="wide")

@st.cache_resource
def get_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # Убедитесь, что название таблицы совпадает!
    return client.open("Finance_DB")

doc = get_connection()
sheet_data = doc.worksheet("data")
sheet_report = doc.worksheet("report")

st.title("💰 Управление холдингом: ПП / Ш / Д")

# ВВОД ДАННЫХ
with st.sidebar:
    mode = st.radio("Тип операции", ["Обычный Приход/Расход", "Внутренний перевод"])
    
    with st.form("main_form", clear_on_submit=True):
        date = str(st.date_input("Дата", datetime.now()))
        
        if mode == "Обычный Приход/Расход":
            company = st.selectbox("Юрлицо", ["ООО ПП", "ИП Ш", "ИП Д", "Наличные"])
            category = st.selectbox("Категория", ["Приход (Выручка)", "Закуп товара (Китай)", "Закуп (РФ)", "Маркетинг (Директ/Авито)", "ФОТ (Зарплаты)", "Аренда/Офис", "Налоги", "Вывод средств/Личное"])
            op_type = st.radio("Движение", ["Расход", "Приход"])
            amount = st.number_input("Сумма (₽)", min_value=0, step=1000)
            project = st.text_input("Проект")
            comms = st.text_area("Комментарий")
            
            if st.form_submit_button("Записать"):
                inc = amount if op_type == "Приход" else 0
                exp = amount if op_type == "Расход" else 0
                sheet_data.append_row([date, company, category, project, inc, exp, comms])
                st.success("Данные внесены")
                st.cache_data.clear()

        else:  # ВНУТРЕННИЙ ПЕРЕВОД
            source = st.selectbox("ОТКУДА (Списание)", ["ООО ПП", "ИП Ш", "ИП Д", "Наличные"])
            target = st.selectbox("КУДА (Пополнение)", ["ИП Ш", "ООО ПП", "ИП Д", "Наличные"])
            amount = st.number_input("Сумма перевода (₽)", min_value=0, step=1000)
            comms = st.text_area("Комментарий к переводу")
            
            if st.form_submit_button("Выполнить перевод"):
                if source == target:
                    st.error("Компании должны быть разными!")
                else:
                    # Создаем две строки одновременно
                    row_out = [date, source, "Внутренний перевод", "Внутренний", 0, amount, f"Перевод в {target}: {comms}"]
                    row_in = [date, target, "Внутренний перевод", "Внутренний", amount, 0, f"Приход из {source}: {comms}"]
                    sheet_data.append_rows([row_out, row_in])
                    st.success(f"Перевод {amount}₽ из {source} в {target} выполнен")
                    st.cache_data.clear()

# ДАШБОРД
def load_report():
    # Читаем данные напрямую из листа report (ячейки B8 или где у вас итого)
    vals = sheet_report.get_all_values()
    # Чистая прибыль из ячейки E7 (в Python это индекс [6][4])
    profit = vals[6][4] 
    # Остаток в кассе из ячейки B8 (в Python это [7][1])
    cash = vals[7][1]
    # Выручка из ячейки E2 ([1][4])
    revenue = vals[1][4]
    return revenue, profit, cash

try:
    rev, prof, cash = load_report()
    c1, c2, c3 = st.columns(3)
    c1.metric("Выручка (Холдинг)", f"{rev} ₽")
    c2.metric("Чистая прибыль", f"{prof} ₽")
    c3.metric("Остаток в кассе (из Таблицы)", f"{cash} ₽")
except:
    st.warning("Не удалось подтянуть данные из листа report. Проверьте структуру ячеек.")

st.divider()
st.subheader("Последние операции")
all_data = pd.DataFrame(sheet_data.get_all_records())
st.dataframe(all_data.tail(10), use_container_width=True)
