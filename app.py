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
    
    # PERBAIKAN: Hapus .encode('latin1') karena .output(dest='S') sudah mengembalikan bytes
    return pdf.output(dest='S')
    
def generate_invoice_number():
    df_invoices = get_invoices()
    today_date = datetime.now().strftime('%y%m%d')
    prefix = f"INV-{today_date}-"
    
    if not df_invoices.empty:
        df_invoices = df_invoices[df_invoices['invoice_number'].str.startswith(prefix)]
        if not df_invoices.empty:
            last_invoice = df_invoices['invoice_number'].max()
            last_seq = int(last_invoice.split('-')[-1])
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

    # PERBAIKAN: Pastikan semua nilai numerik dikonversi ke float atau int standar Python
    data_list = [
        tanggal_waktu,
        gaji_bulan,
        int(employee_id),
        float(gaji_pokok),
        float(lembur),
        float(lembur_minggu),
        float(uang_makan),
        float(pot_absen_finger),
        float(ijin_hr),
        float(simpanan_wajib),
        float(potongan_koperasi),
        float(kasbon),
        float(gaji_akhir),
        keterangan
    ]
    
    return append_row_to_gsheet('payroll', data_list)

def get_payroll_records():
    df_payroll = get_data_from_gsheets('payroll')
    df_employees = get_employees()

    if df_payroll.empty or df_employees.empty:
        return pd.DataFrame()
    
    df_employees['id'] = range(1, len(df_employees) + 1)
    
    df_payroll = df_payroll.merge(df_employees, left_on='employee_id', right_on='id', how='left')
    
    return df_payroll[['tanggal_waktu', 'gaji_bulan', 'nama_karyawan', 'gaji_akhir', 'keterangan']]

