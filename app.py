import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# --- Konfigurasi Google Sheets ---
# Sesuaikan SHEET_ID dengan ID Google Sheet Anda
SHEET_ID = "PT. BERKAT KARYA ANUGERAH"

# Otorisasi kredensial dari secrets
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
except KeyError:
    st.error("Pastikan file secrets.toml sudah terkonfigurasi dengan benar.")
    st.stop()
except Exception as e:
    st.error(f"Terjadi kesalahan saat otorisasi Google Sheets: {e}")
    st.stop()

# --- Fungsi Login ---
def authenticate(username, password):
    try:
        # Buka worksheet 'users'
        users_worksheet = sheet.worksheet("users")
        # Ambil semua data dari worksheet
        records = users_worksheet.get_all_records()
        df = pd.DataFrame(records)
        
        # Cari pengguna berdasarkan username dan password
        user = df[(df['username'] == username) & (df['password'] == password)]
        
        if not user.empty:
            return True
        else:
            return False
    except gspread.exceptions.WorksheetNotFound:
        st.error("Worksheet 'users' tidak ditemukan. Pastikan nama sheet sudah benar.")
        return False
    except Exception as e:
        st.error(f"Terjadi kesalahan saat membaca data pengguna: {e}")
        return False

# --- Tampilan Halaman ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if st.session_state['logged_in']:
    st.header("Selamat datang di Timesheet METSO!")
    st.success("Anda berhasil login.")
    st.write("Ini adalah aplikasi sederhana untuk menampilkan data dari Google Sheets.")
    st.write("---")
    
    st.subheader("Data Pengguna dari Google Sheets")
    try:
        users_worksheet = sheet.worksheet("users")
        df_users = pd.DataFrame(users_worksheet.get_all_records())
        st.dataframe(df_users)
    except Exception as e:
        st.error(f"Gagal menampilkan data: {e}")
        
    if st.button("Logout"):
        st.session_state['logged_in'] = False
        st.experimental_rerun()
else:
    st.title("Halaman Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.form_submit_button("Login")

        if login_button:
            if authenticate(username, password):
                st.session_state['logged_in'] = True
                st.success(f"Berhasil login sebagai {username}!")
                st.experimental_rerun()
            else:
                st.error("Username atau password salah.")
