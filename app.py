import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import os
import io
import urllib.parse
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
                    is_approved INTEGER DEFAULT 1
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
st.set_page_config(page_title="Local Cashbook & Admin Panel", page_icon="💻", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None

st.title("💻 PC Local Accounting System")

# =========================================================
# 4. LOGIN (User & Admin Only - No Public Registration)
# =========================================================
if not st.session_state['logged_in']:
    tab_user_login, tab_admin_login = st.tabs(["👤 User Login", "🔐 Admin Login"])

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
                    st.warning("⚠️ आपका अकाउंट अभी निष्क्रिय है।")
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

    # ------------------ CUSTOMER PANEL ------------------
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

    # ------------------ MASTER ADMIN PANEL ------------------
    elif user_role == "Admin":
        st.title("👑 Admin Control Panel")
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["👥 यूजर्स डेटा & ID लिस्ट", "➕ नया यूजर जोड़ें", "📊 खातों का डेटा & Excel"])

        # TAB 1: User IDs and Details First
        with admin_tab1:
            st.subheader("👥 सभी Registered Users की सूची")
            
            user_list_query = """
                SELECT u.id, u.username, u.password, u.client_id, 
                       c.name, c.mobile, c.address, c.created_date
                FROM users u
                LEFT JOIN clients c ON u.client_id = c.unique_client_id
                WHERE u.role = 'Customer'
                ORDER BY u.id DESC
            """
            users_data = run_query(user_list_query)

            if not users_data.empty:
                # Excel Export of All Users
                st.download_button("📥 सभी यूजर्स डेटा Excel Export करें", 
                                   data=convert_df_to_excel(users_data), 
                                   file_name="All_Users_Details.xlsx")
                st.write("---")
                
                # Show dataframe
                st.dataframe(users_data[['username', 'password', 'client_id', 'name', 'mobile', 'address', 'created_date']], use_container_width=True)
            else:
                st.info("अभी कोई यूजर पंजीकृत नहीं है।")

        # TAB 2: Add New User (Registration by Admin Only) & Send WhatsApp Message
        with admin_tab2:
            st.subheader("➕ नया यूजर रजिस्टर करें (Admin Only)")
            
            with st.form("add_user_form", clear_on_submit=False):
                col1, col2 = st.columns(2)
                with col1:
                    c_name = st.text_input("ग्राहक का नाम *")
                    c_mobile = st.text_input("मोबाइल नंबर (WhatsApp) *")
                    c_address = st.text_area("पता *")
                with col2:
                    c_userid = st.text_input("User ID बनाएं *")
                    c_pass = st.text_input("Password बनाएं *")

                submit_reg = st.form_submit_button("पंजीकृत करें")

            if submit_reg:
                if all([c_name, c_mobile, c_userid, c_pass, c_address]):
                    # Check if Username already exists
                    existing = run_query("SELECT * FROM users WHERE username=?", (c_userid,))
                    if not existing.empty:
                        st.error("❌ यह User ID पहले से मौजूद है! कृपया दूसरी ID चुनें।")
                    else:
                        auto_id = f"NK-CUST-{1001 + len(run_query('SELECT * FROM clients'))}"
                        today = datetime.now().strftime("%Y-%m-%d")
                        
                        execute_db("INSERT INTO clients (unique_client_id, name, mobile, address, created_date) VALUES (?, ?, ?, ?, ?)",
                                   (auto_id, c_name, c_mobile, c_address, today))
                        
                        execute_db("INSERT INTO users (username, password, role, client_id, is_approved) VALUES (?, ?, 'Customer', ?, 1)",
                                   (c_userid, c_pass, auto_id))
                        
                        st.success(f"✅ यूजर सफलतापूर्वक जोड़ा गया! Client ID: {auto_id}")
                        
                        # Generate WhatsApp link to send User ID & Password
                        clean_mobile = ''.join(filter(str.isdigit, c_mobile))
                        if len(clean_mobile) == 10:
                            clean_mobile = "91" + clean_mobile
                        
                        whatsapp_msg = f"नमस्ते {c_name},\nआपका NIKA Services अकाउंट बन गया है।\n\n🆔 *User ID:* {c_userid}\n🔑 *Password:* {c_pass}\n🪪 *Client ID:* {auto_id}\n\nधन्यवाद!"
                        encoded_msg = urllib.parse.quote(whatsapp_msg)
                        wa_url = f"https://wa.me/{clean_mobile}?text={encoded_msg}"
                        
                        st.markdown(f'<a href="{wa_url}" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #25D366; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">📲 WhatsApp पर ID & Password भेजें</a>', unsafe_allow_html=True)
                else:
                    st.error("⚠️ सभी फील्ड भरना अनिवार्य है!")

        # TAB 3: All Transactions & Master Excel Export
        with admin_tab3:
            st.subheader("📊 सभी लेनदेन (Accounts)")
            all_accounts = run_query("SELECT * FROM accounts ORDER BY id DESC")
            st.dataframe(all_accounts, use_container_width=True)
            if not all_accounts.empty:
                st.download_button("📥 Master Transactions Excel डाउनलोड", 
                                   data=convert_df_to_excel(all_accounts), 
                                   file_name="Master_Transactions_Data.xlsx")
