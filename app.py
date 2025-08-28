import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import bcrypt
import streamlit.components.v1 as components # Import for custom HTML/JS

# --- Page Configuration ---
st.set_page_config(
    page_title="PT. BERKAT KARYA ANUGERAH",
    page_icon="📝",
    layout="wide"
)

# --- Google Sheet Configuration ---
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

key_dict = st.secrets["gcp_service_account"]
creds = Credentials.from_service_account_info(key_dict, scopes=scope)
SHEET_ID = "183qGysrbVVHwkNIxwtemTy0khx7eZw5jw0lreis_GLw"

@st.cache_resource(ttl=3600) # Cache connection for 1 hour (3600 seconds)
def get_google_sheet_client(sheet_id):
    try:
        client = gspread.authorize(creds)
        sheet_user_obj = client.open_by_key(sheet_id).worksheet("user")
        sheet_presensi_obj = client.open_by_key(sheet_id).worksheet("presensi")
        sheet_audit_log_obj = client.open_by_key(sheet_id).worksheet("audit_log")
        # NEW: Areas sheet
        sheet_areas_obj = client.open_by_key(sheet_id).worksheet("areas")

        return client, sheet_user_obj.title, sheet_presensi_obj.title, sheet_audit_log_obj.title, sheet_areas_obj.title
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(
            "**Error:** Spreadsheet not found. "
            "Please double-check the `SHEET_ID` in your code. "
            "Also, ensure your service account (email in credential) has Editor access to this Google Sheet."
        )
        st.stop()
    except gspread.exceptions.WorksheetNotFound as e:
        # Simplified error message to prevent IndexError
        st.error(
            f"**Error:** Worksheet not found: {e.args[0]}. "
            "Please ensure all required worksheets (user, presensi, audit_log, areas) exist in your Google Sheet."
        )
        st.stop()
    except Exception as e:
        st.error(f"**Google Sheets connection error:** {e}. "
                 "Please check your internet connection or Google API status."
                 "If it's a 503 error, try refreshing the app in a few moments.")
        st.stop()

client, sheet_user_title, sheet_presensi_title, sheet_audit_log_title, sheet_areas_title = get_google_sheet_client(SHEET_ID)


@st.cache_data(ttl=600) # Cache data for 10 minutes (600 seconds)
def get_data_from_sheet(spreadsheet_id, worksheet_title):
    try:
        worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_title)
        df = pd.DataFrame(worksheet.get_all_records())
        
        # --- Robustness check for crucial columns ---
        if worksheet_title == sheet_presensi_title:
            required_presensi_cols = ['Id', 'Date', 'Hours', 'Overtime', 'Area 1', 'Shift']
            for col in required_presensi_cols:
                if col not in df.columns:
                    st.warning(f"Kolom '{col}' tidak ditemukan di sheet '{worksheet_title}'. Pastikan header sudah benar.")
                    # If 'Id' is missing from presensi sheet, subsequent operations will fail.
                    # It's better to explicitly check and return an empty DataFrame or halt.
                    if col == 'Id': # Added specific check for 'Id' as it's critical for filtering
                         st.error("Error fatal: Kolom 'Id' tidak ditemukan di Google Sheet 'presensi'. Harap perbaiki header sheet Anda.")
                         return pd.DataFrame() # Return empty to prevent further errors
        
        if worksheet_title == sheet_audit_log_title:
            required_audit_cols = ["Timestamp", "User ID", "Username", "Action", "Description", "Status"]
            for col in required_audit_cols:
                if col not in df.columns:
                    st.warning(f"Audit log column '{col}' not found. Please ensure your 'audit_log' Google Sheet has the correct headers.")
        
        # NEW: Areas sheet column check
        if worksheet_title == sheet_areas_title:
            required_area_cols = ["AreaName"]
            for col in required_area_cols:
                if col not in df.columns:
                    st.warning(f"Area sheet column '{col}' not found. Please ensure your 'areas' Google Sheet has the correct header ('AreaName').")
                    # Return empty df if critical column is missing for areas to avoid errors
                    return pd.DataFrame()

        if 'Password' in df.columns:
            df['Password'] = df['Password'].astype(str).str.strip() # Strip whitespace
        # Convert 'Number of Areas' to int, handle potential missing column or non-numeric
        if 'Number of Areas' in df.columns:
            df['Number of Areas'] = pd.to_numeric(df['Number of Areas'], errors='coerce').fillna(1).astype(int)
        return df
    except Exception as e:
        st.error(f"Error fetching data from sheet '{worksheet_title}': {e}")
        return pd.DataFrame()


# --- Helper Functions ---
def check_login(user_id, password):
    df_users = get_data_from_sheet(SHEET_ID, sheet_user_title)

    user_row = df_users[df_users['Id'].astype(str) == str(user_id)]

    if user_row.empty:
        return None

    password_bytes = password.encode('utf-8')

    stored_password_value = str(user_row.iloc[0]['Password']).strip()
    stored_hash_bytes = stored_password_value.encode('utf-8')

    if stored_hash_bytes.startswith(b'$2a$') or stored_hash_bytes.startswith(b'$2b$') or stored_hash_bytes.startswith(b'$2y$'):
        try:
            if bcrypt.checkpw(password_bytes, stored_hash_bytes):
                return user_row.iloc[0]
            else:
                return None
        except ValueError:
            st.warning("Invalid hash format detected for existing password. Please contact support.")
            return None
    else:
        if password == stored_password_value:
            return user_row.iloc[0]
        else:
            return None


def get_day_name(date_obj):
    return date_obj.strftime("%A")

def get_date_range(start, end):
    return pd.date_range(start=start, end=end).to_list()

