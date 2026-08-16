import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import os
import io
import pdfplumber
from reportlab.pdfgen import canvas

# =========================================================
# 1. LOCAL DATABASE INITIALIZATION (PC Server Setup)
# =========================================================
DB_NAME = "local_cashbook.db"

def init_db():
    """अपने PC पर SQLite डेटाबेस और टेबल ऑटोमैटिक बनाएगा"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT,
                    role TEXT,
                    client_id TEXT,
                    is_approved INTEGER DEFAULT 0
                )''')
    
    # Clients Table
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unique_client_id TEXT,
                    name TEXT,
                    mobile TEXT,
                    address TEXT,
                    created_date TEXT
                )''')
    
    # Accounts/Ledger Table
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    date TEXT,
                    type TEXT,
                    amount REAL,
                    description TEXT
                )''')
    
    # Default Admin (अगर पहले से नहीं है)
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role, is_approved) VALUES ('admin', 'admin123', 'Admin', 1)")
    
    conn.commit()
    conn.close()

init_db()

# =========================================================
# 2. HELPER FUNCTIONS FOR LOCAL DB
# =========================================================
def run_query(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def execute_db(query, params=()):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

def generate_id_card_pdf(name, client_id, mobile, address):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(250, 160))
    c.rect(5, 5, 240, 150)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20, 135, "NIKA SERVICES - ID CARD")
    c.setLineWidth(0.5)
    c.line(20, 128, 230, 128)
    c.setFont("Helvetica", 10)
    c.drawString(20, 105, f"ID No: {client_id}")
    c.drawString(20, 85, f"Name: {name}")
    c.drawString(20, 65, f"Mobile: {mobile}")
    c.drawString(20, 45, f"Address: {str(address)[:25]}...")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# =========================================================
# 3. PAGE CONFIG & SESSION
# =========================================================
st.set_page_config(page_title="Local Cashbook & ID Generator", page_icon="💻", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None

st.title("💻 PC Local Accounting & ID Generator")

# =========================================================
# 4. LOGIN & REGISTRATION
# =========================================================
if not st.session_state['logged_in']:
    tab_user_login, tab_admin_login, reg_tab = st.tabs(["👤 User Login", "🔐 Admin Login", "📝 New Registration"])

    with tab_user_login:
        c_username = st.text_input("User ID", key="c_user")
        c_password = st.text_input("Password", type="password", key="c_pass")
        if st.button("User Login"):
            users_df = run_query("SELECT * FROM users WHERE username=? AND password=? AND role='Customer'", (c_username, c_password))
            if not users_df.empty:
                if users_df.iloc[0]['is_approved'] == 1:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = users_df.iloc[0].to_dict()
                    st.success("✅ लॉगिन सफल!")
                    st.rerun()
                else:
                    st.warning("⚠️ आपका अकाउंट अभी पेंडिंग है।")
            else:
                st.error("❌ गलत विवरण!")

    with tab_admin_login:
        a_username = st.text_input("Admin User ID", key="a_user")
        a_password = st.text_input("Admin Password", type="password", key="a_pass")
        if st.button("Admin Login"):
            users_df = run_query("SELECT * FROM users WHERE username=? AND password=? AND role='Admin'", (a_username, a_password))
            if not users_df.empty:
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = users_df.iloc[0].to_dict()
                st.success("✅ एडमिन लॉगिन सफल!")
                st.rerun()
            else:
                st.error("❌ गलत Admin विवरण!")

    with reg_tab:
        c_name = st.text_input("नाम *")
        c_mobile = st.text_input("मोबाइल *")
        c_userid = st.text_input("User ID बनाएं *")
        c_pass = st.text_input("Password बनाएं *", type="password")
        c_address = st.text_area("पता *")

        if st.button("Register Account"):
            if all([c_name, c_mobile, c_userid, c_pass, c_address]):
                auto_id = f"NK-CUST-{1001 + len(run_query('SELECT * FROM clients'))}"
                today = datetime.now().strftime("%Y-%m-%d")
                
                execute_db("INSERT INTO clients (unique_client_id, name, mobile, address, created_date) VALUES (?, ?, ?, ?, ?)",
                           (auto_id, c_name, c_mobile, c_address, today))
                
                execute_db("INSERT INTO users (username, password, role, client_id, is_approved) VALUES (?, ?, 'Customer', ?, 0)",
                           (c_userid, c_pass, auto_id))
                
                st.success(f"✅ रजिस्ट्रेशन सफल हुआ! ID: {auto_id}")
            else:
                st.error("सभी फील्ड भरें!")

# =========================================================
# 5. DASHBOARD (USER & ADMIN)
# =========================================================
else:
    st.sidebar.write(f"Logged in: **{st.session_state['user_info']['username']}**")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.session_state['user_info'] = None
        st.rerun()

    user_role = st.session_state['user_info']['role']
    user_id = st.session_state['user_info']['username']

    if user_role == "Customer":
        u_tab1, u_tab2, u_tab3 = st.tabs(["📊 दैनिक हिसाब", "📁 PDF & ID Card", "📥 Excel Download"])

        with u_tab1:
            t_type = st.selectbox("प्रकार", ["Income (आय)", "Expense (खर्च)"])
            t_amount = st.number_input("राशि (₹)", min_value=1.0)
            t_desc = st.text_input("विवरण")

            if st.button("सेव करें"):
                execute_db("INSERT INTO accounts (username, date, type, amount, description) VALUES (?, ?, ?, ?, ?)",
                           (user_id, datetime.now().strftime("%Y-%m-%d %H:%M"), t_type, t_amount, t_desc))
                st.success("✅ हिसाब आपके PC पर सेव हो गया!")
                st.rerun()

            st.subheader("आपका हिसाब")
            st.dataframe(run_query("SELECT date, type, amount, description FROM accounts WHERE username=?", (user_id,)), use_container_width=True)

        with u_tab2:
            uploaded_pdf = st.file_uploader("PDF अपलोड करें", type=["pdf"])
            if uploaded_pdf:
                with pdfplumber.open(uploaded_pdf) as pdf:
                    text = "".join([page.extract_text() or "" for page in pdf.pages])
                st.text_area("एक्सट्रैक्ट टेक्स्ट:", text, height=150)

            st.subheader("ID Card Generator")
            client_df = run_query("SELECT * FROM clients WHERE unique_client_id=?", (st.session_state['user_info'].get('client_id'),))
            if not client_df.empty:
                c_row = client_df.iloc[0]
                pdf = generate_id_card_pdf(c_row['name'], c_row['unique_client_id'], c_row['mobile'], c_row['address'])
                st.download_button("🪪 ID Card Download करें", data=pdf, file_name=f"ID_{c_row['unique_client_id']}.pdf")

        with u_tab3:
            my_acc = run_query("SELECT * FROM accounts WHERE username=?", (user_id,))
            if not my_acc.empty:
                st.download_button("📊 Excel डेटा डाउनलोड करें", data=convert_df_to_excel(my_acc), file_name="My_Accounts.xlsx")

    elif user_role == "Admin":
        st.title("👑 Master Admin Control")
        admin_tab1, admin_tab2 = st.tabs(["📊 सभी यूजर्स का डेटा", "⚙️ Approvals"])

        with admin_tab1:
            st.dataframe(run_query("SELECT * FROM accounts"), use_container_width=True)
            st.download_button("📥 Master Excel डाउनलोड", data=convert_df_to_excel(run_query("SELECT * FROM accounts")), file_name="Master_Data.xlsx")

        with admin_tab2:
            pending = run_query("SELECT * FROM users WHERE is_approved=0")
            for idx, row in pending.iterrows():
                col1, col2 = st.columns([3, 1])
                col1.write(f"User: **{row['username']}** | Client ID: {row['client_id']}")
                if col2.button("Approve", key=f"app_{row['id']}"):
                    execute_db("UPDATE users SET is_approved=1 WHERE id=?", (row['id'],))
                    st.success("Approved!")
                    st.rerun()
