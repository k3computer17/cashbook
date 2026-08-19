import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import io
import random
import string

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
                    payment_mode TEXT DEFAULT 'Cash',
                    description TEXT
                )''')

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
    
    # HARD RESET / ENSURE OFFICIAL ADMIN ACCOUNT
    # Isse Admin Login kabhi bhi fail nahi hoga
    c.execute("DELETE FROM users WHERE username='admin'")
    c.execute("""INSERT INTO users 
                 (username, password, role, is_approved, is_first_login, full_name) 
                 VALUES ('admin', 'admin123', 'Official_Admin', 1, 0, 'System Administrator')""")
    
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
# 3. PAGE CONFIG & STYLING
# =========================================================
st.set_page_config(page_title="Digital Cashbook Portal", page_icon="🏦", layout="wide")

st.markdown("""
    <style>
    .metric-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px;
        color: white;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .metric-title { font-size: 0.85rem; color: #94a3b8; font-weight: 600; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #38bdf8; }
    .metric-sub { font-size: 0.75rem; color: #64748b; margin-top: 4px; }
    .section-box {
        background-color: #f8fafc;
        border-left: 5px solid #0284c7;
        padding: 10px 15px;
        border-radius: 4px;
        margin-bottom: 15px;
    }
    .receipt-box {
        background: #ffffff;
        border: 2px dashed #0284c7;
        padding: 20px;
        border-radius: 10px;
        font-family: monospace;
    }
    </style>
""", unsafe_allow_html=True)

# Session States
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None
if 'force_password_change' not in st.session_state:
    st.session_state['force_password_change'] = False

# =========================================================
# 4. LOGIN & AUTHENTICATION PORTALS (USER / ADMIN / FORGOT)
# =========================================================
if st.session_state['force_password_change']:
    st.warning("🔒 First Time Login: Please set your new permanent password.")
    with st.form("first_time_pwd_form"):
        new_pwd = st.text_input("New Password *", type="password")
        confirm_pwd = st.text_input("Confirm New Password *", type="password")
        
        if st.form_submit_button("💾 Save New Password"):
            if new_pwd and confirm_pwd and (new_pwd == confirm_pwd):
                user_id = st.session_state['user_info']['username']
                execute_db("UPDATE users SET password=?, is_first_login=0 WHERE username=?", (new_pwd, user_id))
                st.success("✅ Password updated successfully!")
                st.session_state['force_password_change'] = False
                st.session_state['user_info']['is_first_login'] = 0
                st.rerun()
            else:
                st.error("❌ Passwords do not match!")

elif not st.session_state['logged_in']:
    st.title("🏦 Digital Cashbook & Merchant Portal")
    
    login_tab1, login_tab2, login_tab3 = st.tabs([
        "👤 Merchant / User Login", 
        "🔑 Forgot Password (User Recovery)", 
        "🛡️ Official Admin Portal"
    ])

    # ---------------------------------------------------------
    # TAB 1: USER LOGIN PORTAL
    # ---------------------------------------------------------
    with login_tab1:
        st.subheader("👤 User Login Window")
        with st.form("user_login_form"):
            u_username = st.text_input("User ID / Username")
            u_password = st.text_input("Password", type="password")
            if st.form_submit_button("🔑 User Login", use_container_width=True):
                chk_user = run_query("SELECT * FROM users WHERE username=? AND password=? AND role='Customer'", (u_username, u_password))
                if not chk_user.empty:
                    user_data = chk_user.iloc[0].to_dict()
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = user_data
                    if user_data.get('is_first_login') == 1:
                        st.session_state['force_password_change'] = True
                    st.rerun()
                else:
                    st.error("❌ Invalid User ID or Password!")

    # ---------------------------------------------------------
    # TAB 2: FORGOT USER PASSWORD (VERIFICATION BASED)
    # ---------------------------------------------------------
    with login_tab2:
        st.subheader("🔍 Account Verification & Password Reset")
        st.caption("Enter your exact profile details to reset your password.")
        
        with st.form("forgot_password_form"):
            f_uid = st.text_input("User ID *")
            f_fullname = st.text_input("Full Name *")
            f_father = st.text_input("Father Name *")
            f_mobile = st.text_input("Registered Mobile Number *")
            
            st.write("---")
            f_new_pwd = st.text_input("New Password *", type="password")
            f_confirm_pwd = st.text_input("Confirm New Password *", type="password")

            if st.form_submit_button("🔄 Verify & Reset Password", use_container_width=True):
                if f_uid and f_fullname and f_father and f_mobile and f_new_pwd:
                    if f_new_pwd != f_confirm_pwd:
                        st.error("❌ New Password and Confirm Password do not match!")
                    else:
                        chk_val = run_query("""SELECT * FROM users 
                                               WHERE username=? AND TRIM(LOWER(full_name))=TRIM(LOWER(?)) 
                                               AND TRIM(LOWER(father_name))=TRIM(LOWER(?)) AND mobile=? AND role='Customer'""", 
                                            (f_uid, f_fullname, f_father, f_mobile))
                        if not chk_val.empty:
                            execute_db("UPDATE users SET password=?, is_first_login=0 WHERE username=?", (f_new_pwd, f_uid))
                            st.success("🎉 Verification successful! Password updated. You can now login in the User Login tab.")
                        else:
                            st.error("❌ Details mismatch! Please enter exact details provided during registration.")
                else:
                    st.warning("⚠️ All fields are mandatory for security verification.")

    # ---------------------------------------------------------
    # TAB 3: SEPARATE ADMIN LOGIN PORTAL
    # ---------------------------------------------------------
    with login_tab3:
        st.subheader("🛡️ Isolated Admin Login Window")
        with st.form("admin_login_form"):
            a_username = st.text_input("Admin Username", value="admin")
            a_password = st.text_input("Admin Passcode", type="password")
            if st.form_submit_button("🔌 Admin Login Override", use_container_width=True):
                chk_admin = run_query("SELECT * FROM users WHERE username=? AND password=? AND role='Official_Admin'", (a_username, a_password))
                if not chk_admin.empty:
                    admin_data = chk_admin.iloc[0].to_dict()
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = admin_data
                    st.rerun()
                else:
                    st.error("❌ Access Denied: Invalid Admin Credentials!")

# =========================================================
# 5. DASHBOARD WORKSPACE (USER OR ADMIN)
# =========================================================
else:
    user_id = st.session_state['user_info']['username']
    user_role = st.session_state['user_info'].get('role', 'Customer')
    full_name = st.session_state['user_info'].get('full_name', user_id)
    
    # Top Header
    head_col1, head_col2 = st.columns([3, 1])
    with head_col1:
        st.markdown(f"### 👤 Active Account: {full_name}")
        st.caption(f"Role: **{user_role}** | ID: `{user_id}`")
    
    with head_col2:
        if st.button("🚪 Logout Account", use_container_width=True, type="primary"):
            st.session_state['logged_in'] = False
            st.session_state['user_info'] = None
            st.session_state['force_password_change'] = False
            st.rerun()

    st.write("---")

    # =========================================================
    # A. ADMIN DASHBOARD WORKSPACE
    # =========================================================
    if user_role == "Official_Admin":
        st.success("🛡️ Welcome Admin! Master Control Active.")
        
        adm_t1, adm_t2, adm_t3, adm_t4 = st.tabs([
            "📊 Master Cashbook Ledger", 
            "👥 Registered Users List", 
            "➕ Add New User Account", 
            "🔒 Change Admin Password"
        ])

        with adm_t1:
            st.markdown('<div class="section-box"><h4>📊 All Users Master Cashbook Ledger</h4></div>', unsafe_allow_html=True)
            u_list = ["ALL"] + run_query("SELECT username FROM users WHERE role='Customer'")['username'].tolist()
            sel_u = st.selectbox("Filter By Client User:", u_list)
            
            if sel_u == "ALL":
                r_data = run_query("SELECT * FROM accounts ORDER BY id DESC")
            else:
                r_data = run_query("SELECT * FROM accounts WHERE username=? ORDER BY id DESC", (sel_u,))
            st.dataframe(r_data, use_container_width=True)

        with adm_t2:
            st.markdown('<div class="section-box"><h4>👥 Registered Merchant Directory</h4></div>', unsafe_allow_html=True)
            users_df = run_query("SELECT id, username, password, full_name, father_name, shop_name, mobile, email FROM users WHERE role='Customer'")
            st.dataframe(users_df, use_container_width=True)

        with adm_t3:
            st.markdown('<div class="section-box"><h4>➕ Register New Merchant User</h4></div>', unsafe_allow_html=True)
            with st.form("admin_create_user"):
                c_c1, c_c2 = st.columns(2)
                with c_c1:
                    fn = st.text_input("Full Name *")
                    fath = st.text_input("Father Name *")
                    shp = st.text_input("Shop Name *")
                    mob = st.text_input("Mobile No *")
                with c_c2:
                    em = st.text_input("Email ID")
                    pan = st.text_input("PAN Card")
                    adh = st.text_input("Aadhaar No")
                if st.form_submit_button("🚀 Create Account"):
                    if fn and mob and fath:
                        generated_uid = generate_auto_userid(fn, mob)
                        generated_pwd = generate_one_time_password(6)
                        execute_db("""INSERT INTO users 
                                      (username, password, role, is_approved, email, mobile, full_name, father_name, pan_card, aadhaar_no, shop_name, is_first_login) 
                                      VALUES (?, ?, 'Customer', 1, ?, ?, ?, ?, ?, ?, ?, 1)""", 
                                   (generated_uid, generated_pwd, em, mob, fn, fath, pan, adh, shp))
                        st.success(f"🎉 Created User! User ID: {generated_uid} | Temp Pass: {generated_pwd}")
                    else:
                        st.warning("⚠️ Full Name, Father Name & Mobile Required!")

        with adm_t4:
            st.markdown('<div class="section-box"><h4>🔒 Change Admin Security Password</h4></div>', unsafe_allow_html=True)
            with st.form("admin_change_pwd_form"):
                curr_adm_pass = st.text_input("Current Admin Password", type="password")
                new_adm_pass = st.text_input("New Admin Password", type="password")
                conf_adm_pass = st.text_input("Confirm New Password", type="password")
                
                if st.form_submit_button("💾 Save Admin Password"):
                    if curr_adm_pass and new_adm_pass and conf_adm_pass:
                        if new_adm_pass != conf_adm_pass:
                            st.error("❌ Passwords do not match!")
                        else:
                            chk_curr = run_query("SELECT * FROM users WHERE username=? AND password=?", (user_id, curr_adm_pass))
                            if not chk_curr.empty:
                                execute_db("UPDATE users SET password=? WHERE username=?", (new_adm_pass, user_id))
                                st.success("✅ Admin password updated successfully!")
                            else:
                                st.error("❌ Current password incorrect!")

    # =========================================================
    # B. REGULAR USER / MERCHANT DASHBOARD WORKSPACE
    # =========================================================
    else:
        b = calculate_exact_balances(user_id)

        # Dashboard Summary Cards
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"""<div class="metric-card"><div class="metric-title">💵 CASH BALANCE</div><div class="metric-value">₹{b['cash_closing']:,.2f}</div><div class="metric-sub">Opening: ₹{b['cash_op']:,.2f}</div></div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="metric-card"><div class="metric-title">🏦 BANK BALANCE</div><div class="metric-value" style="color:#a7f3d0;">₹{b['bank_closing']:,.2f}</div><div class="metric-sub">Opening: ₹{b['bank_op']:,.2f}</div></div>""", unsafe_allow_html=True)
        c3.markdown(f"""<div class="metric-card"><div class="metric-title">💼 SERVICES COMM.</div><div class="metric-value" style="color:#fde047;">₹{b['services_income']:,.2f}</div><div class="metric-sub">Total Earnings</div></div>""", unsafe_allow_html=True)
        c4.markdown(f"""<div class="metric-card"><div class="metric-title">🏺 GULLAK / PERSONAL</div><div class="metric-value" style="color:#f472b6;">₹{b['personal_gullak']:,.2f}</div><div class="metric-sub">Personal Expenses</div></div>""", unsafe_allow_html=True)

        st.write("---")

        # Feature Tabs
        ut1, ut2, ut3, ut4, ut5, ut6 = st.tabs([
            "➕ New Transaction", 
            "🔍 Customer Ledger & Slip", 
            "🛠️ Daily Services Log", 
            "📊 Analytics & Summary",
            "📋 Full Cashbook", 
            "⚙️ Opening Balances"
        ])

        # TAB 1: NEW TRANSACTION ENTRY
        with ut1:
            st.markdown('<div class="section-box"><h4>➕ AEPS / Cash Deposit / Withdrawal Entry</h4></div>', unsafe_allow_html=True)
            with st.form("main_txn_form", clear_on_submit=True):
                fc1, fc2 = st.columns(2)
                with fc1:
                    t_account = st.selectbox("Account Type *", ["Bank Account", "Cash"])
                    if t_account == "Bank Account":
                        t_type = st.selectbox("Transaction Type *", [
                            "Customer AEPS Withdrawal (बैंक बढ़ा / नकद घटा)",
                            "Customer Deposit / Money Transfer (नकद बढ़ा / बैंक घटा)",
                            "Self Bank Cash Withdrawal (बैंक घटा / नकद बढ़ा)",
                            "Self Bank Cash Deposit (बैंक बढ़ा / नकद घटा)"
                        ])
                    else:
                        t_type = st.selectbox("Transaction Type *", [
                            "Deposit (जमा)", 
                            "Withdrawal (निकासी)", 
                            "Customer Due Payment Received (उधार रिकवरी - Cash +)",
                            "Personal Use / Gullak (निजी खर्च/गुल्लक)"
                        ])
                    
                    t_amount = st.number_input("Amount (₹) *", min_value=0.0, step=100.0)
                    t_pay_mode = st.selectbox("Payment Method", ["Cash", "UPI / QR", "AEPS", "IMPS/NEFT", "Card Machine"])
                    t_tx_id = st.text_input("Txn / UTR / Reference No")
                
                with fc2:
                    t_cname = st.text_input("Customer Name")
                    t_aadhaar = st.text_input("Aadhaar Last 4 Digits", max_chars=4)
                    
                    if t_type == "Customer Due Payment Received (उधार रिकवरी - Cash +)":
                        t_due = 0.0
                        st.info("💡 Recovering Due: Cash increases, Pending Udhar decreases.")
                    else:
                        t_due = st.number_input("New Due / Udhar (₹)", min_value=0.0, value=0.0, step=50.0)
                        
                    t_desc = st.text_input("Description / Notes")
                    t_date = st.date_input("Date", datetime.now())

                if st.form_submit_button("✅ Save Transaction", use_container_width=True):
                    if t_amount > 0:
                        d_str = f"{t_date.strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M')}"
                        execute_db("""INSERT INTO accounts 
                                      (username, date, type, amount, account_type, tx_id, cust_name, cust_aadhaar_last4, cust_due_amount, payment_mode, description) 
                                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                                   (user_id, d_str, t_type, t_amount, t_account, t_tx_id, t_cname, t_aadhaar, t_due, t_pay_mode, t_desc))
                        st.success("🎉 Transaction Successfully Recorded!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Enter a valid amount!")

        # TAB 2: CUSTOMER LEDGER & PRINT RECEIPT GENERATOR
        with ut2:
            st.markdown('<div class="section-box"><h4>🔍 Search Customer Ledger & Generate Slip</h4></div>', unsafe_allow_html=True)
            sc1, sc2 = st.columns(2)
            s_adh = sc1.text_input("Aadhaar Last 4 Digits:")
            s_nm = sc2.text_input("Customer Name:")

            if s_adh or s_nm:
                query = "SELECT id, date, type, amount, cust_name, cust_aadhaar_last4, cust_due_amount, payment_mode, tx_id, description FROM accounts WHERE username=? AND "
                params = [user_id]
                if s_adh:
                    query += "cust_aadhaar_last4 LIKE ?"
                    params.append(f"%{s_adh}%")
                else:
                    query += "cust_name LIKE ?"
                    params.append(f"%{s_nm}%")
                
                cust_df = run_query(query, tuple(params))
                if not cust_df.empty:
                    st.dataframe(cust_df, use_container_width=True)
                    
                    # Receipt Generator
                    st.subheader("🧾 Printable Receipt Generator")
                    sel_tx_id = st.selectbox("Select Txn ID for Slip:", cust_df['id'].tolist())
                    tx_row = cust_df[cust_df['id'] == sel_tx_id].iloc[0]
                    
                    st.markdown(f"""
                    <div class="receipt-box">
                    <h3 style="text-align:center;">{st.session_state['user_info'].get('shop_name', 'DIGITAL STORE')}</h3>
                    <p style="text-align:center;">Payment Slip</p>
                    <hr>
                    <b>Txn ID:</b> TXN#{tx_row['id']} &nbsp;&nbsp;&nbsp; <b>Date:</b> {tx_row['date']}<br>
                    <b>Customer:</b> {tx_row['cust_name'] if tx_row['cust_name'] else 'N/A'}<br>
                    <b>Aadhaar (Last 4):</b> {tx_row['cust_aadhaar_last4'] if tx_row['cust_aadhaar_last4'] else 'N/A'}<br>
                    <b>Type:</b> {tx_row['type']}<br>
                    <b>Mode:</b> {tx_row['payment_mode']}<br>
                    <hr>
                    <h2 style="color:#0284c7;">Amount: ₹{tx_row['amount']:,.2f}</h2>
                    <b>Pending Udhar:</b> ₹{tx_row['cust_due_amount']:,.2f}<br>
                    <hr>
                    <p style="text-align:center;">Thank You!</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("ℹ️ No Records Found!")

        # TAB 3: DAILY SERVICES LOG
        with ut3:
            st.markdown('<div class="section-box"><h4>🛠️ Daily Online Services Tracker</h4></div>', unsafe_allow_html=True)
            with st.form("services_entry", clear_on_submit=True):
                svc1, svc2 = st.columns(2)
                with svc1:
                    s_name = st.selectbox("Service *", ["PMJJBY", "PMSBY", "APY", "KYC", "PAN Card", "Aadhaar Work", "Money Transfer Fee", "Recharge", "Other"])
                    s_ref = st.text_input("Customer Ref / Mobile *")
                with svc2:
                    s_inc = st.number_input("Commission / Fee (₹) *", min_value=0.0)
                    s_nt = st.text_input("Note")
                if st.form_submit_button("💼 Save Service Record"):
                    if s_ref and s_inc >= 0:
                        execute_db("INSERT INTO daily_services (username, date, service_name, ref_no, income_amount, notes) VALUES (?, ?, ?, ?, ?, ?)",
                                   (user_id, datetime.now().strftime('%Y-%m-%d %H:%M'), s_name, s_ref, s_inc, s_nt))
                        st.success("✅ Service Entry Saved!")
                        st.rerun()

            st.dataframe(run_query("SELECT date, service_name, ref_no, income_amount, notes FROM daily_services WHERE username=? ORDER BY id DESC", (user_id,)), use_container_width=True)

        # TAB 4: ANALYTICS & SUMMARY
        with ut4:
            st.markdown('<div class="section-box"><h4>📊 Business Analytics & Chart Summary</h4></div>', unsafe_allow_html=True)
            acc_data = run_query("SELECT type, amount, payment_mode FROM accounts WHERE username=?", (user_id,))
            if not acc_data.empty:
                st.subheader("💳 Payment Method Distribution")
                pay_summary = acc_data.groupby('payment_mode')['amount'].sum().reset_index()
                st.bar_chart(pay_summary.set_index('payment_mode'))
            else:
                st.info("ℹ️ Analytics available after adding transactions.")

        # TAB 5: FULL HISTORY
        with ut5:
            st.markdown('<div class="section-box"><h4>📋 Complete Transaction Cashbook</h4></div>', unsafe_allow_html=True)
            all_txns = run_query("SELECT id, date, account_type, type, amount, cust_name, cust_aadhaar_last4, cust_due_amount, payment_mode, tx_id, description FROM accounts WHERE username=? ORDER BY id DESC", (user_id,))
            st.dataframe(all_txns, use_container_width=True)
            st.download_button("📥 Export Cashbook Excel", data=convert_df_to_excel(all_txns), file_name="Complete_Cashbook.xlsx")

        # TAB 6: OPENING BALANCES
        with ut6:
            st.markdown('<div class="section-box"><h4>⚙️ Account Opening Balances Setup</h4></div>', unsafe_allow_html=True)
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
                    st.success("✅ Opening Balances Saved!")
                    st.rerun()