# --- Functions for User Settings ---
def update_user_data_in_sheet(user_id, column_name, new_value):
    """Updates a specific column for a user in the 'user' Google Sheet."""
    sheet_user_actual = client.open_by_key(SHEET_ID).worksheet(sheet_user_title)

    df_users = pd.DataFrame(sheet_user_actual.get_all_records())

    try:
        df_row_index = df_users[df_users['Id'].astype(str) == str(user_id)].index[0]

        header = sheet_user_actual.row_values(1)
        if column_name not in header:
            st.error(f"Error: Column '{column_name}' not found in 'user' sheet headers. Please add this column to your 'user' Google Sheet.")
            return False

        col_index = header.index(column_name) + 1
        gsheet_row = df_row_index + 2

        if column_name == "Password":
            new_value_bytes = str(new_value).encode('utf-8')
            hashed_password = bcrypt.hashpw(new_value_bytes, bcrypt.gensalt()).decode('utf-8')
            sheet_user_actual.update_cell(gsheet_row, col_index, hashed_password)
        else:
            sheet_user_actual.update_cell(gsheet_row, col_index, new_value)

        get_data_from_sheet.clear()
        return True
    except IndexError:
        st.error(f"User with ID {user_id} not found in the 'user' sheet.")
        return False
    except Exception as e:
        st.error(f"Failed to update {column_name}: {e}")
        return False

def log_audit_event(user_id, username, action, description, status="Success"):
    """Logs an audit event to the 'audit_log' Google Sheet."""
    try:
        sheet_audit_log_actual = client.open_by_key(SHEET_ID).worksheet(sheet_audit_log_title)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = [timestamp, user_id, username, action, description, status]
        sheet_audit_log_actual.append_row(log_entry)
        get_data_from_sheet.clear()
    except Exception as e:
        st.error(f"Error logging audit event: {e}")

# NEW: Function to add an area
def add_area_to_sheet(area_name):
    """Adds a new area to the 'areas' Google Sheet."""
    try:
        sheet_areas_actual = client.open_by_key(SHEET_ID).worksheet(sheet_areas_title)
        
        # Fetch current areas to check for duplicates (case-insensitive)
        df_areas = get_data_from_sheet(SHEET_ID, sheet_areas_title)
        if not df_areas.empty and 'AreaName' in df_areas.columns:
            existing_areas_lower = df_areas['AreaName'].astype(str).str.strip().str.lower().tolist()
            if area_name.strip().lower() in existing_areas_lower:
                st.warning(f"Area '{area_name.strip()}' sudah ada.")
                return False
        
        sheet_areas_actual.append_row([area_name.strip()])
        get_data_from_sheet.clear() # Clear cache to refetch new data
        st.success(f"Area '{area_name.strip()}' berhasil ditambahkan.")
        return True
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Worksheet '{sheet_areas_title}' tidak ditemukan. Harap buat worksheet bernama '{sheet_areas_title}' dengan header 'AreaName'.")
        return False
    except Exception as e:
        st.error(f"Error menambahkan area: {e}")
        return False

# NEW: Function to delete an area
def delete_area_from_sheet(area_name):
    """Deletes an area from the 'areas' Google Sheet."""
    try:
        sheet_areas_actual = client.open_by_key(SHEET_ID).worksheet(sheet_areas_title)
        df_areas = get_data_from_sheet(SHEET_ID, sheet_areas_title)

        if df_areas.empty or 'AreaName' not in df_areas.columns:
            st.warning("Tidak ada data area untuk dihapus atau kolom 'AreaName' tidak ditemukan.")
            return False

        # Find row index (gspread is 1-indexed, headers are row 1)
        row_to_delete_idx = -1
        for i, val in enumerate(sheet_areas_actual.col_values(1)): # Assuming AreaName is in column 1
            if val.strip() == area_name.strip():
                row_to_delete_idx = i + 1 # Convert to 1-based index
                break
        
        if row_to_delete_idx != -1 and row_to_delete_idx > 1: # Ensure not header row
            sheet_areas_actual.delete_rows(row_to_delete_idx)
            get_data_from_sheet.clear() # Clear cache to refetch new data
            st.success(f"Area '{area_name.strip()}' berhasil dihapus.")
            return True
        else:
            st.warning(f"Area '{area_name.strip()}' tidak ditemukan.")
            return False
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Worksheet '{sheet_areas_title}' tidak ditemukan.")
        return False
    except Exception as e:
        st.error(f"Error menghapus area: {e}")
        return False


# --- NEW: Function to copy text to clipboard ---
def copy_to_clipboard_button(text_to_copy, button_label="Salin ke Clipboard"):
    """
    Menampilkan tombol yang menyalin teks ke clipboard saat diklik.
    """
    # JavaScript untuk menyalin teks ke clipboard
    # Perhatikan penggantian karakter khusus untuk keamanan JavaScript string
    escaped_text = text_to_copy.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r")

    js_code = f"""
    <script>
    function copyTextToClipboard(text) {{
        navigator.clipboard.writeText(text).then(function() {{
            alert('Teks berhasil disalin!');
        }}).catch(function(err) {{
            console.error('Tidak dapat menyalin teks: ', err);
            alert('Gagal menyalin teks. Pastikan browser Anda mengizinkan akses clipboard dan coba lagi.');
        }});
    }}
    </script>
    <button onclick="copyTextToClipboard('{escaped_text}')" style="
        background-color: #4CAF50; /* Green */
        border: none;
        color: white;
        padding: 10px 20px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 8px;
    ">{button_label}</button>
    """
    components.html(js_code, height=50) # height bisa disesuaikan

# --- Session State for Login ---
if "user" not in st.session_state:
    st.session_state.user = None
if "logged_out_after_password_change" not in st.session_state:
    st.session_state.logged_out_after_password_change = False


# --- App Title ---
st.image("logo login.png", width=250)

# --- Login Section ---
if st.session_state.user is None:
    st.subheader("🔐 Login to Access Timesheet")

    if st.session_state.logged_out_after_password_change:
        st.info("Your password has been changed. Please log in with your new password.")
        st.session_state.logged_out_after_password_change = False

    user_id = st.text_input("User ID")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = check_login(user_id, password)
        if user is not None:
            st.session_state.user = user
            st.success("Login successful!")
            log_audit_event(user_id, user["Username"], "Login", "Successful login.")
            st.rerun()
        else:
            st.error("❌ Incorrect User ID or Password")
            log_audit_event(user_id, "N/A", "Login", "Failed login attempt (incorrect credentials).", "Failed")
    st.stop()


# --- Sidebar Info Area ---
st.sidebar.title("📍 Info Area")
st.sidebar.write("👤 Logged in as:", st.session_state.user["Username"])
st.sidebar.write("💼 Role:", st.session_state.user["Role"])
st.sidebar.write("🎓 Grade:", st.session_state.user["Grade"])

