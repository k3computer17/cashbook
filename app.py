import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import io
import smtplib
import urllib.parse
import random
import string
from email.mime.text import MIMEText

# =========================================================
# 1. DATABASE INITIALIZATION & MIGRATIONS
# =========================================================
DB_NAME = "local_cashbook.db"

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT,
                    role TEXT,
                    client_id TEXT,
                    is_approved INTEGER DEFAULT 1,
                    email TEXT,
                    mobile TEXT,
                    full_name TEXT,
                    father_name TEXT,
                    pan_card TEXT,
                    aadhaar_no TEXT,
                    shop_name TEXT,
                    is_first_login INTEGER DEFAULT 1
                )''')
    
    # Accounts / Cashbook Table
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    date TEXT,
                    type TEXT,            
                    amount REAL,
                    account_type TEXT,    
                    tx_id TEXT,
                    cust_name TEXT,
                    cust_aadhaar_last4 TEXT,
                    cust_due_amount REAL DEFAULT 0.0,
                    description TEXT
                )''')

    # Auto-migrations
    existing_user_cols = [col[1] for col in c.execute("PRAGMA table_info(users)").fetchall()]
    user_cols_to_add = {
        "email": "TEXT", "mobile": "TEXT", "full_name": "TEXT", 
        "father_name": "TEXT", "pan_card": "TEXT", "aadhaar_no": "TEXT", 
        "shop_name": "TEXT", "is_first_login": "INTEGER DEFAULT 1"
    }
    for col_name, col_type in user_cols_to_add.items():
        if col_name not in existing_user_cols:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")

    existing_acc_cols = [col[1] for col in c.execute("PRAGMA table_info(accounts)").fetchall()]
    if "cust_name" not in existing_acc_cols:
        c.execute("ALTER TABLE accounts ADD COLUMN cust_name TEXT")
    if "cust_aadhaar_last4" not in existing_acc_cols:
        c.execute("ALTER TABLE accounts ADD COLUMN cust_aadhaar_last4 TEXT")
    if "cust_due_amount" not in existing_acc_cols:
        c.execute("ALTER TABLE accounts ADD COLUMN cust_due_amount REAL DEFAULT 0.0")

    # Daily Services Log Table
    c.execute('''CREATE TABLE IF NOT EXISTS daily_services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    date TEXT,
                    service_name TEXT,
                    ref_no TEXT,
                    income_amount REAL,
                    notes TEXT
                )''')
    
    # Opening Balance Table
    c.execute('''CREATE TABLE IF NOT EXISTS opening_balances (
                    username TEXT PRIMARY KEY,
                    cash_op REAL DEFAULT 0.0,
                    bank_op REAL DEFAULT 0.0
                )''')
    
    # Default Admin User
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role, is_approved, is_first_login) VALUES ('admin', 'admin123', 'Admin', 1, 0)")
    
    conn.commit()
    conn.close()

init_db()

# =========================================================
# 2. HELPER FUNCTIONS
# =========================================================
def run_query(query, params=()):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def execute_db(query, params=()):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

def generate_auto_userid(full_name, mobile):
    prefix = "".join(e for e in full_name if e.isalnum())[:4].upper()
    mobile_suffix = mobile[-4:] if len(mobile) >= 4 else str(random.randint(1000, 9999))
    return f"{prefix}{mobile_suffix}"

def generate_one_time_password(length=6):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
    return output.getvalue()