# PERBAIKAN: Fungsi ini telah diperbaiki untuk memastikan semua kolom ada
def get_payroll_records_by_month(month_str):
    df_payroll = get_data_from_gsheets('payroll')
    df_employees = get_employees()
    
    if df_payroll.empty or df_employees.empty:
        return pd.DataFrame()
        
    df_employees['id'] = range(1, len(df_employees) + 1)
    
    df_payroll = df_payroll[df_payroll['gaji_bulan'] == month_str]
    
    # Merge dataframes
    merged_df = df_payroll.merge(df_employees, left_on='employee_id', right_on='id', how='left')
    
    # PERBAIKAN: Pastikan kolom numerik dikonversi sebelum diolah, dan handle missing columns
    for col in ['gaji_pokok_x', 'lembur', 'lembur_minggu', 'uang_makan', 'pot_absen_finger', 'ijin_hr', 'simpanan_wajib', 'potongan_koperasi', 'kasbon', 'gaji_akhir']:
        if col in merged_df.columns:
            merged_df[col] = pd.to_numeric(merged_df[col], errors='coerce').fillna(0)
        else:
            merged_df[col] = 0.0 # Add a column with default value if it's missing
    
    # Rename gaji_pokok_x to gaji_pokok for consistency
    merged_df.rename(columns={'gaji_pokok_x': 'gaji_pokok'}, inplace=True)
    
    return merged_df

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

    # PERBAIKAN: Hapus .encode('latin1') karena .output(dest='S') sudah mengembalikan bytes
    return pdf.output(dest='S')

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
        low_stock_df['label'] = low_stock_df['nama_bahan'].astype(str) + ' (' + low_stock_df['warna'].astype(str) + ')'
        
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
                    # PERBAIKAN: Menggunakan st.text_input dan mengonversi ke float
                    harga_str = st.text_input("Harga", value="0.0")
                    try:
                        harga = float(harga_str)
                    except ValueError:
                        st.error("Harga harus berupa angka. Menggunakan nilai default 0.")
                        harga = 0.0
                
                submitted = st.form_submit_button("💾 Simpan Barang")
                if submitted:
                    if add_master_item(kode_bahan, nama_supplier, nama_bahan, warna, rak, harga):
                        st.success(f"Barang **{nama_bahan}** dengan warna **{warna}** berhasil ditambahkan. ✅")
                        st.rerun()
                    else:
                        st.error("Kombinasi Kode Bahan dan Warna tersebut sudah ada. ❌")
    
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
                                # PERBAIKAN: Menggunakan st.text_input dan mengonversi ke float
                                new_harga_str = st.text_input("Harga", value=str(harga_value))
                                
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                if st.form_submit_button("Simpan Perubahan"):
                                    try:
                                        new_harga = float(new_harga_str)
                                        if update_master_item(selected_row['kode_bahan'], selected_row['warna'], new_kode_bahan, new_warna, new_nama_supplier, new_nama_bahan, new_rak, new_harga):
                                            st.success("Data berhasil diperbarui! ✅")
                                            st.rerun()
                                        else:
                                            st.error("Kombinasi Kode Bahan dan Warna baru sudah ada. Gagal menyimpan perubahan. ❌")
                                    except ValueError:
                                        st.error("Harga harus berupa angka. Gagal menyimpan perubahan.")
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
                
                # PERBAIKAN: Menggunakan st.text_input dan mengonversi ke int
                stok_str = st.text_input("Stok", value="0", help="Masukkan angka")
                yard_str = st.text_input("Yard", value="0.0", help="Masukkan angka (desimal)")
                keterangan = st.text_area("Keterangan", key="in_keterangan")
                
                submitted = st.form_submit_button("💾 Simpan Barang Masuk")
                if submitted:
                    try:
                        stok = int(stok_str)
                        yard = float(yard_str)
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
                    row_index = df_to_edit[df_to_edit['unique_key'] == record_to_edit_str].index.tolist()[0]
                    
                    with st.form("edit_in_form"):
                        edit_tanggal_waktu = st.text_input("Tanggal & Waktu", value=selected_row['tanggal_waktu'])
                        kode_bahan_options = master_df['kode_bahan'].unique().tolist()
                        edit_kode_bahan = st.selectbox("Kode Bahan", kode_bahan_options, index=kode_bahan_options.index(selected_row['kode_bahan']), key="edit_in_kode")
                        
                        filtered_colors_edit = master_df[master_df['kode_bahan'] == edit_kode_bahan]['warna'].tolist()
                        edit_warna = st.selectbox("Warna", filtered_colors_edit, index=filtered_colors_edit.index(selected_row['warna']), key="edit_in_warna")
                        
                        # PERBAIKAN: Menggunakan st.text_input dan mengonversi
                        stok_value = int(selected_row['stok']) if pd.notna(selected_row['stok']) else 0
                        yard_value = float(selected_row['yard']) if pd.notna(selected_row['yard']) else 0.0

                        edit_stok_str = st.text_input("Stok", value=str(stok_value), key="edit_in_stok")
                        edit_yard_str = st.text_input("Yard", value=str(yard_value), key="edit_in_yard")
                        
                        # PERBAIKAN: Tangani nilai NaN dari kolom keterangan
                        keterangan_value = str(selected_row['keterangan']) if pd.notna(selected_row['keterangan']) else ""
                        edit_keterangan = st.text_area("Keterangan", value=keterangan_value, key="edit_in_ket")

                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.form_submit_button("Simpan Perubahan"):
                                try:
                                    edit_stok = int(edit_stok_str)
                                    edit_yard = float(edit_yard_str)
                                    if update_barang_masuk(row_index, edit_tanggal_waktu, edit_kode_bahan, edit_warna, edit_stok, edit_yard, edit_keterangan):
                                        st.success("Data berhasil diperbarui! ✅")
                                        st.rerun()
                                    else:
                                        st.error("Gagal memperbarui data.")
                                except ValueError:
                                    st.error("Stok dan Yard harus berupa angka. Gagal menyimpan perubahan.")
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
    st.title("Transaksi Keluar (Penjualan) & Invoice 🧾")
    st.markdown("---")
    
    tab_new_invoice, tab_history = st.tabs(["➕ Buat Transaksi & Invoice Baru", "📝 Riwayat Transaksi"])
    
    master_df = get_master_barang()
    if master_df.empty:
        st.warning("Belum ada master barang. Silakan tambahkan di menu Master Barang. ⚠️")
        return

    # PERBAIKAN: Pastikan kolom adalah string sebelum digabungkan
    master_df['display_name'] = master_df['kode_bahan'].astype(str) + ' - ' + master_df['nama_bahan'].astype(str) + ' (' + master_df['warna'].astype(str) + ')'
    item_options = master_df['display_name'].tolist()

    if 'cart_items' not in st.session_state:
        st.session_state['cart_items'] = []
    
    with tab_new_invoice:
        st.subheader("Formulir Transaksi Penjualan")

        # Use a separate container for adding items
        with st.container(border=True):
            with st.form("add_item_form"):
                col_item_select, col_add_btn = st.columns([0.8, 0.2])
                with col_item_select:
                    item_to_add_str = st.selectbox("Pilih Item yang Akan Dijual", item_options, key="item_add_select")
                with col_add_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    add_item_submitted = st.form_submit_button("➕ Tambah Item")
                
                if add_item_submitted:
                    selected_item_data = master_df[master_df['display_name'] == item_to_add_str].iloc[0]
                    harga_cleaned = float(selected_item_data['harga']) if pd.notna(selected_item_data['harga']) else 0.0
                    new_item = {
                        "kode_bahan": selected_item_data['kode_bahan'],
                        "nama_bahan": selected_item_data['nama_bahan'],
                        "warna": selected_item_data['warna'],
                        "harga": harga_cleaned,
                        "qty": 0,
                        "yard": 0.0,
                        "keterangan": ""
                    }
                    st.session_state['cart_items'].append(new_item)
                    st.rerun()

        st.subheader("Keranjang Belanja 🛒")
        
        # PERBAIKAN: Move delete button logic outside the form
        if 'cart_items' in st.session_state:
            for i, item in enumerate(st.session_state['cart_items']):
                with st.container(border=True):
                    col_item_display, col_delete_btn = st.columns([0.9, 0.1])
                    
                    with col_item_display:
                        st.markdown(f"**Item {i+1}:** `{item['nama_bahan']} ({item['warna']})`")
                    
                    with col_delete_btn:
                        if st.button("🗑️", key=f"delete_btn_{i}"):
                            st.session_state['cart_items'].pop(i)
                            st.rerun()

        # The main transaction form
        with st.form("new_transaction_form"):
            customer_name = st.text_input("Nama Pelanggan", help="Wajib diisi", key="customer_name")
            
            total_invoice = 0
            if 'cart_items' in st.session_state:
                for i, item in enumerate(st.session_state['cart_items']):
                    with st.container(border=True):
                        st.markdown(f"**Item {i+1}:** `{item['nama_bahan']} ({item['warna']})`")
                        stok_saat_ini = get_stock_balance(item['kode_bahan'], item['warna'])
                        
                        col_qty, col_yard = st.columns(2)
                        with col_qty:
                            # PERBAIKAN: Menggunakan st.text_input dan mengonversi ke int
                            current_qty = int(st.session_state.cart_items[i].get('qty', 0))
                            qty_str = st.text_input(
                                "Jumlah",
                                value=str(current_qty),
                                key=f"qty_str_{i}",
                                help="Masukkan angka"
                            )
                            try:
                                qty = int(qty_str)
                                st.session_state.cart_items[i]['qty'] = qty
                            except ValueError:
                                st.error(f"Jumlah untuk item {i+1} harus berupa angka. Menggunakan nilai 0.")
                                st.session_state.cart_items[i]['qty'] = 0
                        
                        with col_yard:
                            # PERBAIKAN: Menggunakan st.text_input dan mengonversi ke float
                            current_yard = float(st.session_state.cart_items[i].get('yard', 0.0))
                            yard_str = st.text_input(
                                "Yard",
                                value=str(current_yard),
                                key=f"yard_str_{i}",
                                help="Masukkan angka (desimal)"
                            )
                            try:
                                yard = float(yard_str)
                                st.session_state.cart_items[i]['yard'] = yard
                            except ValueError:
                                st.error(f"Yard untuk item {i+1} harus berupa angka. Menggunakan nilai 0.0.")
                                st.session_state.cart_items[i]['yard'] = 0.0
                        
                        current_keterangan = str(st.session_state.cart_items[i].get('keterangan', ''))
                        st.session_state.cart_items[i]['keterangan'] = st.text_area(f"Keterangan (opsional)", value=current_keterangan, key=f"keterangan_{i}")
                        
                        current_item_total = st.session_state.cart_items[i]['qty'] * st.session_state.cart_items[i]['harga']
                        st.session_state.cart_items[i]['total'] = current_item_total
                        total_invoice += current_item_total
                        
                        st.markdown(f"**Harga Satuan:** Rp {st.session_state.cart_items[i]['harga']:,.2f}")
                        st.markdown(f"**Total Harga Item:** Rp {current_item_total:,.2f}")
                
            st.markdown(f"### **Total Keseluruhan:** **Rp {total_invoice:,.2f}**")
            
            submitted = st.form_submit_button("💾 Simpan Transaksi & Buat Invoice")
            if submitted:
                if not customer_name:
                    st.error("Nama Pelanggan wajib diisi.")
                elif not st.session_state['cart_items'] or all(item['qty'] == 0 for item in st.session_state['cart_items']):
                    st.error("Mohon tambahkan setidaknya satu item dengan jumlah lebih dari 0.")
                else:
                    new_invoice_number = generate_invoice_number()
                    success, message = add_barang_keluar_and_invoice(new_invoice_number, customer_name, st.session_state['cart_items'])
                    if success:
                        st.success(f"{message} Nomor Invoice: **{new_invoice_number}** ✅")
                        st.balloons()
                        st.session_state['cart_items'] = [] # Reset cart
                        st.rerun()
                    else:
                        st.error(message + " ❌")
                        
    with tab_history:
        st.subheader("Riwayat Transaksi")
        invoices_df = get_invoices()
        if not invoices_df.empty:
            invoices_df['tanggal_waktu'] = pd.to_datetime(invoices_df['tanggal_waktu']).dt.strftime('%Y-%m-%d %H:%M:%S')
            invoices_df.rename(columns={'invoice_number': 'No Invoice', 'tanggal_waktu': 'Tanggal & Waktu', 'customer_name': 'Nama Pelanggan'}, inplace=True)
            
            st.dataframe(invoices_df, use_container_width=True, hide_index=True)
            
            selected_invoice = st.selectbox("Pilih No Invoice untuk Dilihat/Unduh", invoices_df['No Invoice'].tolist())
            
            if st.button("Tampilkan & Unduh Invoice"):
                invoice_data = invoices_df[invoices_df['No Invoice'] == selected_invoice].iloc[0]
                invoice_items_df = get_invoice_items(selected_invoice)

                st.subheader(f"Detail Invoice: {selected_invoice}")
                st.write(f"**Nama Pelanggan:** {invoice_data['Nama Pelanggan']}")
                st.write(f"**Tanggal:** {invoice_data['Tanggal & Waktu']}")
                st.dataframe(invoice_items_df[['nama_bahan', 'qty', 'harga', 'total']].rename(columns={
                    'nama_bahan': 'Nama Bahan',
                    'qty': 'Qty',
                    'harga': 'Harga',
                    'total': 'Total'
                }), use_container_width=True, hide_index=True)

                pdf_file = generate_invoice_pdf(invoice_data, invoice_items_df)
                st.download_button(
                    label="Unduh Invoice PDF 📥",
                    data=pdf_file,
                    file_name=f"invoice_{selected_invoice}.pdf",
                    mime="application/pdf"
                )
        else:
            st.info("Belum ada riwayat transaksi.")