st.sidebar.markdown("---")

st.sidebar.markdown("""
**Area Codes:**
- **CMN**: Common Area
- **GCP** / **SAP**: Acid Plant
- **ER**: Electro Refinery
- **ET**: ETP Effluent Treatment Plant
- **SC**: Slag Concentrate
- **SM**: Smelter
""")

if st.sidebar.button("Logout"):
    log_audit_event(st.session_state.user["Id"], st.session_state.user["Username"], "Logout", "User logged out.")
    st.session_state.user = None
    st.session_state.logged_out_after_password_change = False
    st.rerun()

# --- Tab Layout ---
# Determine which tabs to show based on user role
allowed_roles_for_audit_log_tab = ["Site Admin", "Commissioning Director"]
show_audit_log_tab = st.session_state.user["Role"] in allowed_roles_for_audit_log_tab

allowed_roles_for_master_edit_tab = ["Site Admin"] # Only Site Admin for Master Edit
show_master_edit_tab = st.session_state.user["Role"] in allowed_roles_for_master_edit_tab


all_possible_tabs_names = ["📝 Timesheet Form", "📊 Activity Log"]
if show_audit_log_tab:
    all_possible_tabs_names.append("🔍 Audit Log")
if show_master_edit_tab:
    all_possible_tabs_names.append("🛠️ Master Edit") # New tab for Master Edit
all_possible_tabs_names.append("⚙️ User Settings")

# Create tabs dynamically
tabs_objects = st.tabs(all_possible_tabs_names)

# Map tab names to their actual tab objects for consistent access
tab_map = {name: obj for name, obj in zip(all_possible_tabs_names, tabs_objects)}


