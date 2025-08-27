import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import bcrypt
import streamlit.components.v1 as components # Import for custom HTML/JS

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

key_dict = st.secrets["gcp_service_account"]
creds = Credentials.from_service_account_info(key_dict, scopes=scope)
SHEET_ID = "1BwwoNx3t3MBrsOB3H9BSxnWbYCwChwgl4t1HrpFYWpA"

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
