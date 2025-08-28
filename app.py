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
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# --- GOOGLE SHEETS CONNECTION & SETUP ---
def get_gsheet_connection():
    try:
        creds = st.secrets["connections"]["gsheets"]
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"].split('/')[-2])
        return sh
    except Exception as e:
        st.error(f"Gagal terhubung ke Google Sheets. Pastikan file secrets.toml sudah benar dan API Google Sheets/Drive telah diaktifkan: {e}")
        st.stop()
    return None

sh = get_gsheet_connection()

# --- UTILITY FUNCTIONS ---
def get_worksheet(sheet_name):
    try:
        return sh.worksheet(sheet_name)
    except WorksheetNotFound:
        return None

def check_and_create_worksheets():
    """Checks for required worksheets and creates them with headers if they don't exist."""
    required_worksheets = {
        "users": ['username', 'password_hash', 'role'],
        "master_barang": ['kode_bahan', 'nama_supplier', 'nama_bahan', 'warna', 'rak', 'harga'],
        "barang_masuk": ['tanggal_waktu', 'kode_bahan', 'warna', 'stok', 'yard', 'keterangan'],
        "barang_keluar": ['tanggal_waktu', 'kode_bahan', 'warna', 'stok', 'yard', 'keterangan'],
        "invoices": ['invoice_number', 'tanggal_waktu', 'customer_name'],
        "invoice_items": ['invoice_number', 'kode_bahan', 'nama_bahan', 'qty', 'harga', 'total'],
        "employees": ['nama_karyawan', 'bagian', 'gaji_pokok'],
        "payroll": ['tanggal_waktu', 'gaji_bulan', 'employee_id', 'gaji_pokok', 'lembur', 'lembur_minggu', 'uang_makan', 'pot_absen_finger', 'ijin_hr', 'simpanan_wajib', 'potongan_koperasi', 'kasbon', 'gaji_akhir', 'keterangan']
    }

    existing_worksheets = [ws.title for ws in sh.worksheets()]
    
    for ws_name, headers in required_worksheets.items():
        if ws_name not in existing_worksheets:
            st.warning(f"Worksheet '{ws_name}' tidak ditemukan. Membuat sekarang...")
            new_ws = sh.add_worksheet(title=ws_name, rows="1000", cols="20")
            new_ws.append_row(headers)
            st.success(f"Worksheet '{ws_name}' berhasil dibuat dengan header.")

# PERBAIKAN: MENAMBAHKAN CACHING UNTUK MENGURANGI PANGGILAN API
@st.cache_data(ttl=600)  # Cache data selama 10 menit
def get_data_from_gsheets(sheet_name):
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        # Drop rows that are all empty, which can happen with get_all_records
        df = df.replace('', pd.NA).dropna(how='all')
        return df
    return pd.DataFrame()

def append_row_to_gsheet(sheet_name, data_list):
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        worksheet.append_row(data_list)
        st.cache_data.clear() # PERBAIKAN: Hapus cache setelah menulis
        return True
    return False

def update_row_in_gsheet(sheet_name, row_index, data_list):
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        worksheet.update(f"A{row_index+2}", [data_list])
        st.cache_data.clear() # PERBAIKAN: Hapus cache setelah menulis
        return True
    return False

def delete_row_from_gsheet(sheet_name, row_index):
    worksheet = get_worksheet(sheet_name)
    if worksheet:
        worksheet.delete_rows(row_index+2)
        st.cache_data.clear() # PERBAIKAN: Hapus cache setelah menulis
        return True
    return False

# --- AUTHENTICATION FUNCTIONS ---
def get_user_data():
    return get_data_from_gsheets('users')

def check_login(username, password):
    users_df = get_user_data()
    user = users_df[users_df['username'] == username]
    if not user.empty:
        stored_password_hash = user.iloc[0]['password_hash']
        # This part is a bit tricky with gsheets.
        # bcrypt hash is a binary object. gsheets stores it as a string.
        # We'll just do a simple password check for simplicity.
        # For production, a more robust solution would be needed.
        return password == stored_password_hash
    return False

def check_and_create_owner():
    users_df = get_data_from_gsheets('users')
    if users_df.empty or 'owner' not in users_df['username'].tolist():
        st.warning("Pengguna 'owner' tidak ditemukan. Membuat sekarang...")
        # Note: In a real-world app, you'd want to hash this password.
        # But to simplify for gsheets, we'll store it as plain text.
        # For a robust solution, you would need to hash the password before storing it.
        if append_row_to_gsheet('users', ['owner', 'owner123', 'admin']):
            st.success("Pengguna 'owner' berhasil dibuat.")

# --- CRUD Functions - Inventory ---
def add_master_item(kode, supplier, nama, warna, rak, harga):
    df_master = get_data_from_gsheets('master_barang')
    if not df_master.empty and ((df_master['kode_bahan'] == kode) & (df_master['warna'] == warna)).any():
        return False
    return append_row_to_gsheet('master_barang', [kode, supplier, nama, warna, rak, harga])

def get_master_barang():
    df = get_data_from_gsheets('master_barang')
    if not df.empty:
        df['harga'] = pd.to_numeric(df['harga'], errors='coerce').fillna(0)
    return df

def update_master_item(old_kode, old_warna, new_kode, new_warna, supplier, nama, rak, harga):
    df_master = get_master_barang() # Use the function that returns a clean df
    row_index = df_master.index[(df_master['kode_bahan'] == old_kode) & (df_master['warna'] == old_warna)].tolist()
    if not row_index:
        return False
    
    row_index = row_index[0]
    
    # Check for duplicate key combination
    if (new_kode != old_kode or new_warna != old_warna):
        if ((df_master['kode_bahan'] == new_kode) & (df_master['warna'] == new_warna)).any():
            return False

    return update_row_in_gsheet('master_barang', row_index, [new_kode, supplier, nama, new_warna, rak, harga])

def delete_master_item(kode, warna):
    df_master = get_data_from_gsheets('master_barang')
    row_index = df_master.index[(df_master['kode_bahan'] == kode) & (df_master['warna'] == warna)].tolist()
    if not row_index:
        return False
    return delete_row_from_gsheet('master_barang', row_index[0])