# --- Timesheet Tab ---
with tab_map["📝 Timesheet Form"]:
    st.header("📝 Online Timesheet Form")
    today = datetime.today()

    col_start_date, col_end_date = st.columns(2)

    with col_start_date:
        start_date = st.date_input("Start Date", today - timedelta(days=6))

    with col_end_date:
        end_date = st.date_input("End Date", today)

    date_list = get_date_range(start_date, end_date)
    st.markdown(f"**Date Range:** {start_date.strftime('%d-%b-%Y')} ➜ {end_date.strftime('%d-%b-%Y')}")

    all_shift_opts = ["Day Shift", "Night Shift", "Noon Shift"]

    user_preferred_shift = st.session_state.user.get("Preferred Shift", "Day Shift")
    if user_preferred_shift not in all_shift_opts:
        user_preferred_shift = "Day Shift"

    shift_opts_ordered = [user_preferred_shift] + [s for s in all_shift_opts if s != user_preferred_shift]

    # NEW: Fetch areas from Google Sheet
    df_areas = get_data_from_sheet(SHEET_ID, sheet_areas_title)
    if not df_areas.empty and 'AreaName' in df_areas.columns:
        all_area_opts = df_areas['AreaName'].astype(str).tolist()
    else:
        # Fallback to hardcoded if sheet is empty or column missing
        all_area_opts = ["GCP", "ER", "ET", "SC", "SM", "SAP"]
        st.warning(f"Tidak dapat memuat daftar area dari sheet '{sheet_areas_title}'. Menggunakan daftar default.")


    user_preferred_areas_str = st.session_state.user.get("Preferred Areas", "")
    if user_preferred_areas_str:
        preferred_areas_list = [a.strip() for a in user_preferred_areas_str.split(',') if a.strip()]
        area_opts = [area for area in preferred_areas_list if area in all_area_opts]
        for area in all_area_opts:
            if area not in area_opts:
                area_opts.append(area)
    else:
        area_opts = all_area_opts

    initial_data = []
    for date in date_list:
        initial_data.append({
            "Date": date.strftime("%Y-%m-%d"),
            "Day": get_day_name(date),
            "Hours": 0.0,
            "Overtime": 0.0,
            "Area 1": area_opts[0] if area_opts else "",
            "Area 2": "",
            "Area 3": "",
            "Area 4": "",
            "Shift": user_preferred_shift,
            "Remark": ""
        })

    df_presensi_input = pd.DataFrame(initial_data)

    st.subheader("Enter Timesheet Details")

    # --- START OF CHANGE FOR DYNAMIC AREA COLUMNS ---
    # Get user's preferred number of area columns, default to 1 if not set or invalid
    num_area_cols_preference = int(st.session_state.user.get("Number of Areas", 1))
    if num_area_cols_preference < 1 or num_area_cols_preference > 4:
        num_area_cols_preference = 1 # Fallback to 1 if outside valid range

    # Define column configurations for data_editor
    column_configs = {
        "Date": st.column_config.Column("Date", help="Date of timesheet entry", disabled=True),
        "Day": st.column_config.Column("Day", help="Day of the week", disabled=True),
        "Hours": st.column_config.NumberColumn("Working Hours", min_value=0.0, max_value=24.0, step=0.5, format="%.1f", help="Total working hours (0-24 hours)"),
        "Overtime": st.column_config.NumberColumn("Overtime Hours", min_value=0.0, max_value=24.0, step=0.5, format="%.1f", help="Total overtime hours (0-24 hours)"),
        "Area 1": st.column_config.SelectboxColumn("Area 1", options=area_opts, required=True, default=area_opts[0] if area_opts else ""),
        "Area 2": st.column_config.SelectboxColumn("Area 2", options=[""] + area_opts, required=False, default="", help="Additional work area (optional)"),
        "Area 3": st.column_config.SelectboxColumn("Area 3", options=[""] + area_opts, required=False, default="", help="Additional work area (optional)"),
        "Area 4": st.column_config.SelectboxColumn("Area 4", options=[""] + area_opts, required=False, default="", help="Additional work area (optional)"),
        "Shift": st.column_config.SelectboxColumn("Shift", options=shift_opts_ordered, required=True, default=user_preferred_shift),
        "Remark": st.column_config.TextColumn("Remarks", help="E.g., Day off / Travel"),
    }

    # Dynamically build column_order based on preference
    column_order = ["Date", "Day", "Hours", "Overtime", "Area 1"]
    for i in range(2, num_area_cols_preference + 1):
        column_order.append(f"Area {i}")
    column_order.extend(["Shift", "Remark"])

    edited_df = st.data_editor(
        df_presensi_input,
        column_config=column_configs,
        column_order=column_order, # Use the dynamically built order
        hide_index=True,
        num_rows="fixed",
        use_container_width=True
    )
    # --- END OF CHANGE FOR DYNAMIC AREA COLUMNS ---

    if st.button("📤 Submit Timesheet"):
        final_data_to_submit = []
        duplicate_entries_found = []
        validation_errors = []

        get_data_from_sheet.clear()
        df_existing_presensi = get_data_from_sheet(SHEET_ID, sheet_presensi_title)

        # Check if df_existing_presensi is empty or crucial columns are missing before proceeding
        if df_existing_presensi.empty:
            st.info("Tidak ada data timesheet yang ada di Google Sheet untuk perbandingan duplikat.")
        elif 'Id' not in df_existing_presensi.columns:
            st.error("Error: Kolom 'Id' tidak ditemukan di data presensi yang ada. Pastikan header di Google Sheet 'presensi' sudah benar.")
            validation_errors.append("Critical Error: Missing 'Id' column in existing timesheet data.")
        elif 'Date' not in df_existing_presensi.columns:
            st.error("Error: Kolom 'Date' tidak ditemukan di data presensi yang ada. Pastikan header di Google Sheet 'presensi' sudah benar.")
            validation_errors.append("Critical Error: Missing 'Date' column in existing timesheet data.")

        current_user_id = st.session_state.user["Id"]
        current_username = st.session_state.user["Username"]

        if not validation_errors: # Only proceed if no critical column errors
            for index, row in edited_df.iterrows():
                entry_date_str = row["Date"]

                hours = 0.0
                overtime = 0.0
                try:
                    hours = float(row["Hours"])
                    overtime = float(row["Overtime"])
                    if hours < 0 or overtime < 0:
                        validation_errors.append(f"Hours or Overtime cannot be negative on Date: **{entry_date_str}**.")
                except ValueError:
                    validation_errors.append(f"Invalid numeric input for Hours or Overtime on Date: **{entry_date_str}**.")

                if (hours + overtime) > 24.01:
                    validation_errors.append(f"Total hours (Working Hours + Overtime) on Date: **{entry_date_str}** exceeds 24 hours. Please correct.")

                if not row["Area 1"] or str(row["Area 1"]).strip() == "":
                    validation_errors.append(f"**Area 1** cannot be empty on Date: **{entry_date_str}**.")

                # Only check for duplicates if df_existing_presensi is not empty and has required columns
                is_duplicate = False
                if not df_existing_presensi.empty and 'Id' in df_existing_presensi.columns and 'Date' in df_existing_presensi.columns:
                    is_duplicate = df_existing_presensi[
                        (df_existing_presensi['Id'].astype(str) == str(current_user_id)) &
                        (df_existing_presensi['Date'].astype(str) == entry_date_str)
                    ].empty is False

                if is_duplicate:
                    duplicate_entries_found.append(entry_date_str)
                else:
                    entry = {
                        "Id": current_user_id,
                        "Username": st.session_state.user["Username"],
                        "Date": entry_date_str,
                        "Day": row["Day"],
                        "Hours": hours,
                        "Overtime": overtime,
                        "Area 1": row["Area 1"],
                        "Area 2": row["Area 2"],
                        "Area 3": row["Area 3"],
                        "Area 4": row["Area 4"],
                        "Shift": row["Shift"],
                        "Remark": row["Remark"],
                    }
                    final_data_to_submit.append([
                        entry["Id"], entry["Username"], entry["Date"], entry["Day"],
                        entry["Hours"], entry["Overtime"],
                        entry["Area 1"], entry["Area 2"], entry["Area 3"], entry["Area 4"],
                        entry["Shift"], entry["Remark"]
                    ])

        if validation_errors:
            for error in validation_errors:
                st.error(f"❗ Input Error: {error}")
            st.warning("Please correct the errors and resubmit.")
            log_audit_event(current_user_id, current_username, "Timesheet Submission",
                            f"Failed to submit timesheet for dates: {', '.join([row['Date'] for _, row in edited_df.iterrows()])} due to validation errors.",
                            "Failed")

        if duplicate_entries_found:
            st.error(f"❌ Submission Failed: Timesheet for the following dates already exists for user {current_user_id}: **{', '.join(duplicate_entries_found)}**. Please edit existing entries via Activity Log if needed.")
            log_audit_event(current_user_id, current_username, "Timesheet Submission",
                            f"Failed to submit timesheet for dates: {', '.join(duplicate_entries_found)} due to duplicate entries.",
                            "Failed")

        if not validation_errors and not duplicate_entries_found and final_data_to_submit:
            try:
                sheet_presensi_actual = client.open_by_key(SHEET_ID).worksheet(sheet_presensi_title)
                sheet_presensi_actual.append_rows(final_data_to_submit)
                get_data_from_sheet.clear()
                st.success("✅ Timesheet successfully submitted!")
                log_audit_event(current_user_id, current_username, "Timesheet Submission",
                                f"Successfully submitted timesheet for dates: {', '.join([entry[2] for entry in final_data_to_submit])}.")

                # --- NEW: "Klik me and paste to your email" feature ---
                st.subheader("Bagikan Konfirmasi Timesheet")
                summary_text = f"Halo,\n\nSaya, {current_username} (ID: {current_user_id}), telah berhasil mengisi timesheet untuk periode {start_date.strftime('%d-%b-%Y')} hingga {end_date.strftime('%d-%b-%Y')}.\n\nTotal entri baru: {len(final_data_to_submit)}.\n\nTerima kasih atas perhatiannya."

                st.text_area("Konten Konfirmasi untuk Dibagikan:", summary_text, height=150, disabled=True)
                
                col_copy, col_email = st.columns([0.3, 0.7])
                with col_copy:
                    copy_to_clipboard_button(summary_text, "Salin ke Clipboard")
                
                with col_email:
                    import urllib.parse
                    # Ganti dengan email penerima default yang sesuai (misal: supervisor atau HR)
                    recipient_email = "your.supervisor@example.com"
                    email_subject = f"Konfirmasi Timesheet {current_username} ({start_date.strftime('%d-%m-%Y')} - {end_date.strftime('%d-%m-%Y')})"
                    
                    encoded_subject = urllib.parse.quote(email_subject)
                    encoded_body = urllib.parse.quote(summary_text + "\n\n(Dikirim otomatis dari aplikasi timesheet)")
                    mailto_link = f"mailto:{recipient_email}?subject={encoded_subject}&body={encoded_body}"
                    
                    st.markdown(f"[Klik untuk Kirim Email Otomatis]({mailto_link})")
                    st.caption("Ini akan membuka aplikasi email default Anda dengan draf email yang sudah terisi.")
                # --- END NEW FEATURE ---

                st.rerun()
            except Exception as e:
                st.error(f"Error submitting timesheet: {e}")
                log_audit_event(current_user_id, current_username, "Timesheet Submission",
                                f"Failed to submit timesheet due to system error: {e}", "Failed")
        elif not final_data_to_submit and not validation_errors and not duplicate_entries_found:
            st.info("💡 No new timesheet entries to submit (all might be duplicates or zero rows).")
            log_audit_event(current_user_id, current_username, "Timesheet Submission",
                            "Attempted submission with no new entries (possibly all duplicates or empty range).", "Info")


