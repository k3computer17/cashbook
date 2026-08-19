import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
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
    
    # Updated Users Table with Subscription, KYC & Demo Expiry
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
    
    # ENSURE OFFICIAL ADMIN ACCOUNT
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

# Session States
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

    with login_tab3:
        st.subheader("🛡️ Admin Login Window")
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
# 5. WORKSPACE (USER / ADMIN)
# =========================================================
else:
    user_id = st.session_state['user_info']['username']
    user_role = st.session_state['user_info'].get('role', 'Customer')
    full_name = st.session_state['user_info'].get('full_name', user_id)
    
    # Refresh current user session from DB
    u_fresh = run_query("SELECT * FROM users WHERE username=?", (user_id,)).iloc[0].to_dict()
    
    # Top Header
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
    # A. ADMIN DASHBOARD WORKSPACE
    # =========================================================
    if user_role == "Official_Admin":
        st.success("🛡️ Official Admin Panel Active")
        
        adm_t1, adm_t2, adm_t3, adm_t4 = st.tabs([
            "📋 Users & KYC Approvals", 
            "⏳ Manage Demo & Extensions", 
            "➕ Add New User", 
            "🔒 Admin Security"
        ])

        # TAB 1: KYC & PAID APPROVALS
        with adm_t1:
            st.subheader("👥 User Management & Paid License Activation")
            all_users = run_query("SELECT id, username, full_name, mobile, shop_name, kyc_status, is_paid, demo_expiry_date FROM users WHERE role='Customer'")
            st.dataframe(all_users, use_container_width=True)
            
            st.write("---")
            st.markdown("#### ⚡ Activate Paid Version / Approve KYC")
            c_u = st.selectbox("Select User ID:", all_users['username'].tolist() if not all_users.empty else [])
            if c_u:
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

        # TAB 2: DEMO EXTENSION CONTROL
        with adm_t2:
            st.subheader("⏳ Extend Demo Validity (3-Day Trial Extension)")
            st.caption("Aap kisi bhi Demo user ki Expiry Date ko aage badha sakte hain.")
            
            if not all_users.empty:
                sel_demo_user = st.selectbox("Select Demo User to Extend:", all_users['username'].tolist())
                d_user_data = all_users[all_users['username'] == sel_demo_user].iloc[0]
                
                curr_exp = d_user_data['demo_expiry_date'] if d_user_data['demo_expiry_date'] else datetime.now().strftime('%Y-%m-%d')
                st.info(f"Current Demo Expiry Date: **{curr_exp}**")
                
                add_days = st.number_input("Add Extra Demo Days:", min_value=1, max_value=30, value=3)
                if st.button("🚀 Extend Demo Period"):
                    curr_date_dt = datetime.strptime(curr_exp, '%Y-%m-%d') if d_user_data['demo_expiry_date'] else datetime.now()
                    new_exp_dt = (curr_date_dt + timedelta(days=add_days)).strftime('%Y-%m-%d')
                    execute_db("UPDATE users SET demo_expiry_date=? WHERE username=?", (new_exp_dt, sel_demo_user))
                    st.success(f"🎉 Demo validity extended till {new_exp_dt} for user {sel_demo_user}!")
                    st.rerun()

        # TAB 3: CREATE USER WITH 3-DAY DEMO
        with adm_t3:
            st.subheader("➕ Register New Merchant User (Default 3-Day Demo)")
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
                        st.success(f"🎉 Account Created! ID: {generated_uid} | Pass: {generated_pwd} | Valid Till: {demo_expiry}")
                    else:
                        st.warning("⚠️ Full Name, Father Name & Mobile Required!")

        # TAB 4: CHANGE ADMIN PASS
        with adm_t4:
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
        # Check Expiry & License Logic
        today_str = datetime.now().strftime('%Y-%m-%d')
        demo_expiry_str = u_fresh.get('demo_expiry_date', today_str)
        is_paid = u_fresh.get('is_paid', 0)
        kyc_status = u_fresh.get('kyc_status', 'Pending')

        # Demo Expired Check
        is_expired = (today_str > demo_expiry_str) if demo_expiry_str else False

        if is_paid == 0 and is_expired:
            st.error(f"🚨 Demo Period Expired on {demo_expiry_str}!")
            st.warning("Aapka 3 days ka demo version khatam ho chuka hai. Kripya Admin se sampark karke Fees pay karein ya Demo extension lein.")
            
            st.write("---")
            st.subheader("📄 Submit / Update Your KYC Details")
            with st.form("kyc_submit_form"):
                k_pan = st.text_input("PAN Card Number", value=u_fresh.get('pan_card', ''))
                k_adh = st.text_input("Aadhaar Number", value=u_fresh.get('aadhaar_no', ''))
                k_shop = st.text_input("Shop Name", value=u_fresh.get('shop_name', ''))
                if st.form_submit_button("📩 Submit KYC for Paid Approval"):
                    execute_db("UPDATE users SET pan_card=?, aadhaar_no=?, shop_name=?, kyc_status='Pending' WHERE username=?", (k_pan, k_adh, k_shop, user_id))
                    st.success("✅ KYC Submitted! Admin jald hi ise approve karke paid membership activate karega.")
                    st.rerun()

        else:
            # Active Subscription / Valid Demo Status
            if is_paid == 1:
                st.success("🟢 Status: Paid Premium Account Active")
            else:
                st.info(f"⏳ Status: 3-Day Demo Version Active (Valid Till: **{demo_expiry_str}**)")

            b = calculate_exact_balances(user_id)

            # Dashboard Balances
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💵 Cash Balance", f"₹{b['cash_closing']:,.2f}")
            c2.metric("🏦 Bank Balance", f"₹{b['bank_closing']:,.2f}")
            c3.metric("💼 Services Comm.", f"₹{b['services_income']:,.2f}")
            c4.metric("🏺 Gullak / Personal", f"₹{b['personal_gullak']:,.2f}")

            st.write("---")

            # Main App Tabs
            ut1, ut2, ut3, ut4 = st.tabs([
                "➕ New Transaction", 
                "🛠️ Daily Services Log", 
                "📋 Full Cashbook", 
                "📄 KYC & Profile"
            ])

            with ut1:
                st.subheader("➕ AEPS / Cash Entry")
                with st.form("txn_form", clear_on_submit=True):
                    t_account = st.selectbox("Account Type *", ["Bank Account", "Cash"])
                    t_type = st.selectbox("Transaction Type *", [
                        "Deposit (जमा)", "Withdrawal (निकासी)", 
                        "Customer AEPS Withdrawal", "Customer Deposit / Money Transfer"
                    ])
                    t_amount = st.number_input("Amount (₹) *", min_value=0.0)
                    t_cname = st.text_input("Customer Name")
                    if st.form_submit_button("✅ Save Transaction"):
                        if t_amount > 0:
                            d_str = datetime.now().strftime('%Y-%m-%d %H:%M')
                            execute_db("INSERT INTO accounts (username, date, type, amount, account_type, cust_name) VALUES (?, ?, ?, ?, ?, ?)",
                                       (user_id, d_str, t_type, t_amount, t_account, t_cname))
                            st.success("Transaction Recorded!")
                            st.rerun()

            with ut2:
                st.subheader("🛠️ Services Tracker")
                with st.form("service_form"):
                    s_name = st.text_input("Service Name")
                    s_inc = st.number_input("Income (₹)", min_value=0.0)
                    if st.form_submit_button("Save Service"):
                        execute_db("INSERT INTO daily_services (username, date, service_name, income_amount) VALUES (?, ?, ?, ?)",
                                   (user_id, datetime.now().strftime('%Y-%m-%d'), s_name, s_inc))
                        st.success("Saved!")
                        st.rerun()

            with ut3:
                st.subheader("📋 Complete Ledger")
                st.dataframe(run_query("SELECT date, type, amount, account_type, cust_name FROM accounts WHERE username=? ORDER BY id DESC", (user_id,)), use_container_width=True)

            with ut4:
                st.subheader("📄 Your Profile & KYC Status")
                st.write(f"**KYC Status:** {u_fresh.get('kyc_status')}")
                st.write(f"**Subscription Status:** {'Paid User' if u_fresh.get('is_paid') == 1 else 'Demo Account'}")
                st.write(f"**Demo Expiry Date:** {u_fresh.get('demo_expiry_date')}")
