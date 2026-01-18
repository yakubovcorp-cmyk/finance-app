import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import extra_streamlit_components as stx

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Финансы Холдинга", layout="wide")

# --- ИНИЦИАЛИЗАЦИЯ МЕНЕДЖЕРА КУКИ ---
def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()

# --- ФУНКЦИЯ АВТОРИЗАЦИИ ---
def check_password():
    # 1. Пытаемся достать логин из куков (автоматический вход)
    saved_user = cookie_manager.get(cookie="username")
    if saved_user in st.secrets["passwords"]:
        st.session_state["password_correct"] = True
        st.session_state["username"] = saved_user
        return True

    # 2. Проверка текущей сессии
    if st.session_state.get("password_correct", False):
        return True

    # 3. Ограничение попыток входа
    if "login_attempts" not in st.session_state:
        st.session_state["login_attempts"] = 0

    if st.session_state["login_attempts"] >= 3:
        st.error("🔒 Доступ заблокирован (3 неверные попытки). Перезагрузите страницу позже.")
        return False

    # Форма входа
    st.write("### 🔐 Вход в систему")
    u_input = st.text_input("Логин", key="u_login")
    p_input = st.text_input("Пароль", type="password", key="u_pass")
    
    if st.button("Войти"):
        if u_input in st.secrets["passwords"] and p_input == st.secrets["passwords"][u_input]:
            st.session_state["password_correct"] = True
            st.session_state["username"] = u_input
            
            # Сохраняем логин в куки браузера на 24 часа
            cookie_manager.set("username", u_input, expires_at=datetime.now() + timedelta(days=1))
            st.rerun()
        else:
            st.session_state["login_attempts"] += 1
            remaining = 3 - st.session_state["login_attempts"]
            st.error(f"❌ Неверный логин или пароль. Осталось попыток: {remaining}")
    
    return False

# Прерываем выполнение, если не авторизован
if not check_password():
    st.stop()

# --- ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS ---
role = st.session_state.get("username", "Пользователь")

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

# --- ЗАГОЛОВОК И КНОПКА ОБНОВЛЕНИЯ ---
col_t1, col_t2 = st.columns([4, 1])
with col_t1:
    st.title(f"📊 ДДС")
with col_t2:
    if st.button("🔄 Обновить данные"):
        st.cache_data.clear()
        st.rerun()

st.write(f"Вы вошли как: **{role}**")

# --- БОКОВАЯ ПАНЕЛЬ: ВВОД ДАННЫХ ---
with st.sidebar:
    st.header("➕ Новая запись")
    mode = st.radio("Тип операции", ["Обычная", "Внутренний перевод"])
    
    with st.form("main_form", clear_on_submit=True):
        date_val = st.date_input("Дата", datetime.now())
        date_str = date_val.strftime("%Y-%m-%d")
        
        if mode == "Обычная":
            comp = st.selectbox("Компания", ["ПП", "Ш", "Д", "Нал"])
            cat = st.selectbox("Категория", ["Выручка", "Закуп товара", "Маркетинг", "ФОТ", "Аренда", "Налоги", "Комиссии", "Личное"])
            op_type = st.radio("Движение", ["Расход", "Приход"])
            amt = st.number_input("Сумма (₽)", min_value=0, step=1000)
            proj = st.text_input("Проект")
            comm = st.text_area("Комментарий")
            
            if st.form_submit_button("Сохранить"):
                inc = amt if op_type == "Приход" else 0
                exp = amt if op_type == "Расход" else 0
                sheet_data.append_row([date_str, comp, cat, proj, inc, exp, comm], value_input_option='USER_ENTERED')
                st.success("✅ Записано")
                st.cache_data.clear()

        else: # Перевод
            src = st.selectbox("ОТКУДА (Списание)", ["ПП", "Ш", "Д", "Нал"])
            trg = st.selectbox("КУДА (Пополнение)", ["Ш", "ПП", "Д", "Нал"])
            amt = st.number_input("Сумма (₽)", min_value=0)
            comm = st.text_area("Комментарий к переводу")
            
            if st.form_submit_button("Выполнить перевод"):
                if src == trg:
                    st.error("Компании должны отличаться!")
                else:
                    rows = [
                        [date_str, src, "Внутренний перевод", "Перевод", 0, amt, f"В {trg}: {comm}"],
                        [date_str, trg, "Внутренний перевод", "Перевод", amt, 0, f"Из {src}: {comm}"]
                    ]
                    sheet_data.append_rows(rows, value_input_option='USER_ENTERED')
                    st.success("✅ Перевод выполнен")
                    st.cache_data.clear()
    
    st.divider()
    if st.button("Выйти из аккаунта"):
        cookie_manager.delete("username")
        st.session_state["password_correct"] = False
        st.rerun()

# --- АНАЛИТИКА (ТОЛЬКО ДЛЯ ADMIN) ---
if role == "admin":
    try:
        rep_vals = sheet_report.get_all_values()
        df_rep = pd.DataFrame(rep_vals[1:], columns=rep_vals[0])
        
        def find_metric(m_name, col="Тек. Месяц"):
            try:
                val = df_rep.loc[df_rep['Метрика'] == m_name, col].values[0]
                return val if val else "0"
            except:
                return "0"

        st.subheader("📍 Текущие показатели")
        m1, m2, m3 = st.columns(3)
        m1.metric("Выручка (Месяц)", f"{find_metric('Выручка')} ₽")
        m2.metric("Прибыль (Месяц)", f"{find_metric('ЧИСТАЯ ПРИБЫЛЬ')} ₽")
        m3.metric("Касса (Всего)", f"{find_metric('ОСТАТОК В КАССЕ', 'Тек. Неделя')} ₽")

        st.divider()
        st.subheader("📈 Аналитика по периодам")
        st.table(df_rep.set_index('Метрика'))

    except Exception as e:
        st.error(f"Не удалось загрузить отчет: {e}")

    st.subheader("📜 Журнал операций")
    try:
        logs_raw = sheet_data.get_all_records()
        if logs_raw:
            logs_df = pd.DataFrame(logs_raw)
            st.dataframe(logs_df.tail(15), use_container_width=True)
    except:
        st.warning("Журнал пуст.")
else:
    st.info("Вы в режиме ассистента. Статистика холдинга скрыта.")
