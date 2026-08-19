import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import io
import smtplib
import urllib.parse
from email.mime.text import MIMEText

# =========================================================
# 1. DATABASE INITIALIZATION & AUTO-MIGRATION LOGIC
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
                    mobile TEXT
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

    # AUTO-MIGRATION FOR ACCOUNTS
    existing_cols = [col[1] for col in c.execute("PRAGMA table_info(accounts)").fetchall()]
    if "cust_name" not in existing_cols:
        c.execute("ALTER TABLE accounts ADD COLUMN cust_name TEXT")
    if "cust_aadhaar_last4" not in existing_cols:
        c.execute("ALTER TABLE accounts ADD COLUMN cust_aadhaar_last4 TEXT")
    if "cust_due_amount" not in existing_cols:
        c.execute("ALTER TABLE accounts ADD COLUMN cust_due_amount REAL DEFAULT 0.0")

    # AUTO-MIGRATION FOR USERS
    existing_user_cols = [col[1] for col in c.execute("PRAGMA table_info(users)").fetchall()]
    if "email" not in existing_user_cols:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if "mobile" not in existing_user_cols:
        c.execute("ALTER TABLE users ADD COLUMN mobile TEXT")

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
        c.execute("INSERT INTO users (username, password, role, is_approved) VALUES ('admin', 'admin123', 'Admin', 1)")
    
    conn.commit()
    conn.close()

init_db()

# =========================================================
# 2. HELPER FUNCTIONS, EMAIL & WHATSAPP LOGIC
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

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
    return output.getvalue()