# --- Activity Log Tab (For All Users) ---
with tab_map["📊 Activity Log"]:
    st.header("📊 All Users Activity Log")

    col_log_start, col_log_end = st.columns(2)

    with col_log_start:
        log_start_date = st.date_input("Log Start Date", datetime.today() - timedelta(days=7), key="all_log_start_date")

    with col_log_end:
        log_end_date = st.date_input("Log End Date", datetime.today(), key="all_log_end_date")

    df_log_all = get_data_from_sheet(SHEET_ID, sheet_presensi_title)

    df_filtered_all_log = pd.DataFrame() # Initialize empty DataFrame

    if 'Date' in df_log_all.columns:
        df_log_all['Date'] = pd.to_datetime(df_log_all['Date'], errors='coerce')
        df_filtered_all_log = df_log_all[(df_log_all['Date'] >= pd.to_datetime(log_start_date)) &
                                         (df_log_all['Date'] <= pd.to_datetime(log_end_date))]
    else:
        st.warning("Kolom 'Date' tidak ditemukan di sheet 'presensi' untuk filtering. Menampilkan semua data log yang tersedia.")
        df_filtered_all_log = df_log_all.copy()

    st.subheader("Filter Activity Log")
    col_filter_user, col_filter_shift, col_filter_area = st.columns(3)

    with col_filter_user:
        allowed_roles_for_all_users = ["Site Admin", "Commissioning Director"]
        is_admin_or_director = st.session_state.user["Role"] in allowed_roles_for_all_users

        if 'Username' in df_filtered_all_log.columns:
            all_usernames_options = sorted(df_filtered_all_log['Username'].unique().tolist())
        else:
            all_usernames_options = []
            st.warning("Kolom 'Username' tidak ditemukan di log aktivitas.")

        if is_admin_or_director:
            # Admins/Directors can see all users
            select_options = ["All"] + all_usernames_options
            default_index = 0 # Default to "All"
            selected_username = st.selectbox(
                "Filter by User",
                options=select_options,
                index=default_index,
                key="filter_user_admin" # Unique key
            )
        else:
            # Other users only see their own data
            current_user_username = st.session_state.user["Username"]
            select_options = [current_user_username]
            default_index = 0 # Only option is their own username
            selected_username = st.selectbox(
                "Filter by User",
                options=select_options,
                index=default_index,
                disabled=True, # Disable the selectbox
                key="filter_user_restricted" # Unique key
            )
            # The filtering logic below will automatically pick up current_user_username
            # because selected_username is set to it.

    with col_filter_shift:
        if 'Shift' in df_filtered_all_log.columns:
            all_shifts = ["All"] + sorted(df_filtered_all_log['Shift'].unique().tolist())
        else:
            all_shifts = ["All"]
            st.warning("Kolom 'Shift' tidak ditemukan di log aktivitas.")
        selected_shift = st.selectbox("Filter by Shift", all_shifts)

    with col_filter_area:
        all_areas_in_log = []
        for col_name in ["Area 1", "Area 2", "Area 3", "Area 4"]:
            if col_name in df_filtered_all_log.columns:
                all_areas_in_log.extend(df_filtered_all_log[col_name].dropna().unique().tolist())
        all_areas_in_log = ["All"] + sorted(list(set(all_areas_in_log)))
        selected_area = st.selectbox("Filter by Area", all_areas_in_log)

    # --- Filtering logic, now robust due to dynamic selected_username ---
    if selected_username != "All": # This will correctly filter for admins (when "All" is not selected)
                                  # and for non-admins (where selected_username is always their own username)
        df_filtered_all_log = df_filtered_all_log[df_filtered_all_log['Username'] == selected_username]

    if selected_shift != "All":
        df_filtered_all_log = df_filtered_all_log[df_filtered_all_log['Shift'] == selected_shift]

    if selected_area != "All":
        df_filtered_all_log = df_filtered_all_log[
            (df_filtered_all_log.get('Area 1', pd.Series()) == selected_area) | # Using .get() for robustness
            (df_filtered_all_log.get('Area 2', pd.Series()) == selected_area) |
            (df_filtered_all_log.get('Area 3', pd.Series()) == selected_area) |
            (df_filtered_all_log.get('Area 4', pd.Series()) == selected_area)
        ]

    columns_to_display_all = [
        "Username",
        "Date",
        "Day", "Hours", "Overtime",
        "Area 1", "Area 2", "Area 3", "Area 4",
        "Shift", "Remark"
    ]

    existing_columns_all = [col for col in columns_to_display_all if col in df_filtered_all_log.columns]

    # --- FIX: Conditionally sort only if 'Date' column exists ---
    if 'Date' in df_filtered_all_log.columns:
        st.dataframe(
            df_filtered_all_log[existing_columns_all]
            .sort_values(by="Date", ascending=False, na_position='last')
            .reset_index(drop=True),
            hide_index=True,
            use_container_width=True
        )
    else:
        st.dataframe(
            df_filtered_all_log[existing_columns_all]
            .reset_index(drop=True), # Display without sorting if 'Date' is missing
            hide_index=True,
            use_container_width=True
        )
        st.warning("Data log tidak dapat diurutkan berdasarkan 'Date' karena kolom tersebut tidak ditemukan.")


