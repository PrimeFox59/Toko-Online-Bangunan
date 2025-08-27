import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import bcrypt
import streamlit.components.v1 as components

# --- Page Configuration ---
st.set_page_config(
    page_title="Timesheet METSO",
    page_icon="📝",
    layout="wide"
)

# --- Google Sheet Configuration ---
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    key_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(key_dict, scopes=scope)
    gc = gspread.authorize(creds)
    SHEET_ID = "1BwwoNx3t3MBrsOB3H9BSxnWbYCwChwgl4t1HrpFYWpA"
except KeyError as e:
    st.error(f"Kredensial Google Cloud tidak ditemukan. Pastikan file .streamlit/secrets.toml sudah benar. Error: {e}")
    st.stop()
except Exception as e:
    st.error(f"Gagal menginisiasi koneksi Google Sheets. Error: {e}")
    st.stop()


# --- Fungsi Login dan Data ---
@st.cache_data(ttl=3600)  # Cache data selama 1 jam
def load_users_data():
    try:
        users_sheet = gc.open_by_key(SHEET_ID).worksheet("users")
        users_data = users_sheet.get_all_records()
        return pd.DataFrame(users_data)
    except gspread.exceptions.WorksheetNotFound:
        st.error("Worksheet 'users' tidak ditemukan. Pastikan nama sheet sudah benar.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Gagal memuat data pengguna: {e}")
        return pd.DataFrame()

def check_login(username, password, users_df):
    if users_df.empty:
        return False
    
    user_row = users_df[users_df['username'] == username]
    
    if not user_row.empty:
        # Mengambil hashed password dari DataFrame
        stored_hashed_password = user_row['password'].iloc[0].encode('utf-8')
        input_password_bytes = password.encode('utf-8')
        
        # Membandingkan password
        try:
            return bcrypt.checkpw(input_password_bytes, stored_hashed_password)
        except Exception:
            # Jika ada masalah saat membandingkan hash (mis. format tidak valid)
            return False
    
    return False

# --- Halaman Utama Aplikasi ---
def main_app():
    st.header("Timesheet METSO")
    st.write(f"Selamat datang, **{st.session_state['username']}**!")
    st.write("Ini adalah halaman utama timesheet. Anda dapat menambahkan fungsionalitas di sini.")

    # Contoh: Tampilkan data timesheet dari sheet lain
    try:
        # Ganti dengan nama sheet timesheet Anda
        timesheet_sheet = gc.open_by_key(SHEET_ID).worksheet("timesheet_data")
        timesheet_df = pd.DataFrame(timesheet_sheet.get_all_records())
        st.subheader("Data Timesheet")
        st.dataframe(timesheet_df)
    except gspread.exceptions.WorksheetNotFound:
        st.warning("Worksheet 'timesheet_data' tidak ditemukan. Tambahkan sheet ini di Google Sheets Anda.")
    
    # Tombol Logout
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.session_state['username'] = ""
        st.rerun()

# --- Halaman Login ---
def login_page():
    st.title("Login Timesheet")
    
    users_df = load_users_data()

    if users_df.empty:
        st.warning("Tidak dapat memuat data pengguna. Cek koneksi atau konfigurasi Google Sheets.")
        st.stop()
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
    
    if submitted:
        if check_login(username, password, users_df):
            st.session_state['logged_in'] = True
            st.session_state['username'] = username
            st.success("Login berhasil!")
            st.balloons()
            st.rerun()
        else:
            st.error("Username atau password salah.")

# --- Kontrol Alur Aplikasi ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['username'] = ""

if st.session_state['logged_in']:
    main_app()
else:
    login_page()