def send_credentials_email(target_email, username, password):
    # ⚠️ Apni Gmail Details Aur App Password Yahan Dalein
    sender_email = "your_email@gmail.com" 
    sender_password = "your_app_password"  # Gmail App Password
    
    app_link = "https://your-app-link.streamlit.app"  # Apne deployed app ka link yahan dalein
    
    subject = "आपका Cashbook System Login Details"
    body = f"""नमस्ते {username},

आपका Cashbook System अकाउंट सफलता से बना दिया गया है। 

लॉगिन करने के विवरण नीचे दिए गए हैं:
🔗 Login Link: {app_link}
👤 User ID: {username}
🔑 Password: {password}

धन्यवाद!
Digital Banking Cashbook System
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
        st.error(f"❌ Email भेज़ने में एरर आया: {e}")
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
# 3. PAGE CONFIG & AUTHENTICATION
# =========================================================
st.set_page_config(page_title="AEPS & Cashbook Accounting System", page_icon="🏦", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None

st.title("🏦 Digital Banking & Daily Cashbook System")

if not st.session_state['logged_in']:
    t_login, t_admin = st.tabs(["👤 User Login", "🔐 Admin Login"])

    with t_login:
        c_username = st.text_input("User ID", key="c_u")
        c_password = st.text_input("Password", type="password", key="c_p")
        if st.button("User Log In"):
            u_df = run_query("SELECT * FROM users WHERE username=? AND password=? AND role='Customer'", (c_username, c_password))
            if not u_df.empty:
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = u_df.iloc[0].to_dict()
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

        # TAB 1: MAIN ENTRY FORM WITH RESET/NEW ENTRY OPTION
        with ut1:
            st.subheader("➕ AEPS / Cash / Deposit Transaction Entry")
            
            if st.button("🔄 New Entry / Clear Form (नया फॉर्म शुरू करें)", help="गलती से बचने के लिए फॉर्म को साफ़ करें"):
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
                    t_aadhaar = st.text_input("आधार के अंतिम 4 अंक (Aadhaar Last 4 Digits)", max_chars=4)
                    
                    if t_type == "Customer Due Payment Received (उधार रिकवरी - Cash +)":
                        t_due = 0.0
                        st.info("💡 यह एंट्री कस्टमर के उधार को कम करेगी और कैश बैलेंस बढ़ाएगी।")
                    else:
                        t_due = st.number_input("नई बाकी/उधार राशि (अगर कोई हो) ₹", min_value=0.0, value=0.0, step=50.0)
                        
                    t_desc = st.text_input("अतिरिक्त नोट / विवरण")
                    t_date = st.date_input("तारीख", datetime.now())

                btn_col1, btn_col2 = st.columns([2, 1])
                with btn_col1:
                    submit_entry = st.form_submit_button("✅ ट्रांजैक्शन दर्ज करें (Save Entry)")
                
                if submit_entry:
                    if t_amount > 0:
                        d_str = f"{t_date.strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M')}"
                        execute_db("""INSERT INTO accounts 
                                      (username, date, type, amount, account_type, tx_id, cust_name, cust_aadhaar_last4, cust_due_amount, description) 
                                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                                   (user_id, d_str, t_type, t_amount, t_account, t_tx_id, t_cname, t_aadhaar, t_due, t_desc))
                        st.success("✅ लेनदेन सफलता से दर्ज हो गया! फॉर्म नई एंट्री के लिए साफ़ हो गया है।")
                        st.rerun()
                    else:
                        st.warning("⚠️ कृपया 0 से अधिक राशि दर्ज करें!")

        # TAB 2: CUSTOMER AADHAAR LEDGER
        with ut2:
            st.subheader("🔍 ग्राहक लेजर खोजें (Search Customer Ledger)")
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
                    st.write(f"### 📋 {cust_data.iloc[0]['cust_name']} (Aadhaar: ****{cust_data.iloc[0]['cust_aadhaar_last4']}) का लेजर खाते का विवरण")
                    
                    tot_len_den = cust_data['amount'].sum()
                    tot_due_added = cust_data['cust_due_amount'].sum()
                    
                    paid_due_df = cust_data[cust_data['type'] == 'Customer Due Payment Received (उधार रिकवरी - Cash +)']
                    tot_due_paid = paid_due_df['amount'].sum() if not paid_due_df.empty else 0.0
                    
                    current_net_due = tot_due_added - tot_due_paid

                    lc1, lc2, lc3 = st.columns(3)
                    lc1.metric("कुल लेन-देन (Total Volume)", f"₹{tot_len_den:,.2f}")
                    lc2.metric("कुल चुकाया गया उधार (Total Recovered)", f"₹{tot_due_paid:,.2f}")
                    lc3.metric("वर्तमान शेष बाकी/उधार (Net Outstanding Due)", f"₹{current_net_due:,.2f}", delta_color="inverse")
                    
                    st.dataframe(cust_data, use_container_width=True)
                    
                    st.download_button(
                        "📥 इस ग्राहक का लेजर Excel में डाउनलोड करें", 
                        data=convert_df_to_excel(cust_data), 
                        file_name=f"Customer_Ledger_{search_aadhaar}.xlsx"
                    )
                else:
                    st.info("ℹ️ इस आधार नंबर या नाम का कोई रिकॉर्ड नहीं मिला।")

        # TAB 3: DAILY SERVICES LOG
        with ut3:
            st.subheader("🛠️ आज की ऑनलाइन/सर्विस वर्क एंट्री")
            with st.form("services_form", clear_on_submit=True):
                svc1, svc2 = st.columns(2)
                with svc1:
                    s_name = st.selectbox("सर्विस चुनें *", ["PMJJBY", "PMSBY", "APY", "KYC", "CKYC", "Loan Lead", "PAN Card", "Aadhaar", "Online Service", "Other"])
                    s_ref = st.text_input("कस्टमर नाम / रेफरेंस नं *")
                with svc2:
                    s_income = st.number_input("प्राप्त फीस/आय (₹ - Cash +) *", min_value=0.0)
                    s_note = st.text_input("अतिरिक्त जानकारी")

                if st.form_submit_button("💼 सर्विस सेव करें"):
                    if s_ref and s_income >= 0:
                        execute_db("INSERT INTO daily_services (username, date, service_name, ref_no, income_amount, notes) VALUES (?, ?, ?, ?, ?, ?)",
                                   (user_id, datetime.now().strftime('%Y-%m-%d %H:%M'), s_name, s_ref, s_income, s_note))
                        st.success("✅ सर्विस इनकम सेव हो गई!")
                        st.rerun()

            st.dataframe(run_query("SELECT date, service_name, ref_no, income_amount, notes FROM daily_services WHERE username=? ORDER BY id DESC", (user_id,)), use_container_width=True)

        # TAB 4: ALL TRANSACTIONS & DELETE
        with ut4:
            st.subheader("📋 आपकी पूरी कैशबुक एंट्रीज")
            all_txns = run_query("SELECT id, date, account_type, type, amount, cust_name, cust_aadhaar_last4, cust_due_amount, tx_id, description FROM accounts WHERE username=? ORDER BY id DESC", (user_id,))
            st.dataframe(all_txns, use_container_width=True)
            
            if not all_txns.empty:
                st.write("---")
                del_id = st.selectbox("एंट्री मिटाने के लिए ID चुनें:", all_txns['id'].tolist())
                if st.button("🗑️ चुनी हुई एंट्री डिलीट करें"):
                    execute_db("DELETE FROM accounts WHERE id=?", (del_id,))
                    st.warning("⚠️ एंट्री डिलीट कर दी गई!")
                    st.rerun()

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
        st.title("👑 Master Admin Report & Control Center")
        
        adm_t1, adm_t2, adm_t3 = st.tabs(["📊 Live Reports & Clean Window View", "👥 Registered Users", "➕ Add New User"])

        # ADMIN TAB 1: NEW WINDOW CLEAN VIEW & EXPORT
        with adm_t1:
            st.subheader("📊 यूजर्स की मास्टर रिपोर्ट (Dedicated Window View)")
            
            sel_user = st.selectbox("यूजर चुनें:", ["ALL"] + run_query("SELECT username FROM users WHERE role='Customer'")['username'].tolist())
            
            if sel_user == "ALL":
                rep_data = run_query("SELECT * FROM accounts ORDER BY id DESC")
            else:
                rep_data = run_query("SELECT * FROM accounts WHERE username=? ORDER BY id DESC", (sel_user,))

            st.write("---")
            
            with st.container():
                st.markdown(f"### 🪟 Dedicated Report View Window: **{sel_user}**")
                
                if not rep_data.empty:
                    st.download_button(
                        label="📥 Clean Report Export To Excel",
                        data=convert_df_to_excel(rep_data),
                        file_name=f"Admin_Report_{sel_user}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
                st.dataframe(rep_data, height=450, use_container_width=True)

        # ADMIN TAB 2: USERS LIST (Including Email and Mobile Info)
        with adm_t2:
            st.subheader("👥 सभी पंजीकृत यूजर्स (Complete Details)")
            users_df = run_query("SELECT id, username, password, email, mobile, client_id FROM users WHERE role='Customer'")
            st.dataframe(users_df, use_container_width=True)

        # ADMIN TAB 3: ADD USER & AUTOMATIC CREDENTIALS SHARE
        with adm_t3:
            st.subheader("➕ नया यूजर बनाएं (Admin Only)")
            with st.form("add_user"):
                u_name = st.text_input("User ID / Username *")
                u_pass = st.text_input("Password *", type="password")
                u_email = st.text_input("User Email ID")
                u_mobile = st.text_input("User Mobile Number (WhatsApp me 10 digits)")
                
                submit_user = st.form_submit_button("✅ नया यूजर बनाएं एवं विवरण भेजें")
                
                if submit_user:
                    if u_name and u_pass:
                        try:
                            execute_db(
                                "INSERT INTO users (username, password, role, is_approved, email, mobile) VALUES (?, ?, 'Customer', 1, ?, ?)", 
                                (u_name, u_pass, u_email, u_mobile)
                            )
                            st.success(f"✅ नया यूजर '{u_name}' सफलता से रजिस्टर हो गया!")
                            
                            # Send Email if Email ID is given
                            if u_email:
                                if send_credentials_email(u_email, u_name, u_pass):
                                    st.info(f"📧 Login Details {u_email} पर भी भेज दी गई हैं।")

                            # Generate WhatsApp Link if Mobile Number is given
                            if u_mobile:
                                app_link = "https://your-app-link.streamlit.app" # Apne deployed app ka link dalein
                                wa_msg = f"नमस्ते {u_name},\n\nआपका Cashbook App का अकाउंट बन गया है।\n\n🔗 Application Link: {app_link}\n👤 User ID: {u_name}\n🔑 Password: {u_pass}\n\nधन्यवाद!"
                                encoded_msg = urllib.parse.quote(wa_msg)
                                wa_url = f"https://wa.me/91{u_mobile}?text={encoded_msg}"
                                
                                st.markdown(f"### 📲 WhatsApp Direct Send Link:\n[👉 यहाँ क्लिक करके {u_name} को WhatsApp पर Login Details भेजें]({wa_url})", unsafe_allow_html=True)
                        
                        except sqlite3.IntegrityError:
                            st.error("❌ यह User ID पहले से मौजूद है! कृपया कोई दूसरा ID चुनें।")
                    else:
                        st.warning("⚠️ कृपया User ID और Password दोनों भरें!")