def calculate_exact_balances(username):
    op = run_query("SELECT * FROM opening_balances WHERE username=?", (username,))
    cash_op = float(op.iloc[0]['cash_op']) if not op.empty else 0.0
    bank_op = float(op.iloc[0]['bank_op']) if not op.empty else 0.0
    
    acc_df = run_query("SELECT * FROM accounts WHERE username=?", (username,))
    serv_df = run_query("SELECT * FROM daily_services WHERE username=?", (username,))
    
    services_cash_income = float(serv_df['income_amount'].sum()) if not serv_df.empty else 0.0
    
    cash_df = acc_df[acc_df['account_type'] == 'Cash'] if not acc_df.empty else pd.DataFrame()
    bank_df = acc_df[acc_df['account_type'] == 'Bank Account'] if not acc_df.empty else pd.DataFrame()

    cash_dep = float(cash_df[cash_df['type'] == 'Deposit (जमा)']['amount'].sum()) if not cash_df.empty else 0.0
    cash_wth = float(cash_df[cash_df['type'] == 'Withdrawal (निकासी)']['amount'].sum()) if not cash_df.empty else 0.0
    personal_gullak = float(cash_df[cash_df['type'] == 'Personal Use / Gullak (निजी खर्च/गुल्लक)']['amount'].sum()) if not cash_df.empty else 0.0
    due_recovered_cash = float(cash_df[cash_df['type'] == 'Customer Due Payment Received (उधार रिकवरी - Cash +)']['amount'].sum()) if not cash_df.empty else 0.0
    
    cust_aeps = float(bank_df[bank_df['type'].str.contains('Customer AEPS Withdrawal', na=False)]['amount'].sum()) if not bank_df.empty else 0.0
    cust_dep_dmt = float(bank_df[bank_df['type'].str.contains('Customer Deposit / Money Transfer', na=False)]['amount'].sum()) if not bank_df.empty else 0.0
    self_bank_wth = float(bank_df[bank_df['type'].str.contains('Self Bank Cash Withdrawal', na=False)]['amount'].sum()) if not bank_df.empty else 0.0
    self_bank_dep = float(bank_df[bank_df['type'].str.contains('Self Bank Cash Deposit', na=False)]['amount'].sum()) if not bank_df.empty else 0.0

    final_cash_closing = cash_op + cash_dep + services_cash_income + self_bank_wth + cust_dep_dmt + due_recovered_cash - cash_wth - personal_gullak - self_bank_dep - cust_aeps
    final_bank_closing = bank_op + self_bank_dep + cust_aeps - self_bank_wth - cust_dep_dmt

    return {
        "cash_op": cash_op,
        "cash_closing": final_cash_closing,
        "bank_op": bank_op,
        "bank_closing": final_bank_closing,
        "services_income": services_cash_income,
        "personal_gullak": personal_gullak
    }