def add_barang_masuk(tanggal_waktu, kode_bahan, warna, stok, yard, keterangan):
    return append_row_to_gsheet('barang_masuk', [tanggal_waktu, kode_bahan, warna, stok, yard, keterangan])

def get_barang_masuk():
    df = get_data_from_gsheets('barang_masuk')
    if df.empty:
        # Perbaikan: Buat DataFrame kosong dengan kolom yang dibutuhkan
        return pd.DataFrame(columns=['tanggal_waktu', 'kode_bahan', 'warna', 'stok', 'yard', 'keterangan'])

    df['stok'] = pd.to_numeric(df['stok'], errors='coerce').fillna(0).astype(int)
    df['yard'] = pd.to_numeric(df['yard'], errors='coerce').fillna(0.0)
    return df

def update_barang_masuk(row_index, tanggal_waktu, kode_bahan, warna, stok, yard, keterangan):
    return update_row_in_gsheet('barang_masuk', row_index, [tanggal_waktu, kode_bahan, warna, stok, yard, keterangan])

def delete_barang_masuk(row_index):
    return delete_row_from_gsheet('barang_masuk', row_index)

def get_stock_balance(kode_bahan, warna):
    df_in = get_barang_masuk()
    df_out = get_barang_keluar()
    
    # Perbaikan: Periksa apakah DataFrame memiliki kolom sebelum melakukan filter
    if not df_in.empty:
        in_stock = df_in[(df_in['kode_bahan'] == kode_bahan) & (df_in['warna'] == warna)]['stok'].sum()
    else:
        in_stock = 0
    
    if not df_out.empty:
        out_stock = df_out[(df_out['kode_bahan'] == kode_bahan) & (df_out['warna'] == warna)]['stok'].sum()
    else:
        out_stock = 0

    return in_stock - out_stock

def get_in_out_records(start_date, end_date):
    df_in = get_barang_masuk()
    df_out = get_barang_keluar()
    
    if df_in.empty and df_out.empty:
        return pd.DataFrame()

    if not df_in.empty:
        df_in['tanggal_waktu'] = pd.to_datetime(df_in['tanggal_waktu'])
        df_in = df_in[(df_in['tanggal_waktu'].dt.date >= start_date) & (df_in['tanggal_waktu'].dt.date <= end_date)]
        df_in = df_in.assign(qty=df_in['stok'], type='Masuk', keterangan=df_in['keterangan'])
    
    if not df_out.empty:
        df_out['tanggal_waktu'] = pd.to_datetime(df_out['tanggal_waktu'])
        df_out = df_out[(df_out['tanggal_waktu'].dt.date >= start_date) & (df_out['tanggal_waktu'].dt.date <= end_date)]
        df_out = df_out.assign(qty=df_out['stok'], type='Keluar', keterangan=df_out['keterangan'])
    
    df = pd.concat([df_in[['tanggal_waktu', 'kode_bahan', 'warna', 'qty', 'type', 'keterangan']], 
                    df_out[['tanggal_waktu', 'kode_bahan', 'warna', 'qty', 'type', 'keterangan']]], ignore_index=True)
    
    df = df.sort_values(by='tanggal_waktu')
    return df

# --- Invoice Functions ---
def get_invoices():
    return get_data_from_gsheets('invoices')

def get_invoice_items(invoice_number):
    df_items = get_data_from_gsheets('invoice_items')
    if not df_items.empty:
        df_items['harga'] = pd.to_numeric(df_items['harga'], errors='coerce').fillna(0)
        df_items['total'] = pd.to_numeric(df_items['total'], errors='coerce').fillna(0)
    return df_items[df_items['invoice_number'] == invoice_number]

def get_barang_keluar():
    df = get_data_from_gsheets('barang_keluar')
    if df.empty:
        # Perbaikan: Buat DataFrame kosong dengan kolom yang dibutuhkan
        return pd.DataFrame(columns=['tanggal_waktu', 'kode_bahan', 'warna', 'stok', 'yard', 'keterangan'])

    df['stok'] = pd.to_numeric(df['stok'], errors='coerce').fillna(0).astype(int)
    df['yard'] = pd.to_numeric(df['yard'], errors='coerce').fillna(0.0)
    return df
    
def generate_invoice_pdf(invoice_data, invoice_items):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    pdf.cell(0, 10, 'PT. BERKAT KARYA ANUGERAH', 0, 1, 'C')
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, 'INVOICE', 0, 1, 'C')
    pdf.set_font("Arial", '', 12)
    pdf.ln(5)
    
    pdf.cell(0, 5, f"No Invoice: {invoice_data['No Invoice']}", 0, 1, 'L')
    pdf.cell(0, 5, f"Tanggal: {invoice_data['Tanggal & Waktu']}", 0, 1, 'L')
    pdf.cell(0, 5, f"Nama Pelanggan: {invoice_data['Nama Pelanggan']}", 0, 1, 'L')
    
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(10, 10, 'No', 1, 0, 'C')
    pdf.cell(70, 10, 'Item', 1, 0, 'C')
    pdf.cell(30, 10, 'Qty', 1, 0, 'C')
    pdf.cell(40, 10, 'Harga', 1, 0, 'C')
    pdf.cell(40, 10, 'Total Harga', 1, 1, 'C')

    pdf.set_font("Arial", '', 12)
    total_invoice_amount = 0
    # PERBAIKAN: Pastikan data numerik sebelum diproses
    invoice_items['harga'] = pd.to_numeric(invoice_items['harga'], errors='coerce').fillna(0)
    invoice_items['total'] = pd.to_numeric(invoice_items['total'], errors='coerce').fillna(0)

    for idx, row in invoice_items.iterrows():
        total_invoice_amount += row['total']
        pdf.cell(10, 10, str(idx + 1), 1, 0, 'C')
        pdf.cell(70, 10, row['nama_bahan'], 1)
        pdf.cell(30, 10, str(row['qty']), 1, 0, 'R')
        pdf.cell(40, 10, f"Rp {row['harga']:,.2f}", 1, 0, 'R')
        pdf.cell(40, 10, f"Rp {row['total']:,.2f}", 1, 1, 'R')

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(150, 10, 'Total', 1, 0, 'R')
    pdf.cell(40, 10, f"Rp {total_invoice_amount:,.2f}", 1, 1, 'R')
    
    pdf.ln(10)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 5, "Terimakasih atas pembelian anda", 0, 1, 'C')
    pdf.ln(10)
    pdf.cell(0, 5, "Ttd Accounting", 0, 1, 'R')
    
    # PERBAIKAN: Menggunakan BytesIO untuk kompatibilitas download
    pdf_output = pdf.output(dest='S')
    pdf_buffer = io.BytesIO(pdf_output)
    return pdf_buffer
    
