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
# 1. DATABASE INITIALIZATION & AUTO-MIGRATION LOGIC
# =========================================================
DB_NAME = "local_cashbook.db"

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    
    # Users Table with Master Details & First-Login Password Change Flags
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

    # AUTO-MIGRATION FOR USERS TABLE
    existing_user_cols = [col[1] for col in c.execute("PRAGMA table_info(users)").fetchall()]
    user_cols_to_add = {
        "email": "TEXT",
        "mobile": "TEXT",
        "full_name": "TEXT",
        "father_name": "TEXT",
        "pan_card": "TEXT",
        "aadhaar_no": "TEXT",
        "shop_name": "TEXT",
        "is_first_login": "INTEGER DEFAULT 1"
    }
    for col_name, col_type in user_cols_to_add.items():
        if col_name not in existing_user_cols:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")

    # AUTO-MIGRATION FOR ACCOUNTS TABLE
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
    
    # Default Admin Entry
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role, is_approved, is_first_login) VALUES ('admin', 'admin123', 'Admin', 1, 0)")
    
    conn.commit()
    conn.close()

init_db()

# =========================================================
# 2. HELPER FUNCTIONS, AUTO-GENERATORS & NOTIFICATIONS
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

def send_credentials_email(target_email, username, password):
    sender_email = "your_email@gmail.com" 
    sender_password = "your_app_password"  # Gmail App Password
    app_link = "https://your-app-link.streamlit.app" 
    
    subject = "आपका Cashbook One-Time Login Password Details"
    body = f"""नमस्ते {username},

आपका Digital Cashbook Account बना दिया गया है।

आपका वन-टाइम (One-Time) लॉगिन विवरण:
🔗 App Link: {app_link}
👤 User ID: {username}
🔑 Temporary Password: {password}

⚠️ कृपया ध्यान दें: पहली बार लॉगिन करने के बाद आपको अपना नया स्थायी पासवर्ड (Permanent Password) सेट करना होगा।

धन्यवाद!
Digital Banking System
"""
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = target_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, target_email, msg.as_string())
        return True
    except Exception as e:
        st.error(f"❌ Email भेज़ने में त्रुटि: {e}")
        return False

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
# 3. PAGE CONFIG & LOGIN / PASSWORD CHANGE SYSTEM
# =========================================================
st.set_page_config(page_title="AEPS & Cashbook Accounting System", page_icon="🏦", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None
if 'force_password_change' not in st.session_state:
    st.session_state['force_password_change'] = False

st.title("🏦 Digital Banking & Daily Cashbook System")

# SCREEN FOR FORCED FIRST-TIME PASSWORD RESET
if st.session_state['force_password_change']:
    st.warning("🔒 यह आपका पहला लॉगिन है! सुरक्षा के लिए कृपया नया पासवर्ड बनाएं।")
    with st.form("first_time_pwd_form"):
        new_pwd = st.text_input("नया पासवर्ड (New Password) *", type="password")
        confirm_pwd = st.text_input("नए पासवर्ड की पुष्टि करें (Confirm Password) *", type="password")
        
        if st.form_submit_button("💾 नया पासवर्ड सेट करें"):
            if new_pwd and confirm_pwd:
                if new_pwd == confirm_pwd:
                    user_id = st.session_state['user_info']['username']
                    execute_db("UPDATE users SET password=?, is_first_login=0 WHERE username=?", (new_pwd, user_id))
                    st.success("✅ पासवर्ड सफलतापूर्वक बदल दिया गया! अब आप सिस्टम का उपयोग कर सकते हैं।")
                    st.session_state['force_password_change'] = False
                    st.session_state['user_info']['is_first_login'] = 0
                    st.rerun()
                else:
                    st.error("❌ दोनों पासवर्ड समान नहीं हैं!")
            else:
                st.warning("⚠️ कृपया नया पासवर्ड दर्ज करें!")

# REGULAR LOGIN SCREEN
elif not st.session_state['logged_in']:
    t_login, t_admin = st.tabs(["👤 User Login", "🔐 Admin Login"])

    with t_login:
        c_username = st.text_input("User ID", key="c_u")
        c_password = st.text_input("Password / Temporary Password", type="password", key="c_p")
        if st.button("User Log In"):
            u_df = run_query("SELECT * FROM users WHERE username=? AND password=? AND role='Customer'", (c_username, c_password))
            if not u_df.empty:
                user_data = u_df.iloc[0].to_dict()
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = user_data
                
                # Check First Time Login Flag
                if user_data.get('is_first_login') == 1:
                    st.session_state['force_password_change'] = True
                
                st.rerun()
            else:
                st.error("❌ गलत विवरण!")

    with t_admin:
        a_username = st.text_input("Admin ID", key="a_u")
        a_password = st.text_input("Admin Password", type="password", key="a_p")
        if st.button("Admin Log In"):
            u_df = run_query("SELECT * FROM users WHERE username=? AND password=? AND role='Admin'", (a_username, a_password))
            if not u_df.empty:
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = u_df.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("❌ गलत Admin विवरण!")

# =========================================================
# 4. DASHBOARD PANELS
# =========================================================
else:
    st.sidebar.write(f"लॉग इन यूजर: **{st.session_state['user_info']['username']}**")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.session_state['user_info'] = None
        st.session_state['force_password_change'] = False
        st.rerun()

    user_role = st.session_state['user_info']['role']
    user_id = st.session_state['user_info']['username']

    # ------------------ USER DASHBOARD ------------------
    if user_role == "Customer":
        b = calculate_exact_balances(user_id)
        
        st.subheader("📊 बैलेंस की ताज़ा स्थिति")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💵 Cash Balance", f"₹{b['cash_closing']:,}", f"Opening: ₹{b['cash_op']:,}")
        m2.metric("🏦 Bank Balance", f"₹{b['bank_closing']:,}", f"Opening: ₹{b['bank_op']:,}")
        m3.metric("💼 Total Service Income", f"₹{b['services_income']:,}")
        m4.metric("🏺 Personal / Gullak", f"₹{b['personal_gullak']:,}")

        st.write("---")
        
        ut1, ut2, ut3, ut4, ut5 = st.tabs([
            "➕ AEPS / Cash / Deposit Transaction Entry", 
            "🔍 Customer Ledger (Aadhaar/Search)", 
            "🛠️ Daily Services Log", 
            "📋 Full Transaction History", 
            "⚙️ Opening Balance Settings"
        ])

        # TAB 1: MAIN ENTRY FORM
        with ut1:
            st.subheader("➕ AEPS / Cash / Deposit Transaction Entry")
            if st.button("🔄 New Entry / Clear Form"):
                st.rerun()

            with st.form("main_txn_form", clear_on_submit=True):
                fc1, fc2 = st.columns(2)
                with fc1:
                    t_account = st.selectbox("Account Type *", ["Bank Account", "Cash"])
                    if t_account == "Bank Account":
                        t_type = st.selectbox("लेनदेन का प्रकार *", [
                            "Customer AEPS Withdrawal (बैंक बढ़ा / नकद घटा)",
                            "Customer Deposit / Money Transfer (नकद बढ़ा / बैंक घटा)",
                            "Self Bank Cash Withdrawal (बैंक घटा / नकद बढ़ा)",
                            "Self Bank Cash Deposit (बैंक बढ़ा / नकद घटा)"
                        ])
                    else:
                        t_type = st.selectbox("लेनदेन का प्रकार *", [
                            "Deposit (जमा)", 
                            "Withdrawal (निकासी)", 
                            "Customer Due Payment Received (उधार रिकवरी - Cash +)",
                            "Personal Use / Gullak (निजी खर्च/गुल्लक)"
                        ])
                    
                    t_amount = st.number_input("राशि (Amount ₹) *", min_value=0.0, step=50.0)
                    t_tx_id = st.text_input("Txn / UTR / Ref No")
                
                with fc2:
                    t_cname = st.text_input("ग्राहक का नाम (Customer Name)")
                    t_aadhaar = st.text_input("आधार के अंतिम 4 अंक", max_chars=4)
                    
                    if t_type == "Customer Due Payment Received (उधार रिकवरी - Cash +)":
                        t_due = 0.0
                        st.info("💡 यह एंट्री कस्टमर के उधार को कम करेगी।")
                    else:
                        t_due = st.number_input("नई बाकी/उधार राशि (अगर कोई हो) ₹", min_value=0.0, value=0.0, step=50.0)
                        
                    t_desc = st.text_input("अतिरिक्त नोट / विवरण")
                    t_date = st.date_input("तारीख", datetime.now())

                if st.form_submit_button("✅ ट्रांजैक्शन दर्ज करें (Save Entry)"):
                    if t_amount > 0:
                        d_str = f"{t_date.strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M')}"
                        execute_db("""INSERT INTO accounts 
                                      (username, date, type, amount, account_type, tx_id, cust_name, cust_aadhaar_last4, cust_due_amount, description) 
                                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                                   (user_id, d_str, t_type, t_amount, t_account, t_tx_id, t_cname, t_aadhaar, t_due, t_desc))
                        st.success("✅ लेनदेन सफलता से दर्ज हो गया!")
                        st.rerun()
                    else:
                        st.warning("⚠️ कृपया 0 से अधिक राशि दर्ज करें!")

        # TAB 2: CUSTOMER LEDGER
        with ut2:
            st.subheader("🔍 ग्राहक लेजर खोजें")
            sc1, sc2 = st.columns(2)
            search_aadhaar = sc1.text_input("आधार नंबर के अंतिम 4 अंक दर्ज करें:")
            search_name = sc2.text_input("या ग्राहक का नाम लिखें:")

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
                else:
                    st.info("ℹ️ कोई रिकॉर्ड नहीं मिला।")

        # TAB 3: DAILY SERVICES LOG
        with ut3:
            st.subheader("🛠️ आज की ऑनलाइन/सर्विस वर्क एंट्री")
            with st.form("services_form", clear_on_submit=True):
                svc1, svc2 = st.columns(2)
                with svc1:
                    s_name = st.selectbox("सर्विस चुनें *", ["PMJJBY", "PMSBY", "APY", "KYC", "CKYC", "Loan Lead", "PAN Card", "Aadhaar", "Online Service", "Other"])
                    s_ref = st.text_input("कस्टमर नाम / रेफरेंस नं *")
                with svc2:
                    s_income = st.number_input("प्राप्त फीस/आय (₹) *", min_value=0.0)
                    s_note = st.text_input("अतिरिक्त जानकारी")

                if st.form_submit_button("💼 सर्विस सेव करें"):
                    if s_ref and s_income >= 0:
                        execute_db("INSERT INTO daily_services (username, date, service_name, ref_no, income_amount, notes) VALUES (?, ?, ?, ?, ?, ?)",
                                   (user_id, datetime.now().strftime('%Y-%m-%d %H:%M'), s_name, s_ref, s_income, s_note))
                        st.success("✅ सर्विस इनकम सेव हो गई!")
                        st.rerun()

            st.dataframe(run_query("SELECT date, service_name, ref_no, income_amount, notes FROM daily_services WHERE username=? ORDER BY id DESC", (user_id,)), use_container_width=True)

        # TAB 4: ALL TRANSACTIONS
        with ut4:
            st.subheader("📋 आपकी पूरी कैशबुक एंट्रीज")
            all_txns = run_query("SELECT id, date, account_type, type, amount, cust_name, cust_aadhaar_last4, cust_due_amount, tx_id, description FROM accounts WHERE username=? ORDER BY id DESC", (user_id,))
            st.dataframe(all_txns, use_container_width=True)

        # TAB 5: OPENING BALANCES
        with ut5:
            st.subheader("⚙️ Opening Balances सेट करें")
            curr_op = run_query("SELECT * FROM opening_balances WHERE username=?", (user_id,))
            op_c = curr_op.iloc[0]['cash_op'] if not curr_op.empty else 0.0
            op_b = curr_op.iloc[0]['bank_op'] if not curr_op.empty else 0.0

            with st.form("op_form"):
                oc1, oc2 = st.columns(2)
                nc = oc1.number_input("Cash Opening Balance (₹)", value=float(op_c))
                nb = oc2.number_input("Bank Opening Balance (₹)", value=float(op_b))
                if st.form_submit_button("💾 Opening Balance अपडेट करें"):
                    execute_db("""INSERT INTO opening_balances (username, cash_op, bank_op) VALUES (?, ?, ?)
                                  ON CONFLICT(username) DO UPDATE SET cash_op=excluded.cash_op, bank_op=excluded.bank_op""",
                               (user_id, nc, nb))
                    st.success("✅ Opening Balance सेव हो गया!")
                    st.rerun()

    # ------------------ MASTER ADMIN PANEL ------------------
    elif user_role == "Admin":
        st.title("👑 Master Admin Control Center")
        
        adm_t1, adm_t2, adm_t3 = st.tabs(["📊 Live Reports View", "👥 Master Registered Users", "➕ Master User Registration"])

        # ADMIN TAB 1: REPORTS
        with adm_t1:
            st.subheader("📊 यूजर्स की मास्टर रिपोर्ट")
            sel_user = st.selectbox("यूजर चुनें:", ["ALL"] + run_query("SELECT username FROM users WHERE role='Customer'")['username'].tolist())
            rep_data = run_query("SELECT * FROM accounts ORDER BY id DESC") if sel_user == "ALL" else run_query("SELECT * FROM accounts WHERE username=? ORDER BY id DESC", (sel_user,))
            st.dataframe(rep_data, height=400, use_container_width=True)

        # ADMIN TAB 2: REGISTERED USERS FULL DETAILS
        with adm_t2:
            st.subheader("👥 सभी पंजीकृत यूजरों की जानकारी")
            users_df = run_query("""SELECT id, username, full_name, father_name, shop_name, mobile, email, pan_card, 
                                           is_first_login FROM users WHERE role='Customer'""")
            st.dataframe(users_df, use_container_width=True)

        # ADMIN TAB 3: MASTER USER REGISTRATION FORM
        with adm_t3:
            st.subheader("➕ नया यूजर रजिस्टर करें (Admin Only)")
            
            with st.form("master_user_form"):
                col1, col2 = st.columns(2)
                with col1:
                    u_full_name = st.text_input("User Full Name (पूरा नाम) *")
                    u_father_name = st.text_input("Father's Name (पिता का नाम) *")
                    u_shop_name = st.text_input("Shop / Center Name (दुकान का नाम) *")
                    u_mobile = st.text_input("Mobile No (WhatsApp 10 digits) *")
                
                with col2:
                    u_email = st.text_input("Email ID *")
                    u_pan = st.text_input("PAN Card Number")
                    u_aadhaar = st.text_input("Aadhaar Card Number (12 digits)")
                
                st.write("---")
                submit_master_user = st.form_submit_button("🚀 ऑटोमैटिक User ID & Password बनाएं और सेव करें")

                if submit_master_user:
                    if u_full_name and u_mobile and u_father_name and u_shop_name:
                        # Auto-Generate User ID and Temporary OTP Password
                        auto_user_id = generate_auto_userid(u_full_name, u_mobile)
                        one_time_pass = generate_one_time_password(6)
                        
                        try:
                            execute_db("""INSERT INTO users 
                                          (username, password, role, is_approved, email, mobile, full_name, father_name, pan_card, aadhaar_no, shop_name, is_first_login) 
                                          VALUES (?, ?, 'Customer', 1, ?, ?, ?, ?, ?, ?, ?, 1)""", 
                                       (auto_user_id, one_time_pass, u_email, u_mobile, u_full_name, u_father_name, u_pan, u_aadhaar, u_shop_name))
                            
                            st.success("✅ यूजर सफलतापूर्वक बन गया है!")
                            st.info(f"🔑 Generated User ID: **{auto_user_id}** | One-Time Password: **{one_time_pass}**")

                            # Email Trigger
                            if u_email:
                                send_credentials_email(u_email, auto_user_id, one_time_pass)

                            # WhatsApp Link Trigger
                            if u_mobile:
                                app_link = "https://your-app-link.streamlit.app"
                                wa_msg = (f"नमस्ते {u_full_name},\n\n"
                                          f"आपका Cashbook App अकाउंट बना दिया गया है।\n\n"
                                          f"🔗 App Link: {app_link}\n"
                                          f"👤 User ID: {auto_user_id}\n"
                                          f"🔑 One-Time Password: {one_time_pass}\n\n"
                                          f"⚠️ ध्यान दें: पहली बार लॉगिन करने के बाद आपको अपना नया पासवर्ड बनाना होगा।")
                                encoded_msg = urllib.parse.quote(wa_msg)
                                wa_url = f"https://wa.me/91{u_mobile}?text={encoded_msg}"
                                
                                st.markdown(f"[👉 यहाँ क्लिक करके WhatsApp पर Login Details और Link भेजें]({wa_url})", unsafe_allow_html=True)

                        except sqlite3.IntegrityError:
                            st.error("❌ इस नाम और नंबर से User ID ऑटो-जनरेट करने में समस्या आई या ID पहले से मौजूद है!")
                    else:
                        st.warning("⚠️ कृपया सभी आवश्यक (*) फ़ील्ड भरें!")
