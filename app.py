import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import io
import bcrypt
import plotly.express as px
import gspread
from gspread.exceptions import WorksheetNotFound

# --- CUSTOM CSS FOR UI/UX IMPROVEMENTS ---
st.markdown("""
<style>
    .reportview-container {
        background: #F0F2F6;
    }
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    .st-emotion-cache-1r6509j {
        background-color: #2F3E50;
    }
    .st-emotion-cache-1r6509j .stButton>button {
        color: white;
    }
    .st-emotion-cache-1r6509j .stButton>button:hover {
        background-color: #455A64;
    }
    .st-emotion-cache-1r6509j .st-bv {
        color: white;
    }
    .st-emotion-cache-16k1w7m {
        background-color: #2F3E50;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #2F3E50;
    }
    .st-emotion-cache-1av5400 {
        background-color: #FFFFFF;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .st-emotion-cache-1av5400 h3 {
        color: #172B4D;
    }
    .st-emotion-cache-1av5400 .st-cc {
        color: #172B4D;
    }
</style>
""", unsafe_allow_html=True)

# --- GOOGLE SHEETS CONNECTION & SETUP ---
try:
    creds = st.secrets["connections"]["gsheets"]
    gc = gspread.service_account_from_dict(creds)
    sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"].split('/')[-2])
except Exception as e:
    st.error(f"Gagal terhubung ke Google Sheets. Pastikan file secrets.toml sudah benar dan API Google Sheets/Drive telah diaktifkan: {e}")
    st.stop()

# --- UTILITY FUNCTIONS ---
def get_worksheet(sheet_name):
    try:
        return sh.worksheet(sheet_name)
    except WorksheetNotFound:
        return None

def check_and_create_worksheets():
    """Checks for required worksheets and creates them with headers if they don't exist."""
    required_worksheets = {
        "master_barang": ['kode_bahan', 'nama_supplier', 'nama_bahan', 'warna', 'rak', 'harga'],
        "barang_masuk": ['tanggal_masuk', 'kode_bahan', 'jumlah_masuk', 'invoice_supplier'],
        "barang_keluar": ['tanggal_keluar', 'kode_bahan', 'jumlah_keluar', 'invoice_konsumen'],
        "invoices": ['invoice_number', 'customer_name', 'invoice_date', 'total_amount'],
        "invoice_items": ['invoice_number', 'kode_bahan', 'quantity', 'price_per_item', 'total_price'],
        "employees": ['username', 'password', 'role'],
        "payroll": ['employee_id', 'pay_date', 'amount']
    }

    existing_worksheets = [ws.title for ws in sh.worksheets()]
    
    for ws_name, headers in required_worksheets.items():
        if ws_name not in existing_worksheets:
            st.warning(f"Worksheet '{ws_name}' tidak ditemukan. Membuat sekarang...")
            new_ws = sh.add_worksheet(title=ws_name, rows="1000", cols="20")
            new_ws.append_row(headers)
            st.success(f"Worksheet '{ws_name}' berhasil dibuat dengan header.")

def get_data_from_gsheets(sheet_name):
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        df = df.replace('', pd.NA).dropna(how='all')
        return df
    return pd.DataFrame()

def append_row_to_gsheet(sheet_name, data_list):
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        worksheet.append_row(data_list)
        return True
    return False

def update_row_in_gsheet(sheet_name, row_index, data_list):
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        worksheet.update(f"A{row_index+2}", [data_list])
        return True
    return False

def delete_row_from_gsheet(sheet_name, row_index):
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        worksheet.delete_rows(row_index+2)
        return True
    return False

# --- AUTHENTICATION FUNCTIONS ---
def get_user_data():
    return get_data_from_gsheets('employees')

def authenticate(username, password):
    users_df = get_user_data()
    user = users_df[users_df['username'] == username]
    if not user.empty:
        stored_password_hash = user.iloc[0]['password']
        return password == stored_password_hash
    return False