def show_monitoring_stok():
    st.title("Monitoring Stok 📊")
    st.markdown("---")
    
    st.subheader("Stok Saat Ini")
    master_df = get_master_barang()
    if not master_df.empty:
        master_df['Stok Saat Ini'] = master_df.apply(lambda row: get_stock_balance(row['kode_bahan'], row['warna']), axis=1)
        df_display = master_df[['kode_bahan', 'nama_bahan', 'warna', 'Stok Saat Ini']].copy()
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning("Belum ada master barang.")

    st.markdown("---")
    st.header("Rekam Jejak Stok (In & Out)")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Tanggal Mulai", value=datetime.now().date())
    with col2:
        end_date = st.date_input("Tanggal Selesai", value=datetime.now().date())
        
    if st.button("Tampilkan Rekam Jejak"):
        records_df = get_in_out_records(start_date, end_date)
        if not records_df.empty:
            st.dataframe(records_df, use_container_width=True, hide_index=True)
        else:
            st.info("Tidak ada catatan stok masuk atau keluar pada rentang tanggal tersebut.")

def show_payroll_page():
    st.title("Sistem Penggajian Karyawan 💰")
    st.markdown("---")
    
    tab_master, tab_process, tab_history = st.tabs(["👥 Master Karyawan", "💸 Proses Penggajian", "📝 Riwayat Penggajian"])

    with tab_master:
        st.subheader("Data Master Karyawan")
        
        with st.expander("➕ Tambah Karyawan Baru", expanded=False):
            with st.form("add_employee_form"):
                col1, col2 = st.columns(2)
                with col1:
                    nama = st.text_input("Nama Karyawan")
                with col2:
                    bagian = st.text_input("Bagian")
                # PERBAIKAN: Menggunakan st.text_input dan mengonversi ke float
                gaji_str = st.text_input("Gaji Pokok", value="0.0", help="Masukkan angka")
                
                submitted = st.form_submit_button("Tambah Karyawan")
                if submitted:
                    try:
                        gaji = float(gaji_str)
                        if nama and bagian and gaji > 0:
                            if add_employee(nama, bagian, gaji):
                                st.success(f"Karyawan {nama} berhasil ditambahkan. ✅")
                                st.rerun()
                            else:
                                st.error("Gagal menambahkan karyawan. Nama karyawan mungkin sudah ada.")
                        else:
                            st.error("Semua field wajib diisi. ❌")
                    except ValueError:
                        st.error("Gaji harus berupa angka. ❌")

        st.markdown("---")
        st.subheader("Daftar Karyawan")
        employees_df_master = get_employees()
        
        # Perbaikan: Selalu tampilkan dataframe, meskipun kosong
        st.dataframe(employees_df_master, use_container_width=True, hide_index=True)

        st.markdown("---")
        with st.expander("Kelola Data Karyawan"):
            # Perbaikan: Hanya tampilkan opsi kelola jika ada karyawan
            if not employees_df_master.empty:
                selected_employee_name = st.selectbox("Pilih Nama Karyawan", employees_df_master['nama_karyawan'].tolist(), key='master_edit_select')
                
                selected_row = employees_df_master[employees_df_master['nama_karyawan'] == selected_employee_name].iloc[0]
                
                with st.form("edit_employee_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        edit_nama = st.text_input("Nama", value=selected_row['nama_karyawan'])
                    with col2:
                        edit_bagian = st.text_input("Bagian", value=selected_row['bagian'])
                    
                    # Perbaikan: Menggunakan st.text_input
                    gaji_pokok_value = float(selected_row['gaji_pokok']) if pd.notna(selected_row['gaji_pokok']) else 0.0
                    edit_gaji_str = st.text_input("Gaji Pokok", value=str(gaji_pokok_value))
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.form_submit_button("Simpan Perubahan"):
                            try:
                                edit_gaji = float(edit_gaji_str)
                                if update_employee(selected_employee_name, edit_nama, edit_bagian, edit_gaji):
                                    st.success("Data karyawan berhasil diperbarui! ✅")
                                    st.rerun()
                                else:
                                    st.error("Gagal memperbarui data. Nama karyawan mungkin sudah ada.")
                            except ValueError:
                                st.error("Gaji harus berupa angka. Gagal menyimpan perubahan.")
                    with col_btn2:
                        if st.form_submit_button("Hapus Karyawan"):
                            if delete_employee(selected_employee_name):
                                st.success("Karyawan berhasil dihapus. 🗑️")
                                st.rerun()
                            else:
                                st.error("Gagal menghapus karyawan.")
            else:
                st.info("Belum ada data karyawan untuk dikelola.")

    with tab_process:
        st.subheader("Proses Penggajian Bulanan")
        employees_df = get_employees()
        if employees_df.empty:
            st.warning("Tambahkan data karyawan terlebih dahulu di tab 'Master Karyawan'. ⚠️")
        else:
            # Gsheets doesn't have an ID column by default. We'll simulate it for this session.
            employees_df['id'] = range(1, len(employees_df) + 1)
            employee_options = employees_df.apply(lambda row: f"{int(row['id'])} - {row['nama_karyawan']} ({row['bagian']})", axis=1).tolist()
            selected_employee_str = st.selectbox("Pilih Karyawan", employee_options)
            
            if selected_employee_str:
                employee_id = int(selected_employee_str.split(' - ')[0])
                selected_employee_data = employees_df[employees_df['id'] == employee_id].iloc[0]
                
                with st.form("payroll_form"):
                    st.write(f"**Nama:** {selected_employee_data['nama_karyawan']}")
                    st.write(f"**Bagian:** {selected_employee_data['bagian']}")

                    selected_date = st.date_input("Pilih Tanggal Gaji", value=datetime.now().date())
                    gaji_bulan = selected_date.strftime('%B %Y')
                    
                    st.markdown("### Pendapatan")
                    st.text_input("Gaji Pokok", value=str(selected_employee_data['gaji_pokok']), disabled=True)
                    lembur_str = st.text_input("Lembur", value="0.0")
                    lembur_minggu_str = st.text_input("Lembur Minggu", value="0.0")
                    uang_makan_str = st.text_input("Uang Makan", value="0.0")
                    
                    # Konversi dan hitung
                    try:
                        lembur = float(lembur_str)
                        lembur_minggu = float(lembur_minggu_str)
                        uang_makan = float(uang_makan_str)
                        total_pendapatan = selected_employee_data['gaji_pokok'] + lembur + lembur_minggu + uang_makan
                    except ValueError:
                        st.error("Masukkan angka yang valid untuk perhitungan gaji. ❌")
                        total_pendapatan = 0
                    
                    st.markdown(f"**Total Pendapatan (1):** **Rp {total_pendapatan:,.2f}**")
                    
                    st.markdown("### Potongan")
                    pot_absen_finger_str = st.text_input("Potongan Absen Finger", value="0.0")
                    ijin_hr_str = st.text_input("Ijin HR", value="0.0")
                    
                    # Konversi dan hitung
                    try:
                        pot_absen_finger = float(pot_absen_finger_str)
                        ijin_hr = float(ijin_hr_str)
                        total_setelah_potongan1 = total_pendapatan - pot_absen_finger - ijin_hr
                    except ValueError:
                        st.error("Masukkan angka yang valid untuk potongan. ❌")
                        total_setelah_potongan1 = total_pendapatan

                    st.markdown(f"**Total Setelah Potongan Absen (2):** **Rp {total_setelah_potongan1:,.2f}**")
                    
                    st.markdown("### Potongan Lain-lain")
                    simpanan_wajib_str = st.text_input("Simpanan Wajib", value="0.0")
                    potongan_koperasi_str = st.text_input("Potongan Koperasi", value="0.0")
                    kasbon_str = st.text_input("Kasbon", value="0.0")

                    # Konversi dan hitung
                    try:
                        simpanan_wajib = float(simpanan_wajib_str)
                        potongan_koperasi = float(potongan_koperasi_str)
                        kasbon = float(kasbon_str)
                        gaji_akhir = total_setelah_potongan1 - simpanan_wajib - potongan_koperasi - kasbon
                    except ValueError:
                        st.error("Masukkan angka yang valid untuk potongan lain-lain. ❌")
                        gaji_akhir = total_setelah_potongan1

                    st.markdown(f"### **TOTAL GAJI AKHIR:** **Rp {gaji_akhir:,.2f}**")
                    
                    keterangan = st.text_area("Keterangan", help="Opsional")
                    
                    submitted = st.form_submit_button("💾 Simpan Gaji")
                    if submitted:
                        if add_payroll_record(employee_id, gaji_bulan, selected_employee_data['gaji_pokok'], lembur, lembur_minggu, uang_makan, pot_absen_finger, ijin_hr, simpanan_wajib, potongan_koperasi, kasbon, gaji_akhir, keterangan):
                            st.success(f"Penggajian untuk {selected_employee_data['nama_karyawan']} berhasil dicatat. ✅")
                            st.rerun()
                        else:
                            st.error("Gagal menyimpan data gaji.")

    with tab_history:
        st.subheader("Riwayat Penggajian")
        
        st.markdown("### Unduh Semua Slip Gaji (PDF)")
        payroll_df_all = get_data_from_gsheets('payroll')
        if not payroll_df_all.empty:
            payroll_months = payroll_df_all['gaji_bulan'].unique().tolist()
            selected_month = st.selectbox("Pilih Bulan Gaji", payroll_months)
            
            if st.button(f"Unduh Slip Gaji {selected_month}"):
                payslip_data = get_payroll_records_by_month(selected_month)
                if not payslip_data.empty:
                    pdf_file = generate_payslips_pdf(payslip_data)
                    st.download_button(
                        label="Unduh PDF 📥",
                        data=pdf_file,
                        file_name=f"slip_gaji_{selected_month.replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.error("Data penggajian tidak ditemukan untuk bulan tersebut. ❌")
        else:
            st.info("Tidak ada riwayat penggajian untuk diunduh.")

        st.markdown("---")
        st.subheader("Tabel Riwayat Penggajian")
        payroll_df = get_payroll_records()
        if not payroll_df.empty:
            month_mapping = {
                'January': 'Januari', 'February': 'Februari', 'March': 'Maret',
                'April': 'April', 'May': 'Mei', 'June': 'Juni',
                'July': 'Juli', 'August': 'Agustus', 'September': 'September',
                'October': 'Oktober', 'November': 'November', 'December': 'Desember'
            }
            
            payroll_df['tanggal_waktu'] = pd.to_datetime(payroll_df['tanggal_waktu'])
            payroll_df['tanggal_waktu'] = payroll_df['tanggal_waktu'].dt.strftime('%d %B %Y')
            
            for en, idn in month_mapping.items():
                payroll_df['tanggal_waktu'] = payroll_df['tanggal_waktu'].str.replace(en, idn)
            
            st.dataframe(payroll_df, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada riwayat penggajian.")

# --- Login & Main App Logic ---
def login_page():
    st.title("Login Sistem Kontrol Stok")
    with st.form("login_form"):
        st.subheader("Silakan Masuk")
        username = st.text_input("Nama Pengguna")
        password = st.text_input("Kata Sandi", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if check_login(username, password):
                st.session_state['logged_in'] = True
                st.session_state['page'] = 'Dashboard'
                st.success("Berhasil Login! ✅")
                st.rerun()
            else:
                st.error("Nama pengguna atau kata sandi salah. ❌")

def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['page'] = 'Login'
    
    st.sidebar.title("PT. BERKAT KARYA ANUGERAH")
    st.sidebar.markdown("---")

    if st.session_state['logged_in']:
        if 'sheets_checked' not in st.session_state:
            check_and_create_worksheets()
            st.session_state['sheets_checked'] = True

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
    else:
        login_page()

if __name__ == "__main__":
    main()