# =========================================================
# 3. CUSTOM UI STYLING & POWER SWITCH CARD
# =========================================================
st.set_page_config(page_title="Digital Banking & Cashbook System", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    /* Metric Cards Styling */
    .metric-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px;
        color: white;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    .metric-title { font-size: 0.85rem; color: #94a3b8; font-weight: 600; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #38bdf8; margin: 4px 0; }
    .metric-sub { font-size: 0.75rem; color: #64748b; }

    /* Technical Power Switch / Hardware Info Card */
    .hardware-card {
        background: #020617;
        border: 1px solid #1e293b;
        border-left: 5px solid #22c55e;
        border-radius: 12px;
        padding: 18px 24px;
        margin: 15px 0 25px 0;
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3);
    }
    .switch-badge {
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        border: 1px solid rgba(34, 197, 94, 0.3);
        display: inline-block;
        margin-bottom: 8px;
    }
    .tech-term {
        color: #38bdf8;
        font-weight: 600;
    }
    
    /* Section Box Styling */
    .section-box {
        background-color: #f8fafc;
        border-left: 5px solid #2563eb;
        padding: 10px 16px;
        border-radius: 4px;
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None
if 'force_password_change' not in st.session_state:
    st.session_state['force_password_change'] = False

# =========================================================
# 4. SINGLE UNIFIED LOGIN (HIDDEN ADMIN)
# =========================================================
if st.session_state['force_password_change']:
    st.warning("🔒 सुरक्षा अपडेट: कृपया अपना नया स्थायी पासवर्ड बनाएं।")
    with st.form("first_time_pwd_form"):
        new_pwd = st.text_input("नया पासवर्ड *", type="password")
        confirm_pwd = st.text_input("पासवर्ड पुष्टि करें *", type="password")
        
        if st.form_submit_button("💾 नया पासवर्ड सेट करें"):
            if new_pwd and confirm_pwd and (new_pwd == confirm_pwd):
                user_id = st.session_state['user_info']['username']
                execute_db("UPDATE users SET password=?, is_first_login=0 WHERE username=?", (new_pwd, user_id))
                st.success("✅ पासवर्ड अपडेट हो गया!")
                st.session_state['force_password_change'] = False
                st.session_state['user_info']['is_first_login'] = 0
                st.rerun()
            else:
                st.error("❌ पासवर्ड मैच नहीं हुए!")

elif not st.session_state['logged_in']:
    st.title("🏦 Unified Digital Banking & Cashbook Portal")
    
    st.subheader("🔑 Sign In")
    c_username = st.text_input("User ID / Login ID")
    c_password = st.text_input("Password", type="password")
    
    if st.button("Log In", type="primary", use_container_width=True):
        u_df = run_query("SELECT * FROM users WHERE username=? AND password=?", (c_username, c_password))
        if not u_df.empty:
            user_data = u_df.iloc[0].to_dict()
            st.session_state['logged_in'] = True
            st.session_state['user_info'] = user_data
            if user_data.get('is_first_login') == 1:
                st.session_state['force_password_change'] = True
            st.rerun()
        else:
            st.error("❌ अमान्य User ID या Password!")

# =========================================================
# 5. USER PORTAL (WITH HARDWARE SWITCH CARD & HIDDEN ADMIN)
# =========================================================
else:
    user_role = st.session_state['user_info']['role']
    user_id = st.session_state['user_info']['username']

    # Sidebar Header
    st.sidebar.markdown(f"### 👤 Active User\n**{st.session_state['user_info'].get('full_name', user_id)}**")
    st.sidebar.caption(f"Role: {user_role} | ID: {user_id}")
    st.sidebar.write("---")
    
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state['logged_in'] = False
        st.session_state['user_info'] = None
        st.session_state['force_password_change'] = False
        st.rerun()

    b = calculate_exact_balances(user_id)

    # 1. Dashboard Metrics Overview
    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(f"""<div class="metric-card"><div class="metric-title">💵 CASH BALANCE</div><div class="metric-value">₹{b['cash_closing']:,.2f}</div><div class="metric-sub">Opening: ₹{b['cash_op']:,.2f}</div></div>""", unsafe_allow_html=True)
    m2.markdown(f"""<div class="metric-card"><div class="metric-title">🏦 BANK BALANCE</div><div class="metric-value" style="color:#a7f3d0;">₹{b['bank_closing']:,.2f}</div><div class="metric-sub">Opening: ₹{b['bank_op']:,.2f}</div></div>""", unsafe_allow_html=True)
    m3.markdown(f"""<div class="metric-card"><div class="metric-title">💼 SERVICES INCOME</div><div class="metric-value" style="color:#fde047;">₹{b['services_income']:,.2f}</div><div class="metric-sub">Commission Earned</div></div>""", unsafe_allow_html=True)
    m4.markdown(f"""<div class="metric-card"><div class="metric-title">🏺 GULLAK / PERSONAL</div><div class="metric-value" style="color:#f472b6;">₹{b['personal_gullak']:,.2f}</div><div class="metric-sub">Personal Expense</div></div>""", unsafe_allow_html=True)

    # 2. Hardware / Technical Info Card (Power Switch Component)
    st.markdown("""
        <div class="hardware-card">
            <span class="switch-badge">⚡ HARDWARE & POWER SPECIFICATION</span>
            <div style="color: #f8fafc; font-size: 0.95rem; line-height: 1.6;">
                बोर्ड पर लगे जिस मुख्य स्विच से मशीन ऑन या ऑफ होती है, उसे तकनीकी भाषा में 
                <span class="tech-term">पॉवर स्विच (Power Switch)</span>, 
                <span class="tech-term">पॉवर बटन (Power Button)</span> या 
                <span class="tech-term">टॉगल स्विच (Toggle Switch)</span> कहा जाता है। 
                सर्किट बोर्ड या मदरबोर्ड की भाषा में इसे 
                <span class="tech-term">पॉवर ऑन/ऑफ स्विच (Power On/Off Switch)</span> या 
                <span class="tech-term">पिनहेडर पॉवर स्विच (Power Pin Header Switch)</span> भी कहते हैं।
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 3. Dynamic Tabs Structure
    tab_list = [
        "➕ New Transaction", 
        "🔍 Customer Ledger", 
        "🛠️ Daily Services Log", 
        "📋 Full Cashbook", 
        "⚙️ Balances & Settings"
    ]
    
    # Check if User is Admin -> Automatically add Hidden Admin Panel Tab
    if user_role == "Admin":
        tab_list.append("👑 Master Admin Controls")

    tabs = st.tabs(tab_list)

    # TAB 1: ENTRY WINDOW
    with tabs[0]:
        st.markdown('<div class="section-box"><h4>➕ Transaction Entry Window</h4></div>', unsafe_allow_html=True)
        with st.form("main_txn_form", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            with fc1:
                t_account = st.selectbox("Account Type *", ["Bank Account", "Cash"])
                if t_account == "Bank Account":
                    t_type = st.selectbox("Transaction Type *", [
                        "Customer AEPS Withdrawal",
                        "Customer Deposit / Money Transfer",
                        "Self Bank Cash Withdrawal",
                        "Self Bank Cash Deposit"
                    ])
                else:
                    t_type = st.selectbox("Transaction Type *", [
                        "Deposit (जमा)", 
                        "Withdrawal (निकासी)", 
                        "Customer Due Payment Received (उधार रिकवरी - Cash +)",
                        "Personal Use / Gullak (निजी खर्च/गुल्लक)"
                    ])
                t_amount = st.number_input("Amount (₹) *", min_value=0.0, step=100.0)
                t_tx_id = st.text_input("Txn / UTR / Reference No")
            
            with fc2:
                t_cname = st.text_input("Customer Name")
                t_aadhaar = st.text_input("Aadhaar Last 4 Digits", max_chars=4)
                t_due = st.number_input("New Due Amount (₹)", min_value=0.0, value=0.0, step=50.0)
                t_desc = st.text_input("Description / Note")
                t_date = st.date_input("Date", datetime.now())

            if st.form_submit_button("✅ Save Transaction", use_container_width=True):
                if t_amount > 0:
                    d_str = f"{t_date.strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M')}"
                    execute_db("""INSERT INTO accounts 
                                  (username, date, type, amount, account_type, tx_id, cust_name, cust_aadhaar_last4, cust_due_amount, description) 
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                               (user_id, d_str, t_type, t_amount, t_account, t_tx_id, t_cname, t_aadhaar, t_due, t_desc))
                    st.success("🎉 Transaction Success!")
                    st.rerun()

    # TAB 2: LEDGER SEARCH
    with tabs[1]:
        st.markdown('<div class="section-box"><h4>🔍 Customer Aadhaar & Due Search</h4></div>', unsafe_allow_html=True)
        sc1, sc2 = st.columns(2)
        search_aadhaar = sc1.text_input("Aadhaar Last 4 Digits:")
        search_name = sc2.text_input("Or Search Name:")

        if search_aadhaar or search_name:
            query = "SELECT date, type, amount, cust_name, cust_aadhaar_last4, cust_due_amount, tx_id, description FROM accounts WHERE username=? AND "
            params = [user_id]
            if search_aadhaar:
                query += "cust_aadhaar_last4 LIKE ?"
                params.append(f"%{search_aadhaar}%")
            else:
                query += "cust_name LIKE ?"
                params.append(f"%{search_name}%")
            
            cust_data = run_query(query, tuple(params))
            if not cust_data.empty:
                st.dataframe(cust_data, use_container_width=True)
                st.download_button("📥 Export Excel", data=convert_df_to_excel(cust_data), file_name="Customer_Ledger.xlsx")
            else:
                st.info("ℹ️ No data found.")

    # TAB 3: SERVICES LOG
    with tabs[2]:
        st.markdown('<div class="section-box"><h4>🛠️ Online Services & Commission Entry Log</h4></div>', unsafe_allow_html=True)
        with st.form("services_form", clear_on_submit=True):
            svc1, svc2 = st.columns(2)
            with svc1:
                s_name = st.selectbox("Service Name *", ["PMJJBY", "PMSBY", "APY", "KYC", "PAN Card", "Aadhaar Work", "Money Transfer Fee", "Other"])
                s_ref = st.text_input("Reference / Cust Name *")
            with svc2:
                s_income = st.number_input("Fee / Income (₹) *", min_value=0.0)
                s_note = st.text_input("Notes")

            if st.form_submit_button("💼 Save Service Record"):
                if s_ref and s_income >= 0:
                    execute_db("INSERT INTO daily_services (username, date, service_name, ref_no, income_amount, notes) VALUES (?, ?, ?, ?, ?, ?)",
                               (user_id, datetime.now().strftime('%Y-%m-%d %H:%M'), s_name, s_ref, s_income, s_note))
                    st.success("✅ Saved!")
                    st.rerun()

        st.dataframe(run_query("SELECT date, service_name, ref_no, income_amount, notes FROM daily_services WHERE username=? ORDER BY id DESC", (user_id,)), use_container_width=True)

    # TAB 4: FULL CASHBOOK
    with tabs[3]:
        st.markdown('<div class="section-box"><h4>📋 Full Transaction Register</h4></div>', unsafe_allow_html=True)
        all_txns = run_query("SELECT id, date, account_type, type, amount, cust_name, cust_aadhaar_last4, cust_due_amount, tx_id, description FROM accounts WHERE username=? ORDER BY id DESC", (user_id,))
        st.dataframe(all_txns, use_container_width=True)

    # TAB 5: SETTINGS
    with tabs[4]:
        st.markdown('<div class="section-box"><h4>⚙️ Opening Balances</h4></div>', unsafe_allow_html=True)
        curr_op = run_query("SELECT * FROM opening_balances WHERE username=?", (user_id,))
        op_c = curr_op.iloc[0]['cash_op'] if not curr_op.empty else 0.0
        op_b = curr_op.iloc[0]['bank_op'] if not curr_op.empty else 0.0

        with st.form("op_form"):
            oc1, oc2 = st.columns(2)
            nc = oc1.number_input("Cash Opening Balance (₹)", value=float(op_c))
            nb = oc2.number_input("Bank Opening Balance (₹)", value=float(op_b))
            if st.form_submit_button("💾 Save Balances"):
                execute_db("""INSERT INTO opening_balances (username, cash_op, bank_op) VALUES (?, ?, ?)
                              ON CONFLICT(username) DO UPDATE SET cash_op=excluded.cash_op, bank_op=excluded.bank_op""",
                           (user_id, nc, nb))
                st.success("✅ Balances Updated!")
                st.rerun()

    # TAB 6: HIDDEN ADMIN CONTROLS (Only Visible if Logged-in User is Admin)
    if user_role == "Admin":
        with tabs[5]:
            st.markdown('<div class="section-box"><h4>👑 Hidden Master Admin Controls</h4></div>', unsafe_allow_html=True)
            
            st.subheader("👥 Register New User")
            with st.form("master_user_form"):
                col1, col2 = st.columns(2)
                with col1:
                    u_full_name = st.text_input("Full Name *")
                    u_father_name = st.text_input("Father Name *")
                    u_shop_name = st.text_input("Shop Name *")
                    u_mobile = st.text_input("Mobile No *")
                with col2:
                    u_email = st.text_input("Email ID *")
                    u_pan = st.text_input("PAN No")
                    u_aadhaar = st.text_input("Aadhaar No")
                
                if st.form_submit_button("🚀 Create User"):
                    if u_full_name and u_mobile:
                        auto_user_id = generate_auto_userid(u_full_name, u_mobile)
                        one_time_pass = generate_one_time_password(6)
                        execute_db("""INSERT INTO users 
                                      (username, password, role, is_approved, email, mobile, full_name, father_name, pan_card, aadhaar_no, shop_name, is_first_login) 
                                      VALUES (?, ?, 'Customer', 1, ?, ?, ?, ?, ?, ?, ?, 1)""", 
                                   (auto_user_id, one_time_pass, u_email, u_mobile, u_full_name, u_father_name, u_pan, u_aadhaar, u_shop_name))
                        st.success(f"🎉 Created User! ID: {auto_user_id} | Pass: {one_time_pass}")

            st.write("---")
            st.subheader("📊 Master Database Reports")
            all_users = run_query("SELECT id, username, full_name, shop_name, mobile FROM users WHERE role='Customer'")
            st.dataframe(all_users, use_container_width=True)