# --- PAGES ---
def show_login_page():
    st.title("Login Sistem Kontrol Stok")
    with st.form("Login Form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if authenticate(username, password):
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.session_state['page'] = 'Dashboard'
                st.success("Login berhasil!")
                st.rerun()
            else:
                st.error("Username atau password salah.")

def show_dashboard():
    st.title(f"Selamat Datang, {st.session_state['username']}! 👋")
    st.markdown("### Dashboard Ringkasan Stok")
    
    df_master = get_data_from_gsheets('master_barang')
    df_masuk = get_data_from_gsheets('barang_masuk')
    df_keluar = get_data_from_gsheets('barang_keluar')

    st.subheader("Ringkasan Stok")
    if not df_master.empty:
        stok_masuk = df_masuk.groupby('kode_bahan')['jumlah_masuk'].sum().reset_index()
        stok_keluar = df_keluar.groupby('kode_bahan')['jumlah_keluar'].sum().reset_index()
        
        stok_df = df_master[['kode_bahan', 'nama_bahan']].copy()
        stok_df['stok_saat_ini'] = 0

        for index, row in stok_df.iterrows():
            kode = row['kode_bahan']
            masuk = stok_masuk[stok_masuk['kode_bahan'] == kode]['jumlah_masuk'].sum()
            keluar = stok_keluar[stok_keluar['kode_bahan'] == kode]['jumlah_keluar'].sum()
            stok_df.loc[index, 'stok_saat_ini'] = masuk - keluar

        st.dataframe(stok_df, use_container_width=True)
    else:
        st.info("Tidak ada data master barang.")

    st.subheader("Tren Barang Masuk & Keluar (Bulan)")
    if not df_masuk.empty and not df_keluar.empty:
        df_masuk['tanggal_masuk'] = pd.to_datetime(df_masuk['tanggal_masuk'])
        df_keluar['tanggal_keluar'] = pd.to_datetime(df_keluar['tanggal_keluar'])

        df_masuk['bulan'] = df_masuk['tanggal_masuk'].dt.to_period('M')
        df_keluar['bulan'] = df_keluar['tanggal_keluar'].dt.to_period('M')
        
        trend_masuk = df_masuk.groupby('bulan')['jumlah_masuk'].sum().reset_index()
        trend_keluar = df_keluar.groupby('bulan')['jumlah_keluar'].sum().reset_index()
        
        trend_df = pd.merge(trend_masuk, trend_keluar, on='bulan', how='outer').fillna(0)
        trend_df['bulan'] = trend_df['bulan'].astype(str)
        
        fig = px.bar(trend_df, x='bulan', y=['jumlah_masuk', 'jumlah_keluar'],
                     barmode='group', title="Tren Barang Masuk & Keluar")
        st.plotly_chart(fig, use_container_width=True)

def show_master_barang():
    st.title("Manajemen Master Barang")
    st.subheader("Tambah Barang Baru")
    with st.expander("Form Tambah Barang", expanded=False):
        with st.form("add_item_form", clear_on_submit=True):
            kode = st.text_input("Kode Bahan").upper()
            supplier = st.text_input("Nama Supplier")
            nama = st.text_input("Nama Bahan")
            warna = st.text_input("Warna")
            rak = st.text_input("Lokasi Rak")
            harga = st.number_input("Harga", min_value=0, format="%d")
            submit_button = st.form_submit_button("Tambah Barang")

            if submit_button:
                if kode and nama:
                    if append_row_to_gsheet('master_barang', [kode, supplier, nama, warna, rak, harga]):
                        st.success("Barang berhasil ditambahkan!")
                    else:
                        st.error("Gagal menambahkan barang. Silakan coba lagi.")
                else:
                    st.error("Kode Bahan dan Nama Bahan tidak boleh kosong.")
    
    st.subheader("Daftar Barang")
    df = get_data_from_gsheets('master_barang')
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        
        # Edit and Delete functionality
        st.subheader("Edit/Hapus Barang")
        with st.expander("Form Edit/Hapus", expanded=False):
            kode_list = df['kode_bahan'].tolist()
            selected_kode = st.selectbox("Pilih Kode Bahan untuk Edit/Hapus", kode_list)
            selected_row = df[df['kode_bahan'] == selected_kode].iloc[0]
            row_index = df.index[df['kode_bahan'] == selected_kode].tolist()[0]
            
            with st.form("edit_item_form"):
                new_supplier = st.text_input("Nama Supplier", value=selected_row['nama_supplier'])
                new_nama = st.text_input("Nama Bahan", value=selected_row['nama_bahan'])
                new_warna = st.text_input("Warna", value=selected_row['warna'])
                new_rak = st.text_input("Lokasi Rak", value=selected_row['rak'])
                new_harga = st.number_input("Harga", min_value=0, format="%d", value=int(selected_row['harga']))

                col1, col2 = st.columns(2)
                with col1:
                    update_button = st.form_submit_button("Update Barang")
                with col2:
                    delete_button = st.form_submit_button("Hapus Barang")
            
            if update_button:
                if update_row_in_gsheet('master_barang', row_index, [selected_kode, new_supplier, new_nama, new_warna, new_rak, new_harga]):
                    st.success("Barang berhasil diupdate!")
                else:
                    st.error("Gagal mengupdate barang. Silakan coba lagi.")
                st.rerun()

            if delete_button:
                if delete_row_from_gsheet('master_barang', row_index):
                    st.success("Barang berhasil dihapus!")
                else:
                    st.error("Gagal menghapus barang. Silakan coba lagi.")
                st.rerun()
    else:
        st.info("Belum ada data di Master Barang. Silakan tambahkan barang terlebih dahulu.")

def show_input_masuk():
    st.title("Input Barang Masuk")
    st.subheader("Form Input Barang Masuk")
    df_master = get_data_from_gsheets('master_barang')
    if df_master.empty:
        st.warning("Data master barang kosong. Tambahkan barang terlebih dahulu di halaman 'Master Barang'.")
        return

    item_options = df_master['kode_bahan'].tolist()
    
    with st.form("form_barang_masuk", clear_on_submit=True):
        tanggal = st.date_input("Tanggal Masuk", datetime.now())
        kode = st.selectbox("Pilih Kode Bahan", item_options)
        jumlah = st.number_input("Jumlah Masuk", min_value=1, format="%d")
        invoice_supplier = st.text_input("Nomor Invoice Supplier")
        
        submit_button = st.form_submit_button("Simpan Barang Masuk")
        
        if submit_button:
            if append_row_to_gsheet('barang_masuk', [tanggal.strftime("%Y-%m-%d"), kode, jumlah, invoice_supplier]):
                st.success(f"Barang Masuk untuk {kode} sebanyak {jumlah} berhasil disimpan.")
            else:
                st.error("Gagal menyimpan data. Silakan coba lagi.")

    st.subheader("Riwayat Barang Masuk")
    df = get_data_from_gsheets('barang_masuk')
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Tidak ada riwayat barang masuk.")

def show_transaksi_keluar_invoice_page():
    st.title("Manajemen Transaksi Keluar (Invoice)")
    
    st.subheader("Daftar Invoice")
    df_invoices = get_data_from_gsheets('invoices')
    if not df_invoices.empty:
        st.dataframe(df_invoices, use_container_width=True)
    else:
        st.info("Tidak ada data invoice.")
    
    st.subheader("Buat Invoice Baru")
    with st.expander("Form Buat Invoice", expanded=False):
        with st.form("form_invoice_baru", clear_on_submit=True):
            invoice_number = st.text_input("Nomor Invoice").upper()
            customer_name = st.text_input("Nama Konsumen")
            invoice_date = st.date_input("Tanggal Invoice", datetime.now())
            
            submit_button = st.form_submit_button("Buat Invoice")
            
            if submit_button:
                if invoice_number and customer_name:
                    if append_row_to_gsheet('invoices', [invoice_number, customer_name, invoice_date.strftime("%Y-%m-%d"), 0]):
                        st.success(f"Invoice {invoice_number} untuk {customer_name} berhasil dibuat.")
                    else:
                        st.error("Gagal membuat invoice.")
                else:
                    st.error("Nomor Invoice dan Nama Konsumen tidak boleh kosong.")
    
    st.subheader("Tambah Item ke Invoice")
    df_invoices = get_data_from_gsheets('invoices')
    df_master = get_data_from_gsheets('master_barang')
    
    if not df_invoices.empty and not df_master.empty:
        invoice_options = df_invoices['invoice_number'].tolist()
        item_options = df_master['kode_bahan'].tolist()
        
        with st.form("form_tambah_item_invoice", clear_on_submit=True):
            selected_invoice = st.selectbox("Pilih Invoice", invoice_options)
            selected_item = st.selectbox("Pilih Kode Bahan", item_options)
            quantity = st.number_input("Jumlah", min_value=1, format="%d")
            
            add_item_button = st.form_submit_button("Tambah Item")
            
            if add_item_button:
                item_details = df_master[df_master['kode_bahan'] == selected_item].iloc[0]
                price_per_item = int(item_details['harga'])
                total_price = quantity * price_per_item
                
                if append_row_to_gsheet('barang_keluar', [datetime.now().strftime("%Y-%m-%d"), selected_item, quantity, selected_invoice]):
                    if append_row_to_gsheet('invoice_items', [selected_invoice, selected_item, quantity, price_per_item, total_price]):
                        st.success(f"Item {selected_item} berhasil ditambahkan ke Invoice {selected_invoice}.")
                        
                        df_invoice_items = get_data_from_gsheets('invoice_items')
                        invoice_total = df_invoice_items[df_invoice_items['invoice_number'] == selected_invoice]['total_price'].sum()
                        
                        invoice_row_index = df_invoices[df_invoices['invoice_number'] == selected_invoice].index.tolist()[0]
                        df_invoices.loc[invoice_row_index, 'total_amount'] = invoice_total
                        update_row_in_gsheet('invoices', invoice_row_index, df_invoices.loc[invoice_row_index].tolist())
                        
                    else:
                        st.error("Gagal menambahkan item ke invoice.")
                else:
                    st.error("Gagal menyimpan data barang keluar.")
    
    st.subheader("Cetak Invoice")
    if not df_invoices.empty:
        invoice_to_print = st.selectbox("Pilih Invoice untuk Dicetak", df_invoices['invoice_number'].tolist())
        if st.button("Cetak PDF"):
            generate_pdf(invoice_to_print)

def generate_pdf(invoice_number):
    df_invoices = get_data_from_gsheets('invoices')
    df_invoice_items = get_data_from_gsheets('invoice_items')
    df_master = get_data_from_gsheets('master_barang')

    invoice_details = df_invoices[df_invoices['invoice_number'] == invoice_number].iloc[0]
    invoice_items = df_invoice_items[df_invoice_items['invoice_number'] == invoice_number]
    
    if invoice_items.empty:
        st.warning("Invoice ini tidak memiliki item.")
        return

    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, 'INVOICE', 0, 1, 'C')
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

        def chapter_title(self, title):
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, title, 0, 1, 'L')
            self.ln(5)

        def chapter_body(self, data, is_table=False):
            self.set_font('Arial', '', 10)
            if is_table:
                self.set_fill_color(200, 220, 255)
                self.cell(30, 7, 'Kode Bahan', 1, 0, 'C', 1)
                self.cell(60, 7, 'Nama Bahan', 1, 0, 'C', 1)
                self.cell(20, 7, 'Qty', 1, 0, 'C', 1)
                self.cell(40, 7, 'Harga Satuan', 1, 0, 'C', 1)
                self.cell(40, 7, 'Total', 1, 1, 'C', 1)

                for index, row in data.iterrows():
                    nama_bahan = df_master[df_master['kode_bahan'] == row['kode_bahan']]['nama_bahan'].iloc[0]
                    self.cell(30, 7, str(row['kode_bahan']), 1, 0)
                    self.cell(60, 7, str(nama_bahan), 1, 0)
                    self.cell(20, 7, str(row['quantity']), 1, 0)
                    self.cell(40, 7, f"Rp{row['price_per_item']:,}", 1, 0, 'R')
                    self.cell(40, 7, f"Rp{row['total_price']:,}", 1, 1, 'R')
            else:
                self.multi_cell(0, 5, data)
                self.ln()

    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)

    pdf.chapter_title(f"Invoice # {invoice_details['invoice_number']}")
    pdf.chapter_body(f"Customer: {invoice_details['customer_name']}\nDate: {invoice_details['invoice_date']}\n")

    pdf.chapter_title("Items")
    pdf.chapter_body(invoice_items, is_table=True)

    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"Total Amount: Rp{invoice_details['total_amount']:,}", 0, 1, 'R')

    pdf_output = pdf.output(dest='S').encode('latin1')
    st.download_button(
        label="Download Invoice PDF",
        data=pdf_output,
        file_name=f"invoice_{invoice_number}.pdf",
        mime="application/pdf"
    )

