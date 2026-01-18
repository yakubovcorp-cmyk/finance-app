import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Управление холдингом", layout="wide")

# --- ФУНКЦИЯ АВТОРИЗАЦИИ ---
def check_password():
    # Инициализация состояний сессии
    if "login_attempts" not in st.session_state:
        st.session_state["login_attempts"] = 0
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # Если уже авторизованы
    if st.session_state["password_correct"]:
        return True

    # Блокировка при превышении попыток
    if st.session_state["login_attempts"] >= 3:
        st.error("🔒 Доступ заблокирован: слишком много неверных попыток. Перезагрузите страницу.")
        return False

    # Форма входа
    st.write("### 🔐 Вход в систему управления")
    with st.container():
        user_input = st.text_input("Логин", key="username_input")
        pass_input = st.text_input("Пароль", type="password", key="password_input")
        
        if st.button("Войти"):
            if user_input in st.secrets["passwords"] and pass_input == st.secrets["passwords"][user_input]:
                st.session_state["password_correct"] = True
                st.session_state["username"] = user_input
                st.rerun()
            else:
                st.session_state["login_attempts"] += 1
                remaining = 3 - st.session_state["login_attempts"]
                if remaining > 0:
                    st.warning(f"❌ Неверный логин или пароль. Осталось попыток: {remaining}")
                else:
                    st.error("🔒 Попытки исчерпаны. Доступ заблокирован.")
    return False

# Проверка входа
if not check_password():
    st.stop()

# --- ПОСЛЕ УСПЕШНОГО ВХОДА ---
role = st.session_state.get("username", "Пользователь")

@st.cache_resource
def get_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # Название таблицы должно быть в точности Finance_DB
    return client.open("Finance_DB")

try:
    doc = get_connection()
    sheet_data = doc.worksheet("data")
    sheet_report = doc.worksheet("report")
except Exception as e:
    st.error(f"Ошибка подключения к Google Sheets: {e}")
    st.stop()

st.title(f"📊 Панель управления (Роль: {role})")

# --- БОКОВАЯ ПАНЕЛЬ (ВВОД ДАННЫХ) ---
with st.sidebar:
    st.header("➕ Новая запись")
    mode = st.radio("Тип операции", ["Обычная", "Внутренний перевод"])
    
    with st.form("main_form", clear_on_submit=True):
        date = str(st.date_input("Дата", datetime.now()))
        
        if mode == "Обычная":
            company = st.selectbox("Компания", ["ПП", "Ш", "Д", "Нал"])
            category = st.selectbox("Категория", ["Выручка", "Закуп товара", "Маркетинг", "ФОТ", "Аренда", "Налоги", "Комиссии", "Личное"])
            op_type = st.radio("Движение", ["Расход", "Приход"])
            amount = st.number_input("Сумма (₽)", min_value=0, step=1000)
            project = st.text_input("Проект")
            comms = st.text_area("Комментарий")
            
            if st.form_submit_button("Сохранить"):
                inc = amount if op_type == "Приход" else 0
                exp = amount if op_type == "Расход" else 0
                sheet_data.append_row([date, company, category, project, inc, exp, comms])
                st.success("Данные отправлены")
                st.cache_data.clear()

        else:  # Внутренний перевод
            source = st.selectbox("ОТКУДА (Списание)", ["ПП", "Ш", "Д", "Нал"])
            target = st.selectbox("КУДА (Пополнение)", ["Ш", "ПП", "Д", "Нал"])
            amount = st.number_input("Сумма перевода (₽)", min_value=0, step=1000)
            comms = st.text_area("Комментарий")
            
            if st.form_submit_button("Выполнить перевод"):
                if source == target:
                    st.error("Выберите разные компании")
                else:
                    rows = [
                        [date, source, "Внутренний перевод", "Перевод", 0, amount, f"В {target}: {comms}"],
                        [date, target, "Внутренний перевод", "Перевод", amount, 0, f"Из {source}: {comms}"]
                    ]
                    sheet_data.append_rows(rows)
                    st.success(f"Перевод зафиксирован")
                    st.cache_data.clear()

# --- ОСНОВНОЙ ЭКРАН (ТОЛЬКО ДЛЯ ADMIN) ---
if role == "admin":
    # 1. Загрузка данных отчета
    try:
        report_data = sheet_report.get_all_values()
        # Превращаем в таблицу, где первая строка - заголовки
        df_rep = pd.DataFrame(report_data[1:], columns=report_data[0])
        
        st.subheader("📍 Результаты за текущий месяц")
        
        # Функция для поиска значения в report по названию метрики
        def get_val(metric_name, column_name="Тек. Месяц"):
            try:
                val = df_rep.loc[df_rep['Метрика'] == metric_name, column_name].values[0]
                return val if val else "0"
            except:
                return "—"

        # Метрики сверху
        c1, c2, c3 = st.columns(3)
        c1.metric("Выручка (Месяц)", f"{get_val('Выручка')} ₽")
        c2.metric("Прибыль (Месяц)", f"{get_val('ЧИСТАЯ ПРИБЫЛЬ')} ₽")
        c3.metric("Остаток (Cash)", f"{get_val('ОСТАТОК В КАССЕ', 'Тек. Неделя')} ₽")

        st.divider()

        # 2. Полная сравнительная таблица
        st.subheader("📈 Аналитика по периодам")
        st.table(df_rep.set_index('Метрика'))
        
    except Exception as e:
        st.error(f"Ошибка чтения листа report: {e}")
        st.info("Убедитесь, что заголовки на листе report совпадают: Метрика, Тек. Неделя, Прошл. Неделя, Тек. Месяц, Квартал, ВЕСЬ ГОД")

    # 3. Последние записи
    st.subheader("📜 Журнал операций (последние 15)")
    try:
        raw_logs = sheet_data.get_all_records()
        if raw_logs:
            st.dataframe(pd.DataFrame(raw_logs).tail(15), use_container_width=True)
    except:
        st.warning("Не удалось загрузить журнал операций.")

else:
    # Интерфейс для ассистента
    st.info("👋 У вас есть доступ к добавлению данных. Статистика холдинга скрыта.")
    st.write("Используйте боковое меню слева, чтобы внести новую операцию или внутренний перевод.")