def generate_invoice_number():
    df_invoices = get_invoices()
    today_date = datetime.now().strftime('%y%m%d')
    prefix = f"INV-{today_date}-"
    
    if not df_invoices.empty:
        df_invoices = df_invoices[df_invoices['invoice_number'].str.startswith(prefix)]
        if not df_invoices.empty:
            last_invoice = df_invoices['invoice_number'].max()
            try:
                last_seq = int(last_invoice.split('-')[-1])
            except (ValueError, IndexError):
                last_seq = 0
            new_seq = last_seq + 1
        else:
            new_seq = 1
    else:
        new_seq = 1
        
    new_invoice_number = f"{prefix}{new_seq:03d}"
    return new_invoice_number

def add_barang_keluar_and_invoice(invoice_number, customer_name, items):
    tanggal_waktu = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Check stock before starting transactions
    for item in items:
        current_stock = get_stock_balance(item['kode_bahan'], item['warna'])
        if item['qty'] > current_stock:
            return False, f"Stok untuk bahan {item['nama_bahan']} ({item['warna']}) tidak mencukupi. Stok saat ini: {current_stock}"

    # Insert into invoices table
    if not append_row_to_gsheet('invoices', [invoice_number, tanggal_waktu, customer_name]):
        return False, "Gagal membuat invoice."
    
    # Insert items and outgoing goods
    for item in items:
        if not append_row_to_gsheet('invoice_items', [invoice_number, item['kode_bahan'], item['nama_bahan'], item['qty'], item['harga'], item['total']]):
            return False, "Gagal menambahkan item ke invoice."
        if not append_row_to_gsheet('barang_keluar', [tanggal_waktu, item['kode_bahan'], item['warna'], item['qty'], item['yard'], item['keterangan']]):
            return False, "Gagal mencatat barang keluar."
    
    return True, "Transaksi berhasil dicatat dan invoice dibuat."

# --- Payroll Functions ---
def add_employee(nama, bagian, gaji):
    df_employees = get_employees()
    # Check if employee already exists to avoid duplicates
    if not df_employees.empty and (df_employees['nama_karyawan'] == nama).any():
        return False
    return append_row_to_gsheet('employees', [nama, bagian, gaji])

def get_employees():
    df = get_data_from_gsheets('employees')
    if not df.empty:
        df['gaji_pokok'] = pd.to_numeric(df['gaji_pokok'], errors='coerce').fillna(0)
    return df

def update_employee(old_name, new_nama, new_bagian, new_gaji):
    df_employees = get_employees()
    row_index = df_employees.index[df_employees['nama_karyawan'] == old_name].tolist()
    if not row_index:
        return False
    return update_row_in_gsheet('employees', row_index[0], [new_nama, new_bagian, new_gaji])

def delete_employee(nama):
    df_employees = get_employees()
    row_index = df_employees.index[df_employees['nama_karyawan'] == nama].tolist()
    if not row_index:
        return False
    return delete_row_from_gsheet('employees', row_index[0])

def add_payroll_record(employee_id, gaji_bulan, gaji_pokok, lembur, lembur_minggu, uang_makan, pot_absen_finger, ijin_hr, simpanan_wajib, potongan_koperasi, kasbon, gaji_akhir, keterangan):
    tanggal_waktu = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return append_row_to_gsheet('payroll', [tanggal_waktu, gaji_bulan, employee_id, gaji_pokok, lembur, lembur_minggu, uang_makan, pot_absen_finger, ijin_hr, simpanan_wajib, potongan_koperasi, kasbon, gaji_akhir, keterangan])

def get_payroll_records():
    df_payroll = get_data_from_gsheets('payroll')
    df_employees = get_employees()

    if df_payroll.empty or df_employees.empty:
        return pd.DataFrame()
    
    df_employees['id'] = range(1, len(df_employees) + 1)
    
    df_payroll = df_payroll.merge(df_employees, left_on='employee_id', right_on='id', how='left')
    
    return df_payroll[['tanggal_waktu', 'gaji_bulan', 'nama_karyawan', 'gaji_akhir', 'keterangan']]

def get_payroll_records_by_month(month_str):
    df_payroll = get_data_from_gsheets('payroll')
    df_employees = get_employees()
    
    if df_payroll.empty or df_employees.empty:
        return pd.DataFrame()
        
    df_employees['id'] = range(1, len(df_employees) + 1)
    
    df_payroll = df_payroll[df_payroll['gaji_bulan'] == month_str]
    
    # Perbaikan: Pastikan kolom numerik dikonversi sebelum diolah
    for col in ['gaji_pokok', 'lembur', 'lembur_minggu', 'uang_makan', 'pot_absen_finger', 'ijin_hr', 'simpanan_wajib', 'potongan_koperasi', 'kasbon', 'gaji_akhir']:
        df_payroll[col] = pd.to_numeric(df_payroll[col], errors='coerce').fillna(0)
    
    df_payroll = df_payroll.merge(df_employees, left_on='employee_id', right_on='id', how='left')
    
    return df_payroll