def show_monitoring_stok():
    st.title("Monitoring Stok")
    st.markdown("### Ringkasan Stok Saat Ini")

    df_master = get_data_from_gsheets('master_barang')
    df_masuk = get_data_from_gsheets('barang_masuk')
    df_keluar = get_data_from_gsheets('barang_keluar')
    
    if not df_master.empty:
        stok_masuk = df_masuk.groupby('kode_bahan')['jumlah_masuk'].sum().reset_index()
        stok_keluar = df_keluar.groupby('kode_bahan')['jumlah_keluar'].sum().reset_index()

        stok_df = df_master[['kode_bahan', 'nama_bahan', 'rak']].copy()
        stok_df['stok_saat_ini'] = 0

        for index, row in stok_df.iterrows():
            kode = row['kode_bahan']
            masuk = stok_masuk[stok_masuk['kode_bahan'] == kode]['jumlah_masuk'].sum()
            keluar = stok_keluar[stok_keluar['kode_bahan'] == kode]['jumlah_keluar'].sum()
            stok_df.loc[index, 'stok_saat_ini'] = masuk - keluar
        
        st.dataframe(stok_df, use_container_width=True)
    else:
        st.info("Tidak ada data untuk ditampilkan.")

def show_penggajian():
    st.title("Sistem Penggajian Sederhana")
    st.subheader("Data Gaji Karyawan")
    st.info("Sistem ini belum terintegrasi sepenuhnya. Data diinput secara manual.")
    
    df_payroll = get_data_from_gsheets('payroll')
    df_employees = get_data_from_gsheets('employees')

    if not df_payroll.empty:
        st.dataframe(df_payroll, use_container_width=True)
    else:
        st.info("Tidak ada data penggajian.")
    
    st.subheader("Input Data Gaji")
    if not df_employees.empty:
        employee_options = df_employees['username'].tolist()
        
        with st.form("form_penggajian", clear_on_submit=True):
            employee_id = st.selectbox("Pilih Karyawan", employee_options)
            pay_date = st.date_input("Tanggal Pembayaran", datetime.now())
            amount = st.number_input("Jumlah Gaji", min_value=0, format="%d")
            
            if st.form_submit_button("Simpan Gaji"):
                if append_row_to_gsheet('payroll', [employee_id, pay_date.strftime("%Y-%m-%d"), amount]):
                    st.success("Data gaji berhasil disimpan!")
                else:
                    st.error("Gagal menyimpan data gaji.")
    else:
        st.warning("Tidak ada data karyawan. Tambahkan karyawan di Google Sheet 'employees' secara manual.")

