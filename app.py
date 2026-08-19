import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import io
import random
import string

# =========================================================
# 1. DATABASE INITIALIZATION & SAFE MIGRATIONS
# =========================================================
DB_NAME = "local_cashbook.db"

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    
    # Base Users Table
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
                    is_first_login INTEGER DEFAULT 1,
                    kyc_status TEXT DEFAULT 'Pending',
                    is_paid INTEGER DEFAULT 0,
                    created_at TEXT,
                    demo_expiry_date TEXT
                )''')
    
    # Dynamic Column Migration
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()]
    new_cols = {
        "father_name": "TEXT",
        "kyc_status": "TEXT DEFAULT 'Pending'",
        "is_paid": "INTEGER DEFAULT 0",
        "created_at": "TEXT",
        "demo_expiry_date": "TEXT"
    }
    for col_name, col_type in new_cols.items():
        if col_name not in existing_cols:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")

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
    
    # Force Reset Admin Account
    c.execute("DELETE FROM users WHERE username='admin'")
    c.execute("""INSERT INTO users 
                 (username, password, role, is_approved, is_first_login, full_name, is_paid, kyc_status) 
                 VALUES ('admin', 'admin123', 'Official_Admin', 1, 0, 'System Administrator', 1, 'Approved')""")
    
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
    .receipt-thermal {
        width: 280px;
        background: #fff;
        color: #000;
        padding: 12px;
        font-family: 'Courier New', Courier, monospace;
        font-size: 12px;
        border: 1px solid #000;
        margin: auto;
    }
    @media print {
        body * { visibility: hidden; }
        .receipt-thermal, .receipt-thermal * { visibility: visible; }
        .receipt-thermal { position: absolute; left: 0; top: 0; width: 100%; }
    }
    </style>
""", unsafe_allow_html=True)

# Session States Initialization
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None
if 'force_password_change' not in st.session_state:
    st.session_state['force_password_change'] = False

# =========================================================
# 4. LOGIN & AUTHENTICATION PORTALS
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
        "👤 Merchant Login", 
        "🔑 Forgot Password", 
        "🛡️ Official Admin Portal"
    ])

    # User Login
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

    # Forgot Password
    with login_tab2:
        st.subheader("🔍 Account Verification & Password Reset")
        with st.form("forgot_password_form"):
            f_uid = st.text_input("User ID *")
            f_fullname = st.text_input("Full Name *")
            f_father = st.text_input("Father Name *")
            f_mobile = st.text_input("Registered Mobile Number *")
            f_new_pwd = st.text_input("New Password *", type="password")
            f_confirm_pwd = st.text_input("Confirm New Password *", type="password")

            if st.form_submit_button("🔄 Reset Password", use_container_width=True):
                if f_new_pwd == f_confirm_pwd:
                    chk_val = run_query("SELECT * FROM users WHERE username=? AND LOWER(full_name)=LOWER(?) AND LOWER(father_name)=LOWER(?) AND mobile=?", 
                                        (f_uid, f_fullname, f_father, f_mobile))
                    if not chk_val.empty:
                        execute_db("UPDATE users SET password=?, is_first_login=0 WHERE username=?", (f_new_pwd, f_uid))
                        st.success("🎉 Verification successful! Password updated.")
                    else:
                        st.error("❌ Details Mismatch!")
                else:
                    st.error("❌ Passwords do not match!")

    # Admin Login
    with login_tab3:
        st.subheader("🛡️ Isolated Admin Login Window")
        with st.form("admin_login_form"):
            a_username = st.text_input("Admin Username", value="admin")
            a_password = st.text_input("Admin Passcode", type="password")
            if st.form_submit_button("🔌 Admin Login", use_container_width=True):
                chk_admin = run_query("SELECT * FROM users WHERE username=? AND password=? AND role='Official_Admin'", (a_username, a_password))
                if not chk_admin.empty:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = chk_admin.iloc[0].to_dict()
                    st.rerun()
                else:
                    st.error("❌ Invalid Admin Credentials!")

# =========================================================
# 5. DASHBOARD WORKSPACE (USER / ADMIN)
# =========================================================
else:
    user_id = st.session_state['user_info']['username']
    user_role = st.session_state['user_info'].get('role', 'Customer')
    full_name = st.session_state['user_info'].get('full_name', user_id)
    
    u_fresh = run_query("SELECT * FROM users WHERE username=?", (user_id,)).iloc[0].to_dict()
    
    head_col1, head_col2 = st.columns([3, 1])
    with head_col1:
        st.markdown(f"### 👤 Active Account: {full_name}")
        st.caption(f"Role: **{user_role}** | ID: `{user_id}`")
    
    with head_col2:
        if st.button("🚪 Logout Account", use_container_width=True, type="primary"):
            st.session_state['logged_in'] = False
            st.session_state['user_info'] = None
            st.rerun()

    st.write("---")

    # =========================================================
    # A. OFFICIAL ADMIN DASHBOARD
    # =========================================================
    if user_role == "Official_Admin":
        st.success("🛡️ Official Admin Panel Active")
        
        adm_t1, adm_t2, adm_t3, adm_t4, adm_t5 = st.tabs([
            "📋 Users & KYC Approvals", 
            "⏳ Manage Demo & Extensions", 
            "➕ Add New User", 
            "📊 Master Cashbook Ledger",
            "🔒 Admin Security"
        ])

        with adm_t1:
            st.subheader("👥 User Management & License Activation")
            all_users = run_query("SELECT id, username, full_name, mobile, shop_name, kyc_status, is_paid, demo_expiry_date FROM users WHERE role='Customer'")
            st.dataframe(all_users, use_container_width=True)
            
            st.write("---")
            st.markdown("#### ⚡ Activate Paid Version / Approve KYC")
            if not all_users.empty:
                c_u = st.selectbox("Select User ID:", all_users['username'].tolist())
                u_row = all_users[all_users['username'] == c_u].iloc[0]
                ac1, ac2 = st.columns(2)
                with ac1:
                    new_kyc = st.selectbox("Update KYC Status:", ["Pending", "Approved", "Rejected"], index=0 if u_row['kyc_status'] == 'Pending' else 1)
                with ac2:
                    new_paid = st.selectbox("Paid Membership:", [0, 1], format_func=lambda x: "Active (Paid User)" if x == 1 else "Demo / Unpaid", index=int(u_row['is_paid']))
                
                if st.button("💾 Update Subscription & KYC"):
                    execute_db("UPDATE users SET kyc_status=?, is_paid=? WHERE username=?", (new_kyc, new_paid, c_u))
                    st.success(f"✅ User {c_u} updated successfully!")
                    st.rerun()

        with adm_t2:
            st.subheader("⏳ Extend Demo Validity")
            if not all_users.empty:
                sel_demo_user = st.selectbox("Select Demo User to Extend:", all_users['username'].tolist(), key="demo_ext_sel")
                d_user_data = all_users[all_users['username'] == sel_demo_user].iloc[0]
                curr_exp = d_user_data['demo_expiry_date'] if d_user_data['demo_expiry_date'] else datetime.now().strftime('%Y-%m-%d')
                st.info(f"Current Demo Expiry Date: **{curr_exp}**")
                
                add_days = st.number_input("Add Extra Demo Days:", min_value=1, max_value=60, value=3)
                if st.button("🚀 Extend Demo Period"):
                    curr_date_dt = datetime.strptime(curr_exp, '%Y-%m-%d') if d_user_data['demo_expiry_date'] else datetime.now()
                    new_exp_dt = (curr_date_dt + timedelta(days=add_days)).strftime('%Y-%m-%d')
                    execute_db("UPDATE users SET demo_expiry_date=? WHERE username=?", (new_exp_dt, sel_demo_user))
                    st.success(f"🎉 Demo validity extended till {new_exp_dt} for user {sel_demo_user}!")
                    st.rerun()

        with adm_t3:
            st.subheader("➕ Register New Merchant User")
            with st.form("admin_create_user"):
                fn = st.text_input("Full Name *")
                fath = st.text_input("Father Name *")
                shp = st.text_input("Shop Name *")
                mob = st.text_input("Mobile No *")
                em = st.text_input("Email ID")
                pan = st.text_input("PAN Card")
                adh = st.text_input("Aadhaar No")
                
                if st.form_submit_button("🚀 Create 3-Day Demo Account"):
                    if fn and mob and fath:
                        generated_uid = generate_auto_userid(fn, mob)
                        generated_pwd = generate_one_time_password(6)
                        created_at = datetime.now().strftime('%Y-%m-%d')
                        demo_expiry = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
                        
                        execute_db("""INSERT INTO users 
                                      (username, password, role, is_approved, email, mobile, full_name, father_name, pan_card, aadhaar_no, shop_name, is_first_login, kyc_status, is_paid, created_at, demo_expiry_date) 
                                      VALUES (?, ?, 'Customer', 1, ?, ?, ?, ?, ?, ?, ?, 1, 'Pending', 0, ?, ?)""", 
                                   (generated_uid, generated_pwd, em, mob, fn, fath, pan, adh, shp, created_at, demo_expiry))
                        st.success(f"🎉 Account Created! ID: {generated_uid} | Pass: {generated_pwd}")
                    else:
                        st.warning("⚠️ Full Name, Father Name & Mobile Required!")

        with adm_t4:
            st.subheader("📊 All Users Master Cashbook Ledger")
            u_list = ["ALL"] + run_query("SELECT username FROM users WHERE role='Customer'")['username'].tolist()
            sel_u = st.selectbox("Filter By Client User:", u_list)
            r_data = run_query("SELECT * FROM accounts ORDER BY id DESC") if sel_u == "ALL" else run_query("SELECT * FROM accounts WHERE username=? ORDER BY id DESC", (sel_u,))
            st.dataframe(r_data, use_container_width=True)

        with adm_t5:
            st.subheader("🔒 Change Admin Security Password")
            with st.form("admin_pwd_form"):
                cp = st.text_input("Current Password", type="password")
                np = st.text_input("New Password", type="password")
                if st.form_submit_button("💾 Save Password"):
                    chk = run_query("SELECT * FROM users WHERE username=? AND password=?", (user_id, cp))
                    if not chk.empty:
                        execute_db("UPDATE users SET password=? WHERE username=?", (np, user_id))
                        st.success("✅ Password Updated!")
                    else:
                        st.error("❌ Current Password Incorrect!")

    # =========================================================
    # B. REGULAR USER / MERCHANT DASHBOARD
    # =========================================================
    else:
        today_str = datetime.now().strftime('%Y-%m-%d')
        demo_expiry_str = u_fresh.get('demo_expiry_date', today_str)
        is_paid = u_fresh.get('is_paid', 0)
        is_expired = (today_str > demo_expiry_str) if demo_expiry_str else False

        if is_paid == 0 and is_expired:
            st.error(f"🚨 Demo Period Expired on {demo_expiry_str}!")
            st.warning("Aapka 3 days ka demo version khatam ho chuka hai. Kripya Admin se extension lein.")
            with st.form("kyc_submit_form"):
                k_pan = st.text_input("PAN Card Number", value=u_fresh.get('pan_card', ''))
                k_adh = st.text_input("Aadhaar Number", value=u_fresh.get('aadhaar_no', ''))
                k_shop = st.text_input("Shop Name", value=u_fresh.get('shop_name', ''))
                if st.form_submit_button("📩 Submit KYC for Paid Approval"):
                    execute_db("UPDATE users SET pan_card=?, aadhaar_no=?, shop_name=?, kyc_status='Pending' WHERE username=?", (k_pan, k_adh, k_shop, user_id))
                    st.success("✅ KYC Submitted!")
                    st.rerun()

        else:
            b = calculate_exact_balances(user_id)

            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"""<div class="metric-card"><div class="metric-title">💵 CASH BALANCE</div><div class="metric-value">₹{b['cash_closing']:,.2f}</div><div class="metric-sub">Opening: ₹{b['cash_op']:,.2f}</div></div>""", unsafe_allow_html=True)
            c2.markdown(f"""<div class="metric-card"><div class="metric-title">🏦 BANK BALANCE</div><div class="metric-value" style="color:#a7f3d0;">₹{b['bank_closing']:,.2f}</div><div class="metric-sub">Opening: ₹{b['bank_op']:,.2f}</div></div>""", unsafe_allow_html=True)
            c3.markdown(f"""<div class="metric-card"><div class="metric-title">💼 SERVICES COMM.</div><div class="metric-value" style="color:#fde047;">₹{b['services_income']:,.2f}</div><div class="metric-sub">Total Earnings</div></div>""", unsafe_allow_html=True)
            c4.markdown(f"""<div class="metric-card"><div class="metric-title">🏺 GULLAK / PERSONAL</div><div class="metric-value" style="color:#f472b6;">₹{b['personal_gullak']:,.2f}</div><div class="metric-sub">Personal Expenses</div></div>""", unsafe_allow_html=True)

            st.write("---")

            ut1, ut2, ut3, ut4, ut5, ut6 = st.tabs([
                "➕ New Entry", 
                "📖 Customer Ledger & Print", 
                "✏️ Edit / Delete Entry", 
                "📋 Full Cashbook & Export", 
                "🛠️ Daily Services Log",
                "⚙️ Settings & KYC"
            ])

            # TAB 1: NEW TRANSACTION ENTRY
            with ut1:
                st.markdown('<div class="section-box"><h4>➕ New Cashbook Transaction</h4></div>', unsafe_allow_html=True)
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
                        t_tx_id = st.text_input("Txn / UTR Ref No")
                    
                    with fc2:
                        t_cname = st.text_input("Customer Name")
                        t_aadhaar = st.text_input("Aadhaar Last 4 Digits", max_chars=4)
                        t_due = st.number_input("New Udhar / Due Amount (₹)", min_value=0.0, step=50.0) if t_type != "Customer Due Payment Received (उधार रिकवरी - Cash +)" else 0.0
                        t_desc = st.text_input("Description / Notes")
                        t_date = st.date_input("Date", datetime.now())

                    if st.form_submit_button("✅ Save Transaction", use_container_width=True):
                        if t_amount > 0:
                            d_str = f"{t_date.strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M')}"
                            execute_db("""INSERT INTO accounts 
                                          (username, date, type, amount, account_type, tx_id, cust_name, cust_aadhaar_last4, cust_due_amount, payment_mode, description) 
                                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                                       (user_id, d_str, t_type, t_amount, t_account, t_tx_id, t_cname, t_aadhaar, t_due, t_pay_mode, t_desc))
                            st.success("🎉 Entry Recorded Successfully!")
                            st.rerun()

            # TAB 2: CUSTOMER LEDGER & PRINT SLIP
            with ut2:
                st.markdown('<div class="section-box"><h4>📖 Customer Ledger, Thermal Print & Slip</h4></div>', unsafe_allow_html=True)
                sc1, sc2 = st.columns(2)
                s_cname = sc1.text_input("Search Customer Name:")
                s_adh = sc2.text_input("Search Aadhaar (Last 4):")

                query = "SELECT * FROM accounts WHERE username=?"
                params = [user_id]
                if s_cname:
                    query += " AND cust_name LIKE ?"
                    params.append(f"%{s_cname}%")
                if s_adh:
                    query += " AND cust_aadhaar_last4 LIKE ?"
                    params.append(f"%{s_adh}%")

                cust_df = run_query(query, tuple(params))
                if not cust_df.empty:
                    st.dataframe(cust_df, use_container_width=True)
                    
                    st.write("---")
                    st.subheader("🧾 Print Transaction Slip / Thermal Receipt")
                    sel_tx_id = st.selectbox("Select Txn ID to Print:", cust_df['id'].tolist())
                    tx_row = cust_df[cust_df['id'] == sel_tx_id].iloc[0]

                    # Thermal Printable Box
                    st.markdown(f"""
                    <div class="receipt-thermal">
                        <div style="text-align:center;"><b>{u_fresh.get('shop_name', 'DIGITAL STORE')}</b></div>
                        <div style="text-align:center;">PAYMENT SLIP</div>
                        --------------------------------<br>
                        <b>Txn ID:</b> #{tx_row['id']}<br>
                        <b>Date:</b> {tx_row['date']}<br>
                        <b>Customer:</b> {tx_row['cust_name'] if tx_row['cust_name'] else 'N/A'}<br>
                        <b>Aadhaar (Last 4):</b> {tx_row['cust_aadhaar_last4'] if tx_row['cust_aadhaar_last4'] else 'N/A'}<br>
                        --------------------------------<br>
                        <b>Type:</b> {tx_row['type']}<br>
                        <b>Mode:</b> {tx_row['payment_mode']}<br>
                        <div style="font-size:14px; font-weight:bold; margin: 5px 0;">AMOUNT: ₹{tx_row['amount']:,.2f}</div>
                        <b>Pending Udhar:</b> ₹{tx_row['cust_due_amount']:,.2f}<br>
                        --------------------------------<br>
                        <div style="text-align:center;">Thank You! Visit Again</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.caption("💡 Use browser **Ctrl+P** to print receipt via 2-inch/3-inch Thermal Printer.")
                else:
                    st.info("ℹ️ No customer transactions found.")

            # TAB 3: EDIT & DELETE TRANSACTION
            with ut3:
                st.markdown('<div class="section-box"><h4>✏️ Edit or Delete Cashbook Transactions</h4></div>', unsafe_allow_html=True)
                tx_list = run_query("SELECT id, date, cust_name, type, amount FROM accounts WHERE username=? ORDER BY id DESC", (user_id,))
                
                if not tx_list.empty:
                    sel_edit_id = st.selectbox("Select Transaction ID to Modify:", tx_list['id'].tolist())
                    curr_tx = run_query("SELECT * FROM accounts WHERE id=?", (sel_edit_id,)).iloc[0]

                    with st.form("edit_tx_form"):
                        e1, e2 = st.columns(2)
                        with e1:
                            e_amount = e1.number_input("Amount (₹)", value=float(curr_tx['amount']))
                            e_cname = e1.text_input("Customer Name", value=str(curr_tx['cust_name'] or ''))
                            e_adh = e1.text_input("Aadhaar Last 4", value=str(curr_tx['cust_aadhaar_last4'] or ''))
                        with e2:
                            e_due = e2.number_input("Udhar / Due Amount (₹)", value=float(curr_tx['cust_due_amount']))
                            e_desc = e2.text_input("Description", value=str(curr_tx['description'] or ''))
                            e_mode = e2.selectbox("Payment Mode", ["Cash", "UPI / QR", "AEPS", "IMPS/NEFT", "Card Machine"], index=0)

                        btn_update = st.form_submit_button("💾 Update Transaction")
                        if btn_update:
                            execute_db("""UPDATE accounts 
                                          SET amount=?, cust_name=?, cust_aadhaar_last4=?, cust_due_amount=?, description=?, payment_mode=? 
                                          WHERE id=?""", 
                                       (e_amount, e_cname, e_adh, e_due, e_desc, e_mode, sel_edit_id))
                            st.success("✅ Transaction Updated!")
                            st.rerun()

                    st.write("---")
                    if st.button("🗑️ Delete This Transaction", type="primary"):
                        execute_db("DELETE FROM accounts WHERE id=?", (sel_edit_id,))
                        st.success("❌ Transaction Deleted!")
                        st.rerun()

            # TAB 4: FULL CASHBOOK & PDF/EXCEL EXPORT
            with ut4:
                st.markdown('<div class="section-box"><h4>📋 Full Cashbook Ledger & Export Options</h4></div>', unsafe_allow_html=True)
                all_txns = run_query("SELECT id, date, account_type, type, amount, cust_name, cust_aadhaar_last4, cust_due_amount, payment_mode, tx_id, description FROM accounts WHERE username=? ORDER BY id DESC", (user_id,))
                st.dataframe(all_txns, use_container_width=True)
                
                exp_c1, exp_c2 = st.columns(2)
                with exp_c1:
                    st.download_button("📥 Export Cashbook (Excel)", data=convert_df_to_excel(all_txns), file_name="Complete_Cashbook.xlsx", use_container_width=True)
                with exp_c2:
                    st.download_button("📄 Export Cashbook (CSV / PDF Ready)", data=all_txns.to_csv(index=False).encode('utf-8'), file_name="Complete_Cashbook.csv", mime="text/csv", use_container_width=True)

            # TAB 5: DAILY SERVICES LOG
            with ut5:
                st.markdown('<div class="section-box"><h4>🛠️ Daily Services & Commission Income</h4></div>', unsafe_allow_html=True)
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

            # TAB 6: SETTINGS & OPENING BALANCES
            with ut6:
                st.markdown('<div class="section-box"><h4>⚙️ Account Settings & Opening Balances</h4></div>', unsafe_allow_html=True)
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