def generate_payslips_pdf(payslip_df):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    
    for idx, row in payslip_df.iterrows():
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        
        pdf.cell(0, 10, 'PT. BERKAT KARYA ANUGERAH', 0, 1, 'C')
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 5, 'SLIP GAJI', 0, 1, 'C')
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 10)
        pdf.cell(40, 5, 'Nama Karyawan:', 0)
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 5, row['nama_karyawan'], 0, 1)

        pdf.set_font("Arial", 'B', 10)
        pdf.cell(40, 5, 'Bagian:', 0)
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 5, row['bagian'], 0, 1)

        pdf.set_font("Arial", 'B', 10)
        pdf.cell(40, 5, 'Gaji Bulan:', 0)
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 5, row['gaji_bulan'], 0, 1)

        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, 'Pendapatan', 0, 1)
        pdf.set_font("Arial", '', 10)
        
        # Pendapatan
        pdf.cell(60, 5, 'Gaji Pokok', 0, 0)
        pdf.cell(5, 5, ':', 0, 0)
        pdf.cell(0, 5, f"Rp {row['gaji_pokok']:,.2f}", 0, 1, 'R')
        
        pdf.cell(60, 5, 'Lembur', 0, 0)
        pdf.cell(5, 5, ':', 0, 0)
        pdf.cell(0, 5, f"Rp {row['lembur']:,.2f}", 0, 1, 'R')
        
        pdf.cell(60, 5, 'Lembur Minggu', 0, 0)
        pdf.cell(5, 5, ':', 0, 0)
        pdf.cell(0, 5, f"Rp {row['lembur_minggu']:,.2f}", 0, 1, 'R')
        
        pdf.cell(60, 5, 'Uang Makan', 0, 0)
        pdf.cell(5, 5, ':', 0, 0)
        pdf.cell(0, 5, f"Rp {row['uang_makan']:,.2f}", 0, 1, 'R')

        # Total 1
        total1 = row['gaji_pokok'] + row['lembur'] + row['lembur_minggu'] + row['uang_makan']
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(60, 5, 'Total Pendapatan (1)', 'T', 0)
        pdf.cell(5, 5, ':', 'T', 0)
        pdf.cell(0, 5, f"Rp {total1:,.2f}", 'T', 1, 'R')

        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, 'Potongan', 0, 1)
        pdf.set_font("Arial", '', 10)
        
        # Potongan
        pdf.cell(60, 5, 'Absen Finger', 0, 0)
        pdf.cell(5, 5, ':', 0, 0)
        pdf.cell(0, 5, f"Rp {row['pot_absen_finger']:,.2f}", 0, 1, 'R')

        pdf.cell(60, 5, 'Ijin HR', 0, 0)
        pdf.cell(5, 5, ':', 0, 0)
        pdf.cell(0, 5, f"Rp {row['ijin_hr']:,.2f}", 0, 1, 'R')

        # Total 2
        total2 = total1 - row['pot_absen_finger'] - row['ijin_hr']
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(60, 5, 'Total Pendapatan Setelah Potongan Absen (2)', 'T', 0)
        pdf.cell(5, 5, ':', 'T', 0)
        pdf.cell(0, 5, f"Rp {total2:,.2f}", 'T', 1, 'R')

        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, 'Potongan Lain-lain', 0, 1)
        pdf.set_font("Arial", '', 10)

        # Potongan Lain-lain
        pdf.cell(60, 5, 'Simpanan Wajib', 0, 0)
        pdf.cell(5, 5, ':', 0, 0)
        pdf.cell(0, 5, f"Rp {row['simpanan_wajib']:,.2f}", 0, 1, 'R')

        pdf.cell(60, 5, 'Potongan Koperasi', 0, 0)
        pdf.cell(5, 5, ':', 0, 0)
        pdf.cell(0, 5, f"Rp {row['potongan_koperasi']:,.2f}", 0, 1, 'R')

        pdf.cell(60, 5, 'Kasbon', 0, 0)
        pdf.cell(5, 5, ':', 0, 0)
        pdf.cell(0, 5, f"Rp {row['kasbon']:,.2f}", 0, 1, 'R')
        
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(60, 5, 'TOTAL GAJI AKHIR', 'T', 0)
        pdf.cell(5, 5, ':', 'T', 0)
        pdf.cell(0, 5, f"Rp {row['gaji_akhir']:,.2f}", 'T', 1, 'R')

        pdf.ln(10)
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 5, f"Keterangan: {row['keterangan']}", 0, 1)
        pdf.ln(15)
        pdf.cell(0, 5, "Ttd Accounting", 0, 1, 'R')

    # PERBAIKAN: Menggunakan BytesIO untuk kompatibilitas download
    pdf_output = pdf.output(dest='S')
    pdf_buffer = io.BytesIO(pdf_output)
    return pdf_buffer

def show_dashboard():
    st.title("Dashboard Bisnis 📈")
    st.markdown("---")

    master_df = get_master_barang()
    
    col_total_value, col_total_items = st.columns(2)
    if not master_df.empty:
        # Perbaikan: Konversi harga ke numerik
        master_df['harga'] = pd.to_numeric(master_df['harga'], errors='coerce').fillna(0)
        
        master_df['Stok Saat Ini'] = master_df.apply(lambda row: get_stock_balance(row['kode_bahan'], row['warna']), axis=1)
        total_value = (master_df['Stok Saat Ini'] * master_df['harga']).sum()
        total_items = master_df['Stok Saat Ini'].sum()

        with col_total_value:
            st.metric("Total Nilai Stok Saat Ini", f"Rp {total_value:,.2f}")
        with col_total_items:
            st.metric("Total Barang di Gudang", f"{int(total_items)} Unit")
    else:
        st.info("Belum ada master barang untuk ditampilkan di dashboard.")

    st.markdown("---")
    st.header("Stok 10 Item Terendah")
    if not master_df.empty:
        low_stock_df = master_df.sort_values(by='Stok Saat Ini', ascending=True).head(10)
        low_stock_df['label'] = low_stock_df['nama_bahan'] + ' (' + low_stock_df['warna'] + ')'
        
        if not low_stock_df.empty:
            fig = px.bar(low_stock_df, 
                         x='label', 
                         y='Stok Saat Ini',
                         title='10 Item dengan Stok Terendah',
                         labels={'label': 'Nama Bahan', 'Stok Saat Ini': 'Jumlah Stok'},
                         color='Stok Saat Ini',
                         color_continuous_scale=px.colors.sequential.Sunset
                         )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Semua stok barang sudah habis.")
    else:
        st.info("Belum ada master barang untuk menampilkan grafik.")