# --- MAIN APP LOGIC ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'page' not in st.session_state:
    st.session_state['page'] = 'Login'

if st.session_state['logged_in']:
    st.sidebar.title("Aplikasi Stok")
    if st.sidebar.button("Dashboard 🏠", use_container_width=True):
        st.session_state['page'] = "Dashboard"
        st.rerun()
    if st.sidebar.button("Master Barang 📦", use_container_width=True):
        st.session_state['page'] = "Master Barang"
        st.rerun()
    if st.sidebar.button("Barang Masuk 📥", use_container_width=True):
        st.session_state['page'] = "Barang Masuk"
        st.rerun()
    if st.sidebar.button("Transaksi Keluar 🧾", use_container_width=True):
        st.session_state['page'] = "Transaksi Keluar"
        st.rerun()
    if st.sidebar.button("Monitoring Stok 📊", use_container_width=True):
        st.session_state['page'] = "Monitoring Stok"
        st.rerun()
    if st.sidebar.button("Penggajian 💰", use_container_width=True):
        st.session_state['page'] = "Penggajian"
        st.rerun()
    
    st.sidebar.markdown("---")
    if st.sidebar.button("Logout 🚪", use_container_width=True):
        st.session_state['logged_in'] = False
        st.session_state['page'] = 'Login'
        st.rerun()
    
    if 'sheets_checked' not in st.session_state:
        check_and_create_worksheets()
        st.session_state['sheets_checked'] = True

    if st.session_state['page'] == "Dashboard":
        show_dashboard()
    elif st.session_state['page'] == "Master Barang":
        show_master_barang()
    elif st.session_state['page'] == "Barang Masuk":
        show_input_masuk()
    elif st.session_state['page'] == "Transaksi Keluar":
        show_transaksi_keluar_invoice_page()
    elif st.session_state['page'] == "Monitoring Stok":
        show_monitoring_stok()
    elif st.session_state['page'] == "Penggajian":
        show_penggajian()
else:
    show_login_page()
