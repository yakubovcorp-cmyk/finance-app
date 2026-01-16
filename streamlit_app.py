import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- АВТОРИЗАЦИЯ ---
def check_password():
    def password_entered():
        if st.session_state["username"] in st.secrets["passwords"] and \
           st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # удаляем пароль из памяти
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Логин", on_change=password_entered, key="username")
        st.text_input("Пароль", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Логин", on_change=password_entered, key="username")
        st.text_input("Пароль", type="password", on_change=password_entered, key="password")
        st.error("😕 Неверный логин или пароль")
        return False
    else:
        return True

if not check_password():
    st.stop()

# --- ОСНОВНОЙ КОД ПРИЛОЖЕНИЯ (выполняется только после входа) ---
role = st.session_state["username"]

@st.cache_resource
def get_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Finance_DB")

doc = get_connection()
sheet_data = doc.worksheet("data")
sheet_report = doc.worksheet("report")

st.title(f"💰 Управление холдингом (Роль: {role})")

# ЛОГИКА ВВОДА (Доступна и Админу, и Ассистенту)
with st.sidebar:
    st.write(f"Вы вошли как: **{role}**")
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

        else: # ВНУТРЕННИЙ ПЕРЕВОД
            source = st.selectbox("ОТКУДА (Списание)", ["ООО ПП", "ИП Ш", "ИП Д", "Наличные"])
            target = st.selectbox("КУДА (Пополнение)", ["ИП Ш", "ООО ПП", "ИП Д", "Наличные"])
            amount = st.number_input("Сумма перевода (₽)", min_value=0, step=1000)
            comms = st.text_area("Комментарий к переводу")
            
            if st.form_submit_button("Выполнить перевод"):
                if source == target: st.error("Компании должны быть разными!")
                else:
                    row_out = [date, source, "Внутренний перевод", "Внутренний", 0, amount, f"Перевод в {target}: {comms}"]
                    row_in = [date, target, "Внутренний перевод", "Внутренний", amount, 0, f"Приход из {source}: {comms}"]
                    sheet_data.append_rows([row_out, row_in])
                    st.success(f"Перевод выполнен")
                    st.cache_data.clear()

# ДАШБОРД (ТОЛЬКО ДЛЯ АДМИНА)
if role == "admin":
    def load_report():
        vals = sheet_report.get_all_values()
        revenue = vals[1][4]
        profit = vals[6][4] 
        cash = vals[7][1]
        return revenue, profit, cash

    try:
        rev, prof, cash = load_report()
        c1, c2, c3 = st.columns(3)
        c1.metric("Выручка (Холдинг)", f"{rev} ₽")
        c2.metric("Чистая прибыль", f"{prof} ₽")
        c3.metric("Остаток в кассе", f"{cash} ₽")
    except:
        st.warning("Проверьте структуру листа report!")

    st.divider()
    st.subheader("Последние операции")
    all_data = pd.DataFrame(sheet_data.get_all_records())
    st.dataframe(all_data.tail(15), use_container_width=True)
else:
    st.info("👋 Привет! У тебя доступ на добавление операций. Статистика доступна только руководителю.")