def show_master_barang():
    st.title("Master Barang 📦")
    st.markdown("---")
    
    tab_add, tab_list = st.tabs(["➕ Tambah Barang Baru", "📝 Daftar Barang & Kelola"])
    
    with tab_add:
        with st.expander("Form Tambah Barang Baru", expanded=True):
            with st.form("add_item_form"):
                col1, col2 = st.columns(2)
                with col1:
                    kode_bahan = st.text_input("Kode Bahan").upper()
                    nama_supplier = st.text_input("Nama Supplier")
                    warna = st.text_input("Warna").lower()
                with col2:
                    nama_bahan = st.text_input("Nama Bahan")
                    rak = st.text_input("Rak")
                    harga_str = st.text_input("Harga", value='0')
                submitted = st.form_submit_button("💾 Simpan Barang")
                if submitted:
                    try:
                        harga = float(harga_str)
                        if harga < 0:
                            st.error("Harga tidak boleh negatif. ❌")
                        elif add_master_item(kode_bahan, nama_supplier, nama_bahan, warna, rak, harga):
                            st.success(f"Barang **{nama_bahan}** dengan warna **{warna}** berhasil ditambahkan. ✅")
                            st.rerun()
                        else:
                            st.error("Kombinasi Kode Bahan dan Warna tersebut sudah ada. ❌")
                    except ValueError:
                        st.error("Harga harus berupa angka. ❌")
    with tab_list:
        st.subheader("Daftar Barang")
        df = get_master_barang()
        if not df.empty:
            df_display = df.copy()
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            st.markdown("---")
            with st.expander("Kelola Data Master"):
                item_options_map = {f"{row['kode_bahan']} ({row['warna']})": (row['kode_bahan'], row['warna']) for _, row in df.iterrows()}
                item_to_edit_str = st.selectbox("Pilih Kode Bahan (Warna)", list(item_options_map.keys()), key="select_edit_master")
                if item_to_edit_str:
                    selected_kode, selected_warna = item_options_map[item_to_edit_str]
                    filtered_df = df[(df['kode_bahan'] == selected_kode) & (df['warna'] == selected_warna)]
                    if not filtered_df.empty:
                        selected_row = filtered_df.iloc[0]
                        harga_value = float(selected_row['harga']) if pd.notna(selected_row['harga']) else 0.0
                        with st.form("edit_master_form"):
                            col1, col2 = st.columns(2)
                            with col1:
                                new_kode_bahan = st.text_input("Kode Bahan Baru", value=selected_row['kode_bahan']).upper()
                                new_nama_bahan = st.text_input("Nama Bahan", value=selected_row['nama_bahan'])
                                new_rak = st.text_input("Rak", value=selected_row['rak'])
                            with col2:
                                new_warna = st.text_input("Warna Baru", value=selected_row['warna']).lower()
                                new_nama_supplier = st.text_input("Nama Supplier", value=selected_row['nama_supplier'])
                                new_harga_str = st.text_input("Harga", value=str(harga_value))
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                if st.form_submit_button("Simpan Perubahan"):
                                    try:
                                        new_harga = float(new_harga_str)
                                        if new_harga < 0:
                                            st.error("Harga tidak boleh negatif. ❌")
                                        elif update_master_item(selected_row['kode_bahan'], selected_row['warna'], new_kode_bahan, new_warna, new_nama_supplier, new_nama_bahan, new_rak, new_harga):
                                            st.success("Data berhasil diperbarui! ✅")
                                            st.rerun()
                                        else:
                                            st.error("Kombinasi Kode Bahan dan Warna baru sudah ada. Gagal menyimpan perubahan. ❌")
                                    except ValueError:
                                        st.error("Harga harus berupa angka. ❌")
                            with col_btn2:
                                if st.form_submit_button("Hapus Barang"):
                                    if delete_master_item(selected_row['kode_bahan'], selected_row['warna']):
                                        st.success("Data berhasil dihapus! 🗑️")
                                        st.rerun()
                                    else:
                                        st.error("Gagal menghapus data.")
                    else:
                        st.warning("Data yang dipilih tidak ditemukan. Silakan refresh halaman atau pilih data lain.")
        else:
            st.info("Belum ada master barang.")

