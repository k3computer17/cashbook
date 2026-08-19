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
    
    # Safe Column Migrations for existing database compatibility
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

    # Daily Services & Custom Income Log Table
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
    
    # Default Admin Setup
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
        df.to_excel(writer, index=False, sheet_name='Cashbook_Report')
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

    cash_dep = float(cash_df[cash_df['type'] == 'Deposit (जमा / Income)']['amount'].sum()) if not cash_df.empty else 0.0
    cash_wth = float(cash_df[cash_df['type'] == 'Expense / Withdrawal (खर्च / निकासी)']['amount'].sum()) if not cash_df.empty else 0.0
    personal_gullak = float(cash_df[cash_df['type'] == 'Personal Use / Gullak (निजी खर्च)']['amount'].sum()) if not cash_df.empty else 0.0
    due_recovered_cash = float(cash_df[cash_df['type'] == 'Customer Due Payment Received (उधार रिकवरी +)']['amount'].sum()) if not cash_df.empty else 0.0
    
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
# 3. PAGE CONFIGURATION
# =========================================================
st.set_page_config(page_title="BC Csp Cashbook", page_icon="🏦", layout="wide")

st.markdown("""
    <style>
    .metric-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px;
        color: white;
    }
    .metric-title { font-size: 0.85rem; color: #94a3b8; font-weight: 600; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #38bdf8; }
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
# 4. AUTHENTICATION & LOGIN
# =========================================================
if st.session_state['force_password_change']:
    st.warning("🔒 First Time Login: Password Update Required")
    with st.form("first_pwd_form"):
        np1 = st.text_input("New Password *", type="password")
        np2 = st.text_input("Confirm New Password *", type="password")
        if st.form_submit_button("💾 Save Password"):
            if np1 and np1 == np2:
                u_id = st.session_state['user_info']['username']
                execute_db("UPDATE users SET password=?, is_first_login=0 WHERE username=?", (np1, u_id))
                st.success("✅ Password updated!")
                st.session_state['force_password_change'] = False
                st.session_state['user_info']['is_first_login'] = 0
                st.rerun()
            else:
                st.error("❌ Passwords do not match!")

elif not st.session_state['logged_in']:
    st.title("🏦 BC Merchant Cashbook & Ledger")
    
    t_login, t_forgot, t_admin = st.tabs(["👤 Merchant Login", "🔑 Forgot Password", "🛡️ Admin Portal"])

    with t_login:
        with st.form("user_login"):
            ul_user = st.text_input("User ID")
            ul_pass = st.text_input("Password", type="password")
            if st.form_submit_button("🔑 Login", use_container_width=True):
                res = run_query("SELECT * FROM users WHERE username=? AND password=? AND role='Customer'", (ul_user, ul_pass))
                if not res.empty:
                    u_data = res.iloc[0].to_dict()
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = u_data
                    if u_data.get('is_first_login') == 1:
                        st.session_state['force_password_change'] = True
                    st.rerun()
                else:
                    st.error("❌ Invalid User ID or Password!")

    with t_forgot:
        with st.form("forgot_pass"):
            fp_uid = st.text_input("User ID *")
            fp_fn = st.text_input("Full Name *")
            fp_fath = st.text_input("Father Name *")
            fp_mob = st.text_input("Mobile Number *")
            fp_np1 = st.text_input("New Password *", type="password")
            fp_np2 = st.text_input("Confirm New Password *", type="password")
            if st.form_submit_button("🔄 Reset Password", use_container_width=True):
                if fp_np1 == fp_np2:
                    chk = run_query("SELECT * FROM users WHERE username=? AND LOWER(full_name)=LOWER(?) AND LOWER(father_name)=LOWER(?) AND mobile=?", 
                                    (fp_uid, fp_fn, fp_fath, fp_mob))
                    if not chk.empty:
                        execute_db("UPDATE users SET password=?, is_first_login=0 WHERE username=?", (fp_np1, fp_uid))
                        st.success("🎉 Reset successful! Please log in.")
                    else:
                        st.error("❌ Details Mismatch!")
                else:
                    st.error("❌ Passwords do not match!")

    with t_admin:
        with st.form("admin_login"):
            ad_u = st.text_input("Admin Username", value="admin")
            ad_p = st.text_input("Admin Passcode", type="password")
            if st.form_submit_button("🔌 Admin Login", use_container_width=True):
                chk = run_query("SELECT * FROM users WHERE username=? AND password=? AND role='Official_Admin'", (ad_u, ad_p))
                if not chk.empty:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = chk.iloc[0].to_dict()
                    st.rerun()
                else:
                    st.error("❌ Invalid Admin Credentials!")

# =========================================================
# 5. WORKSPACE
# =========================================================
else:
    user_id = st.session_state['user_info']['username']
    user_role = st.session_state['user_info'].get('role', 'Customer')
    full_name = st.session_state['user_info'].get('full_name', user_id)
    
    u_fresh = run_query("SELECT * FROM users WHERE username=?", (user_id,)).iloc[0].to_dict()
    
    hc1, hc2 = st.columns([3, 1])
    hc1.markdown(f"### 👤 Welcome, {full_name} (`{user_id}`)")
    if hc2.button("🚪 Logout", type="primary"):
        st.session_state['logged_in'] = False
        st.session_state['user_info'] = None
        st.rerun()

    st.write("---")

    if user_role == "Official_Admin":
        st.success("🛡️ System Admin Panel Active")
        at1, at2, at3, at4 = st.tabs(["👥 User KYC Approvals", "⏳ Demo Validity", "➕ Register User", "📊 All Txns"])

        with at1:
            all_u = run_query("SELECT id, username, full_name, father_name, mobile, shop_name, kyc_status, is_paid, demo_expiry_date FROM users WHERE role='Customer'")
            st.dataframe(all_u, use_container_width=True)
            if not all_u.empty:
                sel_u = st.selectbox("User:", all_u['username'].tolist())
                row_u = all_u[all_u['username'] == sel_u].iloc[0]
                nk = st.selectbox("KYC Status:", ["Pending", "Approved", "Rejected"], index=0 if row_u['kyc_status'] == 'Pending' else 1)
                npd = st.selectbox("Paid Account:", [0, 1], format_func=lambda x: "Yes" if x == 1 else "No", index=int(row_u['is_paid']))
                if st.button("💾 Update Status"):
                    execute_db("UPDATE users SET kyc_status=?, is_paid=? WHERE username=?", (nk, npd, sel_u))
                    st.success("✅ Saved!")
                    st.rerun()

        with at2:
            if not all_u.empty:
                s_du = st.selectbox("Select User:", all_u['username'].tolist(), key="demo_sel")
                d_row = all_u[all_u['username'] == s_du].iloc[0]
                cur_exp = d_row['demo_expiry_date'] if d_row['demo_expiry_date'] else datetime.now().strftime('%Y-%m-%d')
                st.info(f"Current Expiry: {cur_exp}")
                ext_days = st.number_input("Add Days:", min_value=1, max_value=90, value=7)
                if st.button("🚀 Extend Demo"):
                    c_dt = datetime.strptime(cur_exp, '%Y-%m-%d') if d_row['demo_expiry_date'] else datetime.now()
                    n_dt = (c_dt + timedelta(days=ext_days)).strftime('%Y-%m-%d')
                    execute_db("UPDATE users SET demo_expiry_date=? WHERE username=?", (n_dt, s_du))
                    st.success(f"🎉 Extended till {n_dt}!")
                    st.rerun()

        with at3:
            with st.form("create_usr"):
                fn = st.text_input("Full Name *")
                fath = st.text_input("Father Name *")
                shp = st.text_input("Shop Name *")
                mob = st.text_input("Mobile No *")
                pan = st.text_input("PAN Card")
                adh = st.text_input("Aadhaar No")
                if st.form_submit_button("🚀 Create User"):
                    if fn and fath and mob:
                        guid = generate_auto_userid(fn, mob)
                        gpwd = generate_one_time_password(6)
                        c_at = datetime.now().strftime('%Y-%m-%d')
                        d_exp = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
                        execute_db("""INSERT INTO users 
                                      (username, password, role, is_approved, mobile, full_name, father_name, pan_card, aadhaar_no, shop_name, is_first_login, kyc_status, is_paid, created_at, demo_expiry_date) 
                                      VALUES (?, ?, 'Customer', 1, ?, ?, ?, ?, ?, ?, 1, 'Pending', 0, ?, ?)""", 
                                   (guid, gpwd, mob, fn, fath, pan, adh, shp, c_at, d_exp))
                        st.success(f"🎉 User Created! ID: {guid} | Password: {gpwd}")
                    else:
                        st.warning("⚠️ Full Name, Father Name & Mobile required!")

        with at4:
            st.dataframe(run_query("SELECT * FROM accounts ORDER BY id DESC"), use_container_width=True)

    else:
        b = calculate_exact_balances(user_id)

        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f"""<div class="metric-card"><div class="metric-title">💵 CASH IN HAND</div><div class="metric-value">₹{b['cash_closing']:,.2f}</div></div>""", unsafe_allow_html=True)
        m2.markdown(f"""<div class="metric-card"><div class="metric-title">🏦 BANK BALANCE</div><div class="metric-value" style="color:#a7f3d0;">₹{b['bank_closing']:,.2f}</div></div>""", unsafe_allow_html=True)
        m3.markdown(f"""<div class="metric-card"><div class="metric-title">💼 DAILY SERVICES / INCOME</div><div class="metric-value" style="color:#fde047;">₹{b['services_income']:,.2f}</div></div>""", unsafe_allow_html=True)
        m4.markdown(f"""<div class="metric-card"><div class="metric-title">🏺 GULLAK / PERSONAL</div><div class="metric-value" style="color:#f472b6;">₹{b['personal_gullak']:,.2f}</div></div>""", unsafe_allow_html=True)

        st.write("---")

        ut1, ut2, ut3, ut4, ut5, ut6 = st.tabs([
            "➕ Entry (BC/Bank/Len-Den)", 
            "🛠️ Services & Custom Income",
            "📖 Customer Ledger & Receipt", 
            "✏️ Edit / Delete", 
            "📋 Cashbook & Export", 
            "⚙️ User KYC & Opening Balance"
        ])

        with ut1:
            st.markdown('<div class="section-box"><h4>➕ New Entry</h4></div>', unsafe_allow_html=True)
            with st.form("txn_entry_form", clear_on_submit=True):
                fc1, fc2 = st.columns(2)
                acc_type = fc1.selectbox("Account Head *", ["Bank Account", "Cash"])
                if acc_type == "Bank Account":
                    tx_type = fc1.selectbox("Transaction Type *", [
                        "Customer AEPS Withdrawal (बैंक बढ़ा / नकद घटा)",
                        "Customer Deposit / Money Transfer (नकद बढ़ा / बैंक घटा)",
                        "Self Bank Cash Withdrawal (बैंक घटा / नकद बढ़ा)",
                        "Self Bank Cash Deposit (बैंक बढ़ा / नकद घटा)"
                    ])
                else:
                    tx_type = fc1.selectbox("Transaction Type *", [
                        "Deposit (जमा / Income)", 
                        "Expense / Withdrawal (खर्च / निकासी)", 
                        "Customer Due Payment Received (उधार रिकवरी +)",
                        "Personal Use / Gullak (निजी खर्च)"
                    ])
                tx_amt = fc1.number_input("Amount (₹) *", min_value=0.0, step=100.0)
                pay_mode = fc1.selectbox("Payment Mode", ["Cash", "UPI / QR", "AEPS", "IMPS/NEFT"])

                cust_name = fc2.text_input("Customer Name")
                cust_adh = fc2.text_input("Aadhaar Last 4 Digits", max_chars=4)
                cust_due = fc2.number_input("Pending Due / Udhar (₹)", min_value=0.0) if tx_type != "Customer Due Payment Received (उधार रिकवरी +)" else 0.0
                tx_ref = fc2.text_input("Ref / UTR / Txn No")
                tx_desc = fc2.text_input("Notes")
                tx_date = fc2.date_input("Date", datetime.now())

                if st.form_submit_button("✅ Save Transaction", use_container_width=True):
                    if tx_amt > 0:
                        dt_str = f"{tx_date.strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M')}"
                        execute_db("""INSERT INTO accounts 
                                      (username, date, type, amount, account_type, tx_id, cust_name, cust_aadhaar_last4, cust_due_amount, payment_mode, description) 
                                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                                   (user_id, dt_str, tx_type, tx_amt, acc_type, tx_ref, cust_name, cust_adh, cust_due, pay_mode, tx_desc))
                        st.success("🎉 Transaction Saved!")
                        st.rerun()

        with ut2:
            st.markdown('<div class="section-box"><h4>🛠️ Daily Services & Custom Income Log</h4></div>', unsafe_allow_html=True)
            with st.form("service_add_form", clear_on_submit=True):
                sc1, sc2 = st.columns(2)
                preset_services = ["PMJJBY", "PMSBY", "APY", "PAN Card", "Aadhaar Work", "PVC Card Print", "Recharge / Bill Payment", "Other Custom Income"]
                selected_preset = sc1.selectbox("Service Category *", preset_services)
                custom_service_name = sc1.text_input("Custom Service Name *") if selected_preset == "Other Custom Income" else ""
                final_title = custom_service_name if selected_preset == "Other Custom Income" else selected_preset

                svc_ref = sc1.text_input("Customer / Ref No *")
                svc_inc = sc2.number_input("Income Amount (₹) *", min_value=0.0)
                svc_note = sc2.text_input("Service Notes")
                svc_dt = sc2.date_input("Date", datetime.now())

                if st.form_submit_button("💼 Save Income", use_container_width=True):
                    if final_title and svc_inc >= 0:
                        dt_s = f"{svc_dt.strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M')}"
                        execute_db("INSERT INTO daily_services (username, date, service_name, ref_no, income_amount, notes) VALUES (?, ?, ?, ?, ?, ?)",
                                   (user_id, dt_s, final_title, svc_ref, svc_inc, svc_note))
                        st.success("✅ Saved and added to Cash!")
                        st.rerun()

            st.dataframe(run_query("SELECT id, date, service_name, ref_no, income_amount, notes FROM daily_services WHERE username=? ORDER BY id DESC", (user_id,)), use_container_width=True)

        with ut3:
            st.markdown('<div class="section-box"><h4>📖 Customer Ledger & Thermal Receipt</h4></div>', unsafe_allow_html=True)
            search_cname = st.text_input("Filter Customer Name:")
            q = "SELECT * FROM accounts WHERE username=?"
            p = [user_id]
            if search_cname:
                q += " AND cust_name LIKE ?"
                p.append(f"%{search_cname}%")

            cust_df = run_query(q, tuple(p))
            if not cust_df.empty:
                st.dataframe(cust_df, use_container_width=True)
                sel_id = st.selectbox("Receipt Txn ID:", cust_df['id'].tolist())
                r_row = cust_df[cust_df['id'] == sel_id].iloc[0]

                st.markdown(f"""
                <div class="receipt-thermal">
                    <div style="text-align:center;"><b>{u_fresh.get('shop_name', 'BC STORE')}</b></div>
                    --------------------------------<br>
                    <b>Txn ID:</b> #{r_row['id']}<br>
                    <b>Date:</b> {r_row['date']}<br>
                    <b>Customer:</b> {r_row['cust_name'] or 'N/A'}<br>
                    --------------------------------<br>
                    <b>Type:</b> {r_row['type']}<br>
                    <b>Amount: ₹{r_row['amount']:,.2f}</b><br>
                    <b>Pending Udhar: ₹{r_row['cust_due_amount']:,.2f}</b><br>
                    --------------------------------<br>
                    <div style="text-align:center;">Thank You!</div>
                </div>
                """, unsafe_allow_html=True)

        with ut4:
            st.markdown('<div class="section-box"><h4>✏️ Edit or Delete Records</h4></div>', unsafe_allow_html=True)
            edit_type = st.radio("Modify Category:", ["Cashbook Txns", "Daily Services"], horizontal=True)

            if edit_type == "Cashbook Txns":
                tx_df = run_query("SELECT id, date, type, amount, cust_name FROM accounts WHERE username=? ORDER BY id DESC", (user_id,))
                if not tx_df.empty:
                    edit_tx_id = st.selectbox("Select Txn ID:", tx_df['id'].tolist())
                    row_tx = run_query("SELECT * FROM accounts WHERE id=?", (edit_tx_id,)).iloc[0]

                    with st.form("edit_tx_form"):
                        e_amt = st.number_input("Amount", value=float(row_tx['amount']))
                        e_cname = st.text_input("Customer Name", value=str(row_tx['cust_name'] or ''))
                        if st.form_submit_button("💾 Update"):
                            execute_db("UPDATE accounts SET amount=?, cust_name=? WHERE id=?", (e_amt, e_cname, edit_tx_id))
                            st.success("✅ Updated!")
                            st.rerun()

                    if st.button("🗑️ Delete Txn", type="primary"):
                        execute_db("DELETE FROM accounts WHERE id=?", (edit_tx_id,))
                        st.success("❌ Deleted!")
                        st.rerun()

            else:
                svc_df = run_query("SELECT id, date, service_name, income_amount FROM daily_services WHERE username=? ORDER BY id DESC", (user_id,))
                if not svc_df.empty:
                    edit_svc_id = st.selectbox("Select Service ID:", svc_df['id'].tolist())
                    row_s = run_query("SELECT * FROM daily_services WHERE id=?", (edit_svc_id,)).iloc[0]

                    with st.form("edit_svc_form"):
                        es_amt = st.number_input("Income Amount", value=float(row_s['income_amount']))
                        if st.form_submit_button("💾 Update Service"):
                            execute_db("UPDATE daily_services SET income_amount=? WHERE id=?", (es_amt, edit_svc_id))
                            st.success("✅ Updated!")
                            st.rerun()

                    if st.button("🗑️ Delete Service", type="primary"):
                        execute_db("DELETE FROM daily_services WHERE id=?", (edit_svc_id,))
                        st.success("❌ Deleted!")
                        st.rerun()

        with ut5:
            st.markdown('<div class="section-box"><h4>📋 Full Cashbook & Export</h4></div>', unsafe_allow_html=True)
            full_cb = run_query("SELECT id, date, account_type, type, amount, cust_name, cust_due_amount, payment_mode, description FROM accounts WHERE username=? ORDER BY id DESC", (user_id,))
            st.dataframe(full_cb, use_container_width=True)
            
            c1, c2 = st.columns(2)
            c1.download_button("📥 Excel Download", data=convert_df_to_excel(full_cb), file_name="Cashbook.xlsx", use_container_width=True)
            c2.download_button("📄 CSV Download", data=full_cb.to_csv(index=False).encode('utf-8'), file_name="Cashbook.csv", mime="text/csv", use_container_width=True)

        with ut6:
            st.markdown('<div class="section-box"><h4>⚙️ User KYC & Opening Balances</h4></div>', unsafe_allow_html=True)
            kc1, kc2 = st.columns(2)
            
            with kc1:
                with st.form("user_kyc_form"):
                    st.write("##### Profile Details")
                    p_fn = st.text_input("Full Name", value=u_fresh.get('full_name', ''))
                    p_shop = st.text_input("Shop Name", value=u_fresh.get('shop_name', ''))
                    p_pan = st.text_input("PAN Card", value=u_fresh.get('pan_card', ''))
                    p_adh = st.text_input("Aadhaar Number", value=u_fresh.get('aadhaar_no', ''))
                    if st.form_submit_button("💾 Save KYC"):
                        execute_db("UPDATE users SET full_name=?, shop_name=?, pan_card=?, aadhaar_no=? WHERE username=?",
                                   (p_fn, p_shop, p_pan, p_adh, user_id))
                        st.success("✅ KYC Updated!")
                        st.rerun()

            with kc2:
                op_data = run_query("SELECT * FROM opening_balances WHERE username=?", (user_id,))
                op_c = op_data.iloc[0]['cash_op'] if not op_data.empty else 0.0
                op_b = op_data.iloc[0]['bank_op'] if not op_data.empty else 0.0

                with st.form("opening_bal_form"):
                    st.write("##### Opening Balances")
                    n_c = st.number_input("Opening Cash (₹)", value=float(op_c))
                    n_b = st.number_input("Opening Bank (₹)", value=float(op_b))
                    if st.form_submit_button("💾 Save Balances"):
                        execute_db("""INSERT INTO opening_balances (username, cash_op, bank_op) VALUES (?, ?, ?)
                                      ON CONFLICT(username) DO UPDATE SET cash_op=excluded.cash_op, bank_op=excluded.bank_op""",
                                   (user_id, n_c, n_b))
                        st.success("✅ Opening Balances Saved!")
                        st.rerun()