# --- Audit Log Tab ---
if show_audit_log_tab: # This block is now conditional
    with tab_map["🔍 Audit Log"]:
        st.header("🔍 System Audit Log")
        st.markdown("This log records significant actions performed within the application.")

        df_audit_log = get_data_from_sheet(SHEET_ID, sheet_audit_log_title)

        if not df_audit_log.empty:
            expected_audit_cols = ["Timestamp", "User ID", "Username", "Action", "Description", "Status"]
            # Filter df_audit_log to only include columns that are in expected_audit_cols AND exist in the DataFrame
            df_audit_log_display = df_audit_log[[col for col in expected_audit_cols if col in df_audit_log.columns]]
            
            # Check if any expected columns are missing
            for col in expected_audit_cols:
                if col not in df_audit_log.columns:
                    st.warning(f"Audit log column '{col}' not found. Please ensure your 'audit_log' Google Sheet has the correct headers.")
                    
            if 'Timestamp' in df_audit_log_display.columns:
                df_audit_log_display['Timestamp'] = pd.to_datetime(df_audit_log_display['Timestamp'], errors='coerce')
                df_audit_log_display.dropna(subset=['Timestamp'], inplace=True)
            else:
                st.warning("Kolom 'Timestamp' tidak ditemukan di audit log.")
                
            st.subheader("Filter Audit Log")
            col_audit_start, col_audit_end = st.columns(2)
            with col_audit_start:
                audit_start_date = st.date_input("Audit Log Start Date", datetime.today() - timedelta(days=30), key="audit_log_start_date")
            with col_audit_end:
                audit_end_date = st.date_input("Audit Log End Date", datetime.today(), key="audit_log_end_date")

            if 'Timestamp' in df_audit_log_display.columns:
                df_filtered_audit_log = df_audit_log_display[
                    (df_audit_log_display['Timestamp'].dt.date >= audit_start_date) &
                    (df_audit_log_display['Timestamp'].dt.date <= audit_end_date)
                ].copy()
            else:
                df_filtered_audit_log = df_audit_log_display.copy() # No date filtering possible

            col_audit_user, col_audit_action, col_audit_status = st.columns(3)
            with col_audit_user:
                if 'Username' in df_filtered_audit_log.columns:
                    all_audit_users = ["All"] + sorted(df_filtered_audit_log['Username'].unique().tolist())
                else:
                    all_audit_users = ["All"]
                selected_audit_user = st.selectbox("Filter by User", all_audit_users, key="selected_audit_user")
            with col_audit_action:
                if 'Action' in df_filtered_audit_log.columns:
                    all_audit_actions = ["All"] + sorted(df_filtered_audit_log['Action'].unique().tolist())
                else:
                    all_audit_actions = ["All"]
                selected_audit_action = st.selectbox("Filter by Action", all_audit_actions, key="selected_audit_action")
            with col_audit_status:
                if 'Status' in df_filtered_audit_log.columns:
                    all_audit_statuses = ["All"] + sorted(df_filtered_audit_log['Status'].unique().tolist())
                else:
                    all_audit_statuses = ["All"]
                selected_audit_status = st.selectbox("Filter by Status", all_audit_statuses, key="selected_audit_status")

            if selected_audit_user != "All":
                df_filtered_audit_log = df_filtered_audit_log[df_filtered_audit_log['Username'] == selected_audit_user]
            if selected_audit_action != "All":
                df_filtered_audit_log = df_filtered_audit_log[df_filtered_audit_log['Action'] == selected_audit_action]
            if selected_audit_status != "All":
                df_filtered_audit_log = df_filtered_audit_log[df_filtered_audit_log['Status'] == selected_audit_status]

            # --- FIX: Conditionally sort audit log only if 'Timestamp' column exists ---
            if 'Timestamp' in df_filtered_audit_log.columns:
                st.dataframe(
                    df_filtered_audit_log
                    .sort_values(by="Timestamp", ascending=False, na_position='last')
                    .reset_index(drop=True),
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.dataframe(
                    df_filtered_audit_log
                    .reset_index(drop=True), # Display without sorting if 'Timestamp' is missing
                    hide_index=True,
                    use_container_width=True
                )
                st.warning("Audit log tidak dapat diurutkan berdasarkan 'Timestamp' karena kolom tersebut tidak ditemukan.")
        else:
            st.info("No audit log entries found.")

# --- NEW: Master Edit Tab (Site Admin only) ---
if show_master_edit_tab:
    with tab_map["🛠️ Master Edit"]:
        st.header("🛠️ Master Edit (Site Admin Only)")
        st.markdown("Manage system-wide configurations and user accounts.")

        current_user_id = st.session_state.user["Id"]
        current_username = st.session_state.user["Username"]

        st.subheader("Manage Areas")
        
        # Display current areas
        df_areas_current = get_data_from_sheet(SHEET_ID, sheet_areas_title)
        if not df_areas_current.empty and 'AreaName' in df_areas_current.columns:
            st.write("Current Areas:")
            st.dataframe(df_areas_current[['AreaName']].rename(columns={'AreaName': 'Available Areas'}), hide_index=True, use_container_width=True)
            current_area_names = df_areas_current['AreaName'].astype(str).tolist()
        else:
            st.info(f"Tidak ada area yang ditemukan di sheet '{sheet_areas_title}'.")
            current_area_names = []

        # Add New Area Form
        with st.form("add_area_form", clear_on_submit=True):
            new_area_name = st.text_input("New Area Name", help="Enter a new area name (e.g., 'Refinery')")
            submit_add_area = st.form_submit_button("Add Area")
            if submit_add_area:
                if new_area_name:
                    add_area_to_sheet(new_area_name)
                    log_audit_event(current_user_id, current_username, "Master Edit - Add Area", f"Added new area: {new_area_name}.")
                    st.rerun()
                else:
                    st.warning("Nama area tidak boleh kosong.")

        # Delete Area Form
        if current_area_names:
            with st.form("delete_area_form", clear_on_submit=True):
                area_to_delete = st.selectbox("Select Area to Delete", options=[""] + current_area_names, key="area_to_delete_select")
                submit_delete_area = st.form_submit_button("Delete Selected Area")
                if submit_delete_area:
                    if area_to_delete:
                        confirm_delete = st.warning(f"Apakah Anda yakin ingin menghapus area '{area_to_delete}'? Ini akan menghapus permanen.")
                        # This simple confirmation doesn't block submission. A proper double-confirmation
                        # would need an extra button and state management.
                        # For now, relying on the warning.
                        if delete_area_from_sheet(area_to_delete):
                            log_audit_event(current_user_id, current_username, "Master Edit - Delete Area", f"Deleted area: {area_to_delete}.")
                            st.rerun()
                    else:
                        st.warning("Pilih area yang akan dihapus.")
        else:
            st.info("Tidak ada area untuk dihapus.")


        st.subheader("Manage User Passwords")
        df_all_users = get_data_from_sheet(SHEET_ID, sheet_user_title)

        if not df_all_users.empty and 'Id' in df_all_users.columns and 'Username' in df_all_users.columns:
            user_options = {f"{row['Username']} (ID: {row['Id']})": row['Id'] for idx, row in df_all_users.iterrows()}
            selected_user_display = st.selectbox(
                "Select User to Manage",
                options=[""] + list(user_options.keys()),
                key="select_user_to_manage"
            )
            
            selected_user_id_to_manage = None
            if selected_user_display:
                selected_user_id_to_manage = user_options.get(selected_user_display)

            if selected_user_id_to_manage:
                st.info(f"Mengelola pengguna: {selected_user_display}")

                with st.form("reset_password_form", clear_on_submit=True):
                    new_password_other = st.text_input("New Password", type="password", key="new_pass_other")
                    confirm_new_password_other = st.text_input("Confirm New Password", type="password", key="confirm_new_pass_other")
                    submit_reset_password = st.form_submit_button(f"Reset Password for {selected_user_display}")

                    if submit_reset_password:
                        if not new_password_other:
                            st.warning("Password baru tidak boleh kosong.")
                        elif new_password_other != confirm_new_password_other:
                            st.error("Password baru tidak cocok.")
                        else:
                            if update_user_data_in_sheet(selected_user_id_to_manage, "Password", new_password_other):
                                st.success(f"✅ Password untuk {selected_user_display} berhasil diubah.")
                                log_audit_event(current_user_id, current_username, "Master Edit - User Password Reset", f"Reset password for user ID: {selected_user_id_to_manage} ({selected_user_display.split(' (ID:')[0]}).")
                            else:
                                st.error(f"Gagal mengubah password untuk {selected_user_display}.")
                                log_audit_event(current_user_id, current_username, "Master Edit - User Password Reset", f"Failed to reset password for user ID: {selected_user_id_to_manage}.", "Failed")
            else:
                st.info("Pilih pengguna dari daftar untuk mengelola.")
        else:
            st.warning("Tidak ada data pengguna ditemukan.")
        
        st.info("Catatan: Untuk menjaga integritas data historis, ID pengguna tidak dapat diubah melalui aplikasi ini.")


# --- User Settings Tab
with tab_map["⚙️ User Settings"]:
    st.header("⚙️ User Settings")
    st.markdown("Here you can manage your account preferences.")

    current_user_id = st.session_state.user["Id"]
    current_username = st.session_state.user["Username"]

    st.subheader("Change Password")
    with st.form("change_password_form", clear_on_submit=True):
        old_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password", key="new_pass")
        confirm_new_password = st.text_input("Confirm New Password", type="password", key="confirm_new_pass")
        submit_password_change = st.form_submit_button("Update Password")

        if submit_password_change:
            df_users_latest = get_data_from_sheet(SHEET_ID, sheet_user_title)
            user_row_latest = df_users_latest[df_users_latest['Id'].astype(str) == str(current_user_id)]

            if user_row_latest.empty:
                st.error("User not found for password change. Please try logging in again.")
                log_audit_event(current_user_id, current_username, "Password Change", "Failed: User not found.")
            else:
                stored_password_value = str(user_row_latest.iloc[0]['Password']).strip()
                stored_hash_bytes = stored_password_value.encode('utf-8')

                password_match = False
                if stored_hash_bytes.startswith(b'$2a$') or stored_hash_bytes.startswith(b'$2b$') or stored_hash_bytes.startswith(b'$2y$'):
                    try:
                        password_match = bcrypt.checkpw(old_password.encode('utf-8'), stored_hash_bytes)
                    except ValueError:
                        st.error("Error verifying current password. It might be corrupted.")
                        password_match = False
                        log_audit_event(current_user_id, current_username, "Password Change", "Failed: Error verifying current password due to corrupted hash.")
                else:
                    password_match = (old_password == stored_password_value)

                if not password_match:
                    st.error("❌ Current password incorrect.")
                    log_audit_event(current_user_id, current_username, "Password Change", "Failed: Incorrect current password.")
                elif new_password != confirm_new_password:
                    st.error("❌ New passwords do not match.")
                    log_audit_event(current_user_id, current_username, "Password Change", "Failed: New passwords do not match.")
                elif not new_password:
                    st.warning("⚠️ New password cannot be empty.")
                    log_audit_event(current_user_id, current_username, "Password Change", "Failed: New password cannot be empty.")
                else:
                    if update_user_data_in_sheet(current_user_id, "Password", new_password):
                        st.session_state.user = None
                        st.session_state.logged_out_after_password_change = True
                        st.success("✅ Password updated successfully! Please re-login with your new password.")
                        log_audit_event(current_user_id, current_username, "Password Change", "Successfully updated password.")
                        st.rerun()
                    else:
                        st.error("Something went wrong during password update. Please try again.")
                        log_audit_event(current_user_id, current_username, "Password Change", "Failed: General update error.")

    st.subheader("Change Username")
    with st.form("change_username_form", clear_on_submit=True):
        new_username = st.text_input("New Username", value=current_username)
        submit_username_change = st.form_submit_button("Update Username")

        if submit_username_change:
            if new_username and new_username != current_username:
                if update_user_data_in_sheet(current_user_id, "Username", new_username):
                    st.session_state.user["Username"] = new_username
                    st.success(f"✅ Username updated to '{new_username}' successfully!")
                    log_audit_event(current_user_id, current_username, "Username Change", f"Successfully updated username to '{new_username}'.")
                    st.rerun()
                else:
                    st.error("Something went wrong during username update. Please try again.")
                    log_audit_event(current_user_id, current_username, "Username Change", "Failed: General update error.")
            elif new_username == current_username:
                st.info("💡 Username is already the same. No change needed.")
                log_audit_event(current_user_id, current_username, "Username Change", "No change needed, username is already the same.", "Info")
            else:
                st.warning("⚠️ Username cannot be empty.")
                log_audit_event(current_user_id, current_username, "Username Change", "Failed: Username cannot be empty.")

    st.subheader("Set Priority Areas")
    # NEW: Use all_area_opts from dynamic list
    df_areas_select = get_data_from_sheet(SHEET_ID, sheet_areas_title)
    if not df_areas_select.empty and 'AreaName' in df_areas_select.columns:
        all_area_opts_for_select = df_areas_select['AreaName'].astype(str).tolist()
    else:
        all_area_opts_for_select = ["GCP", "ER", "ET", "SC", "SM", "SAP"]
        st.warning("Could not load area list for 'Set Priority Areas'. Using default.")


    current_preferred_areas_str = st.session_state.user.get("Preferred Areas", "")
    current_preferred_areas_list = [a.strip() for a in current_preferred_areas_str.split(',') if a.strip()]

    current_preferred_areas_list = [area for area in current_preferred_areas_list if area in all_area_opts_for_select]

    with st.form("set_priority_areas_form", clear_on_submit=False):
        selected_areas = st.multiselect(
            "Select and order your frequently used areas (drag to reorder):",
            options=all_area_opts_for_select,
            default=current_preferred_areas_list,
            help="The order you select here will determine the default order in the Timesheet form's 'Area 1' dropdown."
        )
        submit_priority_areas = st.form_submit_button("Save Priority Areas")

        if submit_priority_areas:
            new_preferred_areas_str = ", ".join(selected_areas)
            if update_user_data_in_sheet(current_user_id, "Preferred Areas", new_preferred_areas_str):
                st.session_state.user["Preferred Areas"] = new_preferred_areas_str
                st.success("✅ Priority Areas saved successfully!")
                log_audit_event(current_user_id, current_username, "Update User Preference", f"Successfully updated preferred areas to: {new_preferred_areas_str}.")
                st.rerun()
            else:
                st.error("Something went wrong during saving priority areas. Please try again.")
                log_audit_event(current_user_id, current_username, "Update User Preference", f"Failed to update preferred areas to: {new_preferred_areas_str}.")

    st.subheader("Set Preferred Shift")
    all_shift_opts = ["Day Shift", "Night Shift", "Noon Shift"]
    current_preferred_shift = st.session_state.user.get("Preferred Shift", "Day Shift")

    with st.form("set_preferred_shift_form", clear_on_submit=False):
        selected_shift = st.selectbox(
            "Select your most frequently used shift:",
            options=all_shift_opts,
            index=all_shift_opts.index(current_preferred_shift) if current_preferred_shift in all_shift_opts else 0,
            help="This will set the default shift in the Timesheet form."
        )
        submit_preferred_shift = st.form_submit_button("Save Preferred Shift")

        if submit_preferred_shift:
            if update_user_data_in_sheet(current_user_id, "Preferred Shift", selected_shift):
                st.session_state.user["Preferred Shift"] = selected_shift
                st.success("✅ Preferred Shift saved successfully!")
                log_audit_event(current_user_id, current_username, "Update User Preference", f"Successfully updated preferred shift to: {selected_shift}.")
                st.rerun()
            else:
                st.error("Something went wrong during saving preferred shift. Please try again.")
                log_audit_event(current_user_id, current_username, "Update User Preference", f"Failed to update preferred shift to: {selected_shift}.")

    # --- START OF NEW FEATURE: Set Number of Area Columns ---
    st.subheader("Set Number of Area Columns")
    current_num_areas = st.session_state.user.get("Number of Areas", 1) # Default to 1 if not set
    # Ensure current_num_areas is an integer for display
    if not isinstance(current_num_areas, int):
        try:
            current_num_areas = int(current_num_areas)
        except (ValueError, TypeError):
            current_num_areas = 1 # Fallback if conversion fails

    area_column_options = [1, 2, 3, 4]

    with st.form("set_num_area_cols_form", clear_on_submit=False):
        selected_num_areas = st.selectbox(
            "How many 'Area' columns do you usually need in the Timesheet form?",
            options=area_column_options,
            index=area_column_options.index(current_num_areas) if current_num_areas in area_column_options else 0,
            help="This will hide/show Area 2, Area 3, and Area 4 columns in the Timesheet form."
        )
        submit_num_areas = st.form_submit_button("Save Area Column Preference")

        if submit_num_areas:
            if update_user_data_in_sheet(current_user_id, "Number of Areas", selected_num_areas):
                # Update session state for immediate effect
                st.session_state.user["Number of Areas"] = selected_num_areas
                st.success(f"✅ Area column preference saved successfully! Displaying {selected_num_areas} Area column(s).")
                log_audit_event(current_user_id, current_username, "Update User Preference", f"Set number of Area columns to: {selected_num_areas}.")
                st.rerun() # Rerun to apply changes to the Timesheet form
            else:
                st.error("Something went wrong during saving area column preference. Please try again.")
                log_audit_event(current_user_id, current_username, "Update User Preference", f"Failed to set number of Area columns to: {selected_num_areas}.", "Failed")
    # --- END OF NEW FEATURE: Set Number of Area Columns ---


# --- Developer Credits ---
st.markdown("---")
st.markdown(
    "<p align='center'>This application was developed by <b>Galih Primananda</b> and <b>Iqlima Nur Hayati</b>, 2025.</p>",
    unsafe_allow_html=True
)