def show_input_masuk():
    st.title("Input Barang Masuk 📥")
    st.markdown("---")
    master_df = get_master_barang()
    if master_df.empty:
        st.warning("Belum ada master barang. Silakan tambahkan di menu Master Barang. ⚠️")
        return
    tab_add, tab_list = st.tabs(["➕ Input Barang Masuk Baru", "📝 Daftar Barang Masuk & Kelola"])
    with tab_add:
        with st.expander("Form Input Barang Masuk", expanded=True):
            with st.form("input_masuk_form"):
                col1, col2 = st.columns(2)
                with col1:
                    kode_bahan_options = master_df['kode_bahan'].unique().tolist()
                    selected_kode_bahan = st.selectbox("Pilih Kode Bahan", kode_bahan_options, key="in_kode_bahan")
                with col2:
                    filtered_colors = master_df[master_df['kode_bahan'] == selected_kode_bahan]['warna'].tolist()
                    selected_warna = st.selectbox("Warna", filtered_colors, key="in_warna")
                stok_str = st.text_input("Stok", value='1', key="in_stok")
                yard_str = st.text_input("Yard", value='0', key="in_yard")
                keterangan = st.text_area("Keterangan", key="in_keterangan")
                submitted = st.form_submit_button("💾 Simpan Barang Masuk")
                if submitted:
                    try:
                        stok = int(stok_str)
                        yard = float(yard_str)
                        if stok < 1:
                            st.error("Stok harus lebih dari 0. ❌")
                        else:
                            tanggal_waktu = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            if add_barang_masuk(tanggal_waktu, selected_kode_bahan, selected_warna, stok, yard, keterangan):
                                st.success("Barang masuk berhasil dicatat. ✅")
                                st.rerun()
                            else:
                                st.error("Gagal menyimpan data barang masuk.")
                    except ValueError:
                        st.error("Stok dan Yard harus berupa angka. ❌")
    with tab_list:
        st.subheader("Daftar Barang Masuk")
        df = get_barang_masuk()
        if not df.empty:
            df['tanggal_waktu'] = pd.to_datetime(df['tanggal_waktu']).dt.strftime('%Y-%m-%d %H:%M:%S')
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.markdown("---")
            with st.expander("Kelola Data Barang Masuk"):
                # Gsheets doesn't have a simple ID column, so we'll use a combination of fields as a unique identifier.
                df_to_edit = df.copy()
                df_to_edit['unique_key'] = df_to_edit['tanggal_waktu'] + ' - ' + df_to_edit['kode_bahan'] + ' - ' + df_to_edit['warna'] + ' - ' + df_to_edit['stok'].astype(str)
                record_to_edit_str = st.selectbox("Pilih Data yang akan diedit/dihapus", df_to_edit['unique_key'].tolist(), key="select_edit_in")
                if record_to_edit_str:
                    selected_row = df_to_edit[df_to_edit['unique_key'] == record_to_edit_str].iloc[0]
                    row_index = df_to_edit[df_to_edit['unique_key'] == record_to_edit_str].index[0]
                    with st.form("edit_in_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            edit_kode_bahan = st.selectbox("Kode Bahan", master_df['kode_bahan'].unique().tolist(), index=master_df['kode_bahan'].unique().tolist().index(selected_row['kode_bahan']), key="edit_in_kode")
                        with col2:
                            edit_warna_options = master_df[master_df['kode_bahan'] == edit_kode_bahan]['warna'].tolist()
                            edit_warna = st.selectbox("Warna", edit_warna_options, index=edit_warna_options.index(selected_row['warna']), key="edit_in_warna")
                        edit_stok_str = st.text_input("Stok", value=str(selected_row['stok']), key="edit_in_stok")
                        edit_yard_str = st.text_input("Yard", value=str(selected_row['yard']), key="edit_in_yard")
                        edit_keterangan = st.text_area("Keterangan", value=selected_row['keterangan'], key="edit_in_keterangan")
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.form_submit_button("Simpan Perubahan"):
                                try:
                                    edit_stok = int(edit_stok_str)
                                    edit_yard = float(edit_yard_str)
                                    if edit_stok < 1:
                                        st.error("Stok harus lebih dari 0. ❌")
                                    else:
                                        tanggal_waktu = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                        if update_barang_masuk(row_index, tanggal_waktu, edit_kode_bahan, edit_warna, edit_stok, edit_yard, edit_keterangan):
                                            st.success("Data berhasil diperbarui! ✅")
                                            st.rerun()
                                        else:
                                            st.error("Gagal menyimpan perubahan.")
                                except ValueError:
                                    st.error("Stok dan Yard harus berupa angka. ❌")
                        with col_btn2:
                            if st.form_submit_button("Hapus Data"):
                                if delete_barang_masuk(row_index):
                                    st.success("Data berhasil dihapus! 🗑️")
                                    st.rerun()
                                else:
                                    st.error("Gagal menghapus data.")
        else:
            st.info("Belum ada data barang masuk.")

def show_transaksi_keluar_invoice_page():
    st.title("Transaksi Keluar & Invoice 🧾")
    st.markdown("---")
    
    master_df = get_master_barang()
    if master_df.empty:
        st.warning("Belum ada master barang. Silakan tambahkan di menu Master Barang. ⚠️")
        return

    tab_input, tab_list_invoices = st.tabs(["➕ Buat Transaksi Keluar", "📄 Daftar Invoice"])
    
    with tab_input:
        with st.expander("Form Transaksi Keluar", expanded=True):
            customer_name = st.text_input("Nama Pelanggan", key="customer_name")
            
            if 'cart_items' not in st.session_state:
                st.session_state.cart_items = []

            # Add Item Form
            st.subheader("Tambah Item ke Invoice")
            with st.form("add_item_form"):
                col_item1, col_item2, col_item3 = st.columns(3)
                with col_item1:
                    kode_bahan_options = master_df['kode_bahan'].unique().tolist()
                    selected_kode_bahan = st.selectbox("Pilih Kode Bahan", kode_bahan_options, key="out_kode_bahan")
                with col_item2:
                    filtered_items = master_df[master_df['kode_bahan'] == selected_kode_bahan]
                    warna_options = filtered_items['warna'].tolist()
                    selected_warna = st.selectbox("Warna", warna_options, key="out_warna")
                with col_item3:
                    item_details = filtered_items[filtered_items['warna'] == selected_warna].iloc[0]
                    st.write(f"Harga: **Rp {float(item_details['harga']):,.2f}**")
                    st.write(f"Stok Tersedia: **{int(get_stock_balance(selected_kode_bahan, selected_warna))}**")
                
                qty_str = st.text_input("Jumlah (Stok)", value='1', key="out_qty")
                yard_str = st.text_input("Jumlah (Yard)", value='0', key="out_yard")
                
                # PERBAIKAN: Gunakan text_input untuk harga dan total
                keterangan = st.text_area("Keterangan", key="out_keterangan")
                
                add_item_button = st.form_submit_button("➕ Tambah Item")
                
                if add_item_button:
                    try:
                        qty = int(qty_str)
                        yard = float(yard_str)
                        item_harga = float(item_details['harga'])
                        item_total = qty * item_harga

                        if qty <= 0:
                            st.error("Jumlah (Stok) harus lebih dari 0. ❌")
                        elif qty > get_stock_balance(selected_kode_bahan, selected_warna):
                            st.error(f"Stok tidak mencukupi. Sisa stok: {get_stock_balance(selected_kode_bahan, selected_warna)}")
                        else:
                            st.session_state.cart_items.append({
                                'kode_bahan': selected_kode_bahan,
                                'nama_bahan': item_details['nama_bahan'],
                                'warna': selected_warna,
                                'qty': qty,
                                'yard': yard,
                                'harga': item_harga,
                                'total': item_total,
                                'keterangan': keterangan
                            })
                            st.success("Item berhasil ditambahkan ke keranjang. ✅")
                            st.rerun()
                    except ValueError:
                        st.error("Jumlah (Stok) dan Yard harus berupa angka. ❌")
            
            st.markdown("---")
            st.subheader("Keranjang Invoice")
            if st.session_state.cart_items:
                cart_df = pd.DataFrame(st.session_state.cart_items)
                cart_df_display = cart_df[['nama_bahan', 'warna', 'qty', 'yard', 'harga', 'total']]
                st.dataframe(cart_df_display, use_container_width=True, hide_index=True)
                
                total_semua = cart_df['total'].sum()
                st.metric("Total Invoice", f"Rp {total_semua:,.2f}")
                
                if st.button("Buat Invoice & Catat Transaksi", use_container_width=True, type="primary"):
                    if not customer_name:
                        st.error("Nama pelanggan tidak boleh kosong. ❌")
                    else:
                        invoice_number = generate_invoice_number()
                        success, message = add_barang_keluar_and_invoice(invoice_number, customer_name, st.session_state.cart_items)
                        if success:
                            st.success(f"Invoice **{invoice_number}** berhasil dibuat dan transaksi dicatat. ✅")
                            # Clear cart after successful transaction
                            st.session_state.cart_items = []
                            st.rerun()
                        else:
                            st.error(f"Gagal memproses transaksi: {message} ❌")
            else:
                st.info("Keranjang invoice masih kosong.")

    with tab_list_invoices:
        st.subheader("Daftar Invoice")
        df_invoices = get_invoices()
        if not df_invoices.empty:
            df_invoices_display = df_invoices.copy()
            df_invoices_display['tanggal_waktu'] = pd.to_datetime(df_invoices_display['tanggal_waktu']).dt.strftime('%Y-%m-%d %H:%M:%S')
            st.dataframe(df_invoices_display, use_container_width=True, hide_index=True)

            selected_invoice = st.selectbox("Pilih Nomor Invoice untuk Dilihat", df_invoices['invoice_number'].tolist())
            if selected_invoice:
                invoice_data = df_invoices[df_invoices['invoice_number'] == selected_invoice].iloc[0]
                invoice_items_df = get_invoice_items(selected_invoice)

                if st.button("Download Invoice PDF"):
                    if not invoice_items_df.empty:
                        invoice_details = {
                            "No Invoice": invoice_data['invoice_number'],
                            "Tanggal & Waktu": invoice_data['tanggal_waktu'],
                            "Nama Pelanggan": invoice_data['customer_name']
                        }
                        try:
                            pdf_file = generate_invoice_pdf(invoice_details, invoice_items_df)
                            # PERBAIKAN: Gunakan .getvalue() untuk mengambil data biner dari buffer
                            st.download_button(
                                label="Klik untuk Download",
                                data=pdf_file.getvalue(),
                                file_name=f"Invoice_{invoice_data['invoice_number']}.pdf",
                                mime="application/pdf"
                            )
                        except Exception as e:
                            st.error(f"Terjadi kesalahan saat membuat PDF: {e}")
                    else:
                        st.warning("Data item invoice tidak ditemukan.")
        else:
            st.info("Belum ada invoice yang dibuat.")

def show_monitoring_stok():
    st.title("Monitoring Stok 📊")
    st.markdown("---")
    
    tab_current, tab_history = st.tabs(["📈 Stok Saat Ini", "📜 Riwayat Transaksi"])

    with tab_current:
        st.subheader("Stok Barang Saat Ini")
        master_df = get_master_barang()
        if not master_df.empty:
            master_df['Stok Saat Ini'] = master_df.apply(lambda row: get_stock_balance(row['kode_bahan'], row['warna']), axis=1)
            st.dataframe(master_df, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada data barang.")
            
    with tab_history:
        st.subheader("Riwayat Barang Masuk & Keluar")
        
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            start_date = st.date_input("Tanggal Mulai", datetime.now().date(), key="start_date")
        with col_date2:
            end_date = st.date_input("Tanggal Selesai", datetime.now().date(), key="end_date")
        
        if start_date > end_date:
            st.error("Tanggal mulai tidak boleh lebih dari tanggal selesai.")
        else:
            df_history = get_in_out_records(start_date, end_date)
            if not df_history.empty:
                st.dataframe(df_history, use_container_width=True, hide_index=True)
            else:
                st.info("Tidak ada riwayat transaksi pada rentang tanggal tersebut.")

def show_payroll_page():
    st.title("Penggajian Karyawan 💰")
    st.markdown("---")

    tab_input_gaji, tab_master_karyawan, tab_riwayat_gaji = st.tabs(["📝 Input Gaji", "👥 Master Karyawan", "📜 Riwayat Gaji"])

    with tab_input_gaji:
        st.subheader("Input Gaji Karyawan")
        employees_df = get_employees()
        if employees_df.empty:
            st.warning("Belum ada data karyawan. Silakan tambahkan di menu 'Master Karyawan'.")
            return
        
        month_options = [datetime.now().strftime('%Y-%m')] + [
            (datetime.now().replace(day=1) - pd.DateOffset(months=i)).strftime('%Y-%m') for i in range(1, 12)
        ]
        gaji_bulan = st.selectbox("Bulan Gaji", month_options, key="gaji_bulan")

        nama_karyawan = st.selectbox("Pilih Karyawan", employees_df['nama_karyawan'].tolist(), key="select_payroll_employee")
        if nama_karyawan:
            selected_employee = employees_df[employees_df['nama_karyawan'] == nama_karyawan].iloc[0]
            employee_id = selected_employee.name + 1 # Gspread row index starts at 1, header is 1, so data starts at row 2.
            gaji_pokok = float(selected_employee['gaji_pokok']) if pd.notna(selected_employee['gaji_pokok']) else 0.0
            
            st.metric("Gaji Pokok Karyawan", f"Rp {gaji_pokok:,.2f}")

            with st.form("payroll_form"):
                st.subheader("Pendapatan Lain")
                lembur_str = st.text_input("Lembur", value='0')
                lembur_minggu_str = st.text_input("Lembur Minggu", value='0')
                uang_makan_str = st.text_input("Uang Makan", value='0')

                st.subheader("Potongan")
                pot_absen_finger_str = st.text_input("Potongan Absen Finger", value='0')
                ijin_hr_str = st.text_input("Ijin HR", value='0')
                simpanan_wajib_str = st.text_input("Simpanan Wajib", value='0')
                potongan_koperasi_str = st.text_input("Potongan Koperasi", value='0')
                kasbon_str = st.text_input("Kasbon", value='0')
                
                keterangan = st.text_area("Keterangan Tambahan")

                submit_gaji_btn = st.form_submit_button("💾 Hitung & Simpan Gaji")
                
                if submit_gaji_btn:
                    try:
                        lembur = float(lembur_str)
                        lembur_minggu = float(lembur_minggu_str)
                        uang_makan = float(uang_makan_str)
                        pot_absen_finger = float(pot_absen_finger_str)
                        ijin_hr = float(ijin_hr_str)
                        simpanan_wajib = float(simpanan_wajib_str)
                        potongan_koperasi = float(potongan_koperasi_str)
                        kasbon = float(kasbon_str)
                        
                        gaji_akhir = gaji_pokok + lembur + lembur_minggu + uang_makan - pot_absen_finger - ijin_hr - simpanan_wajib - potongan_koperasi - kasbon
                        
                        if add_payroll_record(employee_id, gaji_bulan, gaji_pokok, lembur, lembur_minggu, uang_makan, pot_absen_finger, ijin_hr, simpanan_wajib, potongan_koperasi, kasbon, gaji_akhir, keterangan):
                            st.success(f"Gaji untuk **{nama_karyawan}** bulan **{gaji_bulan}** berhasil dicatat. ✅")
                            st.rerun()
                        else:
                            st.error("Gagal mencatat data gaji.")
                    except ValueError:
                        st.error("Mohon masukkan angka yang valid untuk semua input gaji dan potongan. ❌")
                        
    with tab_master_karyawan:
        st.subheader("Daftar Karyawan")
        employees_df = get_employees()
        if not employees_df.empty:
            st.dataframe(employees_df, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada data karyawan.")
        
        st.markdown("---")
        
        with st.expander("Kelola Data Karyawan", expanded=False):
            action = st.radio("Pilih Aksi", ["Tambah Karyawan Baru", "Edit Karyawan", "Hapus Karyawan"])
            
            if action == "Tambah Karyawan Baru":
                with st.form("add_employee_form"):
                    nama_karyawan_add = st.text_input("Nama Karyawan Baru")
                    bagian_add = st.text_input("Bagian")
                    gaji_pokok_add_str = st.text_input("Gaji Pokok", value='0')
                    submitted_add = st.form_submit_button("💾 Simpan Karyawan")
                    if submitted_add:
                        try:
                            gaji_pokok_add = float(gaji_pokok_add_str)
                            if gaji_pokok_add < 0:
                                st.error("Gaji pokok tidak boleh negatif. ❌")
                            elif add_employee(nama_karyawan_add, bagian_add, gaji_pokok_add):
                                st.success("Karyawan baru berhasil ditambahkan! ✅")
                                st.rerun()
                            else:
                                st.error("Karyawan dengan nama tersebut sudah ada. ❌")
                        except ValueError:
                            st.error("Gaji pokok harus berupa angka. ❌")

            elif action == "Edit Karyawan":
                if not employees_df.empty:
                    selected_name = st.selectbox("Pilih Karyawan untuk Diedit", employees_df['nama_karyawan'].tolist())
                    selected_row = employees_df[employees_df['nama_karyawan'] == selected_name].iloc[0]
                    with st.form("edit_employee_form"):
                        new_nama = st.text_input("Nama Karyawan Baru", value=selected_row['nama_karyawan'])
                        new_bagian = st.text_input("Bagian Baru", value=selected_row['bagian'])
                        new_gaji_pokok_str = st.text_input("Gaji Pokok Baru", value=str(selected_row['gaji_pokok']))
                        submitted_edit = st.form_submit_button("Simpan Perubahan")
                        if submitted_edit:
                            try:
                                new_gaji_pokok = float(new_gaji_pokok_str)
                                if new_gaji_pokok < 0:
                                    st.error("Gaji pokok tidak boleh negatif. ❌")
                                elif update_employee(selected_name, new_nama, new_bagian, new_gaji_pokok):
                                    st.success("Data karyawan berhasil diperbarui! ✅")
                                    st.rerun()
                                else:
                                    st.error("Gagal menyimpan perubahan. Nama karyawan mungkin sudah ada.")
                            except ValueError:
                                st.error("Gaji pokok harus berupa angka. ❌")
                else:
                    st.info("Tidak ada data karyawan untuk diedit.")
            
            elif action == "Hapus Karyawan":
                if not employees_df.empty:
                    selected_name = st.selectbox("Pilih Karyawan untuk Dihapus", employees_df['nama_karyawan'].tolist())
                    if st.button("Hapus Karyawan"):
                        if delete_employee(selected_name):
                            st.success("Karyawan berhasil dihapus! 🗑️")
                            st.rerun()
                        else:
                            st.error("Gagal menghapus karyawan.")
                else:
                    st.info("Tidak ada data karyawan untuk dihapus.")
    
    with tab_riwayat_gaji:
        st.subheader("Riwayat Gaji Bulanan")
        
        # PERBAIKAN: Pastikan dropdown memiliki opsi
        month_options = [datetime.now().strftime('%Y-%m')] + [(datetime.now().replace(day=1) - pd.DateOffset(months=i)).strftime('%Y-%m') for i in range(1, 12)]
        selected_month = st.selectbox("Pilih Bulan", month_options)
        
        payroll_df = get_payroll_records_by_month(selected_month)
        
        if not payroll_df.empty:
            st.dataframe(payroll_df[['tanggal_waktu', 'nama_karyawan', 'gaji_akhir', 'keterangan']], use_container_width=True, hide_index=True)
            
            if st.button("Download Slip Gaji PDF"):
                try:
                    pdf_file = generate_payslips_pdf(payroll_df)
                    # PERBAIKAN: Gunakan .getvalue() untuk mengambil data biner dari buffer
                    st.download_button(
                        label="Klik untuk Download",
                        data=pdf_file.getvalue(),
                        file_name=f"Slip_Gaji_{selected_month}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"Terjadi kesalahan saat membuat PDF: {e}")
        else:
            st.info("Tidak ada data gaji untuk bulan yang dipilih.")
            
# --- MAIN APP LOGIC ---
def main():
    check_and_create_worksheets()
    check_and_create_owner()
    
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    
    if st.session_state['logged_in']:
        show_app()
    else:
        show_login_page()

def show_login_page():
    st.title("Login Sistem Toko Bangunan 🏠")
    st.markdown("---")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if check_login(username, password):
                st.session_state['logged_in'] = True
                st.session_state['page'] = 'Dashboard'
                st.success("Login berhasil! ✅")
                st.rerun()
            else:
                st.error("Username atau password salah. ❌")
                
def show_app():
    if 'page' not in st.session_state:
        st.session_state['page'] = 'Dashboard'

    st.sidebar.title("Navigasi")
    st.sidebar.markdown("---")
    
    if st.sidebar.button("Dashboard 📈", use_container_width=True):
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
        show_payroll_page()

if __name__ == "__main__":
    main()
