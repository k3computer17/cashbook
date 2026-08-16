import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import os
import io
import re
import urllib.parse
import pdfplumber
from reportlab.pdfgen import canvas

# =========================================================
# 1. LOCAL DATABASE INITIALIZATION
# =========================================================
DB_NAME = "local_cashbook.db"

def init_db():
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
    
    # Accounts / Cashbook Table
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    date TEXT,
                    type TEXT,            
                    amount REAL,
                    account_type TEXT,    
                    tx_id TEXT,
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
    
    # Default Admin
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role, is_approved) VALUES ('admin', 'admin123', 'Admin', 1)")
    
    conn.commit()
    conn.close()

init_db()

# =========================================================
# 2. HELPER FUNCTIONS & AUTOMATIC BALANCING LOGIC
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

def parse_text_or_pdf(text):
    amount_match = re.search(r'(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{2})?)', text, re.IGNORECASE)
    tx_match = re.search(r'(?:Txn|Ref|UPI|IMPS|UTR)\s*(?:No|ID)?[:\s]*([A-Za-z0-9]+)', text, re.IGNORECASE)
    
    amount = float(amount_match.group(1).replace(',', '')) if amount_match else 0.0
    tx_id = tx_match.group(1) if tx_match else ""
    return amount, tx_id

def calculate_exact_balances(username):
    op = run_query("SELECT * FROM opening_balances WHERE username=?", (username,))
    cash_op = op.iloc[0]['cash_op'] if not op.empty else 0.0
    bank_op = op.iloc[0]['bank_op'] if not op.empty else 0.0
    
    acc_df = run_query("SELECT * FROM accounts WHERE username=?", (username,))
    serv_df = run_query("SELECT * FROM daily_services WHERE username=?", (username,))
    
    # Daily Services Income (Adds directly to Cash)
    services_cash_income = serv_df['income_amount'].sum() if not serv_df.empty else 0.0
    
    # General Cash Transactions
    cash_df = acc_df[acc_df['account_type'] == 'Cash'] if not acc_df.empty else pd.DataFrame()
    cash_dep = cash_df[cash_df['type'] == 'Deposit (जमा)']['amount'].sum() if not cash_df.empty else 0.0
    cash_wth = cash_df[cash_df['type'] == 'Withdrawal (निकासी)']['amount'].sum() if not cash_df.empty else 0.0
    personal_gullak = cash_df[cash_df['type'] == 'Personal Use / Gullak (निजी खर्च/गुल्लक)']['amount'].sum() if not cash_df.empty else 0.0
    
    # Bank & AEPS Transactions
    bank_df = acc_df[acc_df['account_type'] == 'Bank Account'] if not acc_df.empty else pd.DataFrame()
    
    # Own Bank Cash Withdrawal (Self Bank se Cash nikala) -> Bank(-), Cash(+)
    bank_wth = bank_df[bank_df['type'] == 'Withdrawal (बैंक से पैसा निकाला / Cash Laye)']['amount'].sum() if not bank_df.empty else 0.0
    
    # Own Bank Cash Deposit (Bank me Cash jamha kiya) -> Bank(+), Cash(-)
    bank_dep = bank_df[bank_df['type'] == 'Deposit (बैंक में जमा किया)']['amount'].sum() if not bank_df.empty else 0.0
    
    # Customer AEPS/Micro ATM Withdrawal -> Bank(+), Cash(-) AUTOMATIC
    cust_aeps_wth = bank_df[bank_df['type'] == 'Customer AEPS Withdrawal (बैंक बढ़ा / नकद घटा)']['amount'].sum() if not bank_df.empty else 0.0
    
    # Customer Cash Deposit -> Bank(-), Cash(+) AUTOMATIC
    cust_cash_dep = bank_df[bank_df['type'] == 'Customer Money Transfer / Deposit (बैंक घटा / नकद बढ़ा)']['amount'].sum() if not bank_df.empty else 0.0

    # AUTOMATIC BALANCING MATH
    # Cash Closing = Cash OP + General Dep + Services Income + Self Bank Cash Withdrawal + Cust Money Transfer - General Wth - Personal Gullak - Self Bank Deposit - Cust AEPS Withdrawal
    final_cash_closing = cash_op + cash_dep + services_cash_income + bank_wth + cust_cash_dep - cash_wth - personal_gullak - bank_dep - cust_aeps_wth
    
    # Bank Closing = Bank OP + Self Bank Deposit + Cust AEPS Withdrawal - Self Bank Cash Withdrawal - Cust Money Transfer
    final_bank_closing = bank_op + bank_dep + cust_aeps_wth - bank_wth - cust_cash_dep
    
    return {
        "cash_op": cash_op,
        "cash_closing": final_cash_closing,
        "bank_op": bank_op,
        "bank_closing": final_bank_closing,
        "services_income": services_cash_income,
        "personal_gullak": personal_gullak
    }

# =========================================================
# 3. PAGE CONFIG & LOGIN
# =========================================================
st.set_page_config(page_title="Cashbook & Services Manager", page_icon="💻", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None

st.title("💻 PC Accounting & Daily Services System")

if not st.session_state['logged_in']:
    tab_user_login, tab_admin_login = st.tabs(["👤 User Login", "🔐 Admin Login"])

    with tab_user_login:
        c_username = st.text_input("User ID", key="c_user")
        c_password = st.text_input("Password", type="password", key="c_pass")
        if st.button("User Login"):
            users_df = run_query("SELECT * FROM users WHERE username=? AND password=? AND role='Customer'", (c_username, c_password))
            if not users_df.empty:
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = users_df.iloc[0].to_dict()
                st.rerun()
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
                st.rerun()
            else:
                st.error("❌ गलत Admin विवरण!")

# =========================================================
# 4. DASHBOARD
# =========================================================
else:
    st.sidebar.write(f"Logged in: **{st.session_state['user_info']['username']}**")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.session_state['user_info'] = None
        st.rerun()

    user_role = st.session_state['user_info']['role']
    user_id = st.session_state['user_info']['username']

    # ------------------ CUSTOMER DASHBOARD ------------------
    if user_role == "Customer":
        b_data = calculate_exact_balances(user_id)
        
        st.subheader("📊 आपके Cash और Bank का रियल-टाइम बैलेंस")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("💵 Cash Balance", f"₹{b_data['cash_closing']:,}", f"Opening: ₹{b_data['cash_op']:,}")
        with c2:
            st.metric("🏦 Bank Balance", f"₹{b_data['bank_closing']:,}", f"Opening: ₹{b_data['bank_op']:,}")
        with c3:
            st.metric("💼 Total Service Income", f"₹{b_data['services_income']:,}")
        with c4:
            st.metric("🏺 Gullak / Personal Exp", f"₹{b_data['personal_gullak']:,}")

        st.write("---")
        
        u_tab1, u_tab2, u_tab3, u_tab4, u_tab5 = st.tabs([
            "✍️ Cash & Bank Entry", 
            "🛠️ Daily Services Work Window", 
            "📋 Ledger & Edit/Delete", 
            "⚙️ Opening Balance सेट करें", 
            "🪪 ID Card & Excel"
        ])

        # TAB 1: CASH & BANK ENTRY
        with u_tab1:
            st.subheader("➕ Cash & Bank Transactions")
            entry_mode = st.radio("इनपुट टाइप:", ["Manual Form", "Copy-Paste Text", "PDF Upload"], horizontal=True)

            auto_amount, auto_tx_id = 0.0, ""
            if entry_mode == "Copy-Paste Text":
                pasted_text = st.text_area("बैंक मैसेज या रसीद पेस्ट करें:")
                if pasted_text:
                    auto_amount, auto_tx_id = parse_text_or_pdf(pasted_text)
            elif entry_mode == "PDF Upload":
                uploaded_pdf = st.file_uploader("PDF अपलोड करें:", type=["pdf"])
                if uploaded_pdf:
                    with pdfplumber.open(uploaded_pdf) as pdf:
                        extracted_text = "".join([page.extract_text() or "" for page in pdf.pages])
                    auto_amount, auto_tx_id = parse_text_or_pdf(extracted_text)

            with st.form("cash_bank_form"):
                fc1, fc2 = st.columns(2)
                with fc1:
                    t_account = st.selectbox("Account Type", ["Bank Account", "Cash"])
                    if t_account == "Bank Account":
                        t_type = st.selectbox("लेनदेन का प्रकार", [
                            "Customer AEPS Withdrawal (बैंक बढ़ा / नकद घटा)",
                            "Customer Money Transfer / Deposit (बैंक घटा / नकद बढ़ा)",
                            "Withdrawal (बैंक से पैसा निकाला / Cash Laye)", 
                            "Deposit (बैंक में जमा किया)"
                        ])
                    else:
                        t_type = st.selectbox("लेनदेन का प्रकार", [
                            "Deposit (जमा)", 
                            "Withdrawal (निकासी)", 
                            "Personal Use / Gullak (निजी खर्च/गुल्लक)"
                        ])
                    
                    t_amount = st.number_input("राशि (₹)", min_value=0.0, value=float(auto_amount))
                
                with fc2:
                    t_tx_id = st.text_input("Txn / Ref / UPI No", value=str(auto_tx_id))
                    t_desc = st.text_input("विवरण / कस्टमर का नाम / नोट")
                    t_date = st.date_input("तारीख", datetime.now())

                if st.form_submit_button("✅ ट्रांजैक्शन सेव करें"):
                    if t_amount > 0:
                        date_str = f"{t_date.strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M')}"
                        execute_db("""INSERT INTO accounts (username, date, type, amount, account_type, tx_id, description) 
                                      VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                                   (user_id, date_str, t_type, t_amount, t_account, t_tx_id, t_desc))
                        st.success("✅ एंट्री सेव हो गई!")
                        st.rerun()

        # TAB 2: DAILY SERVICES WORK WINDOW
        with u_tab2:
            st.subheader("🛠️ आज के कार्य की एंट्री (Daily Services Work Log)")
            
            with st.form("services_log_form"):
                sc1, sc2 = st.columns(2)
                with sc1:
                    service_cat = st.selectbox("सर्विस का प्रकार चुनें *", [
                        "PMJJBY", "PMSBY", "APY", "KYC", "CKYC", "Loan Lead",
                        "PAN Card (Other Service)", "Aadhaar Card (Other Service)", 
                        "Online Service (Other)", "Other Services"
                    ])
                    s_ref = st.text_input("कस्टमर नाम / रेफरेंस / सर्वर No *")
                with sc2:
                    s_income = st.number_input("प्राप्त शुल्क/आय (₹ - Cash में जुड़ेगा) *", min_value=0.0)
                    s_notes = st.text_input("अतिरिक्त नोट")

                if st.form_submit_button("💼 सर्विस कार्य दर्ज करें"):
                    if s_income >= 0 and s_ref:
                        today_time = datetime.now().strftime('%Y-%m-%d %H:%M')
                        execute_db("""INSERT INTO daily_services (username, date, service_name, ref_no, income_amount, notes) 
                                      VALUES (?, ?, ?, ?, ?, ?)""",
                                   (user_id, today_time, service_cat, s_ref, s_income, s_notes))
                        st.success("✅ कार्य दर्ज किया गया और शुल्क Cash में जुड़ गया!")
                        st.rerun()

            st.write("---")
            st.subheader("📊 आज का सर्विसेस लॉग")
            serv_data = run_query("SELECT date, service_name, ref_no, income_amount, notes FROM daily_services WHERE username=? ORDER BY id DESC", (user_id,))
            st.dataframe(serv_data, use_container_width=True)

        # TAB 3: LEDGER & EDIT/DELETE
        with u_tab3:
            st.subheader("📋 आपकी कैशबुक एंट्रीज़")
            my_entries = run_query("SELECT id, date, account_type, type, amount, tx_id, description FROM accounts WHERE username=? ORDER BY id DESC", (user_id,))
            
            if not my_entries.empty:
                st.dataframe(my_entries, use_container_width=True)
                st.write("---")
                
                selected_id = st.selectbox("बदलने/मिटाने के लिए ID चुनें:", my_entries['id'].tolist())
                row_to_edit = my_entries[my_entries['id'] == selected_id].iloc[0]

                with st.expander(f"⚙️ Entry ID #{selected_id} संपादित करें"):
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        e_acc = st.selectbox("Account Type", ["Bank Account", "Cash"], index=0 if row_to_edit['account_type']=="Bank Account" else 1)
                        if e_acc == "Bank Account":
                            e_type = st.selectbox("Type", [
                                "Customer AEPS Withdrawal (बैंक बढ़ा / नकद घटा)",
                                "Customer Money Transfer / Deposit (बैंक घटा / नकद बढ़ा)",
                                "Withdrawal (बैंक से पैसा निकाला / Cash Laye)", 
                                "Deposit (बैंक में जमा किया)"
                            ])
                        else:
                            e_type = st.selectbox("Type", ["Deposit (जमा)", "Withdrawal (निकासी)", "Personal Use / Gullak (निजी खर्च/गुल्लक)"])
                        
                        e_amount = st.number_input("Amount", value=float(row_to_edit['amount']), key="edit_amt")
                    with e_col2:
                        e_tx = st.text_input("Txn ID", value=str(row_to_edit['tx_id']), key="edit_tx")
                        e_desc = st.text_input("Description", value=str(row_to_edit['description']), key="edit_desc")

                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        if st.button("💾 अपडेट करें"):
                            execute_db("UPDATE accounts SET account_type=?, type=?, amount=?, tx_id=?, description=? WHERE id=?", 
                                       (e_acc, e_type, e_amount, e_tx, e_desc, selected_id))
                            st.success("✅ अपडेट हो गया!")
                            st.rerun()
                    with btn_c2:
                        if st.button("🗑️ डिलीट करें"):
                            execute_db("DELETE FROM accounts WHERE id=?", (selected_id,))
                            st.warning("⚠️ डिलीट कर दिया गया!")
                            st.rerun()

        # TAB 4: OPENING BALANCES SETTINGS
        with u_tab4:
            st.subheader("⚙️ Opening Balances सेट करें")
            curr_op = run_query("SELECT * FROM opening_balances WHERE username=?", (user_id,))
            
            op_c = curr_op.iloc[0]['cash_op'] if not curr_op.empty else 0.0
            op_b = curr_op.iloc[0]['bank_op'] if not curr_op.empty else 0.0

            with st.form("op_form"):
                o1, o2 = st.columns(2)
                with o1:
                    new_op_c = st.number_input("Cash Opening Balance (₹)", value=float(op_c))
                with o2:
                    new_op_b = st.number_input("Bank Opening Balance (₹)", value=float(op_b))

                if st.form_submit_button("💾 Opening Balances सेव करें"):
                    execute_db("""INSERT INTO opening_balances (username, cash_op, bank_op) VALUES (?, ?, ?)
                                  ON CONFLICT(username) DO UPDATE SET cash_op=excluded.cash_op, bank_op=excluded.bank_op""",
                               (user_id, new_op_c, new_op_b))
                    st.success("✅ Opening Balances अपडेट हो गए हैं!")
                    st.rerun()

        # TAB 5: ID CARD & EXCEL DOWNLOAD
        with u_tab5:
            st.subheader("🪪 ID Card Download")
            client_df = run_query("SELECT * FROM clients WHERE unique_client_id=?", (st.session_state['user_info'].get('client_id'),))
            if not client_df.empty:
                c_row = client_df.iloc[0]
                pdf = generate_id_card_pdf(c_row['name'], c_row['unique_client_id'], c_row['mobile'], c_row['address'])
                st.download_button("🪪 ID Card Download करें", data=pdf, file_name=f"ID_{c_row['unique_client_id']}.pdf")
            
            st.write("---")
            st.subheader("📊 Excel Data Download")
            my_acc = run_query("SELECT * FROM accounts WHERE username=?", (user_id,))
            if not my_acc.empty:
                st.download_button("📊 Cashbook Excel डाउनलोड करें", data=convert_df_to_excel(my_acc), file_name="My_Accounts.xlsx")

    # ------------------ MASTER ADMIN PANEL ------------------
    elif user_role == "Admin":
        st.title("👑 Master Admin Control Panel")
        admin_tab1, admin_tab2, admin_tab3, admin_tab4 = st.tabs([
            "👥 यूजर्स ID लिस्ट", 
            "➕ नया यूजर जोड़ें", 
            "📊 मास्टर Cashbook Ledger", 
            "🛠️ यूजर Services वर्क रिपोर्ट"
        ])

        # ADMIN TAB 1: USERS LIST
        with admin_tab1:
            st.subheader("👥 सभी Registered Users")
            users_data = run_query("""SELECT u.id, u.username, u.password, u.client_id, c.name, c.mobile, c.address, c.created_date 
                                      FROM users u LEFT JOIN clients c ON u.client_id = c.unique_client_id 
                                      WHERE u.role = 'Customer' ORDER BY u.id DESC""")
            if not users_data.empty:
                st.download_button("📥 All Users Excel Export", data=convert_df_to_excel(users_data), file_name="All_Users_Details.xlsx")
                st.dataframe(users_data, use_container_width=True)

        # ADMIN TAB 2: ADD USER & WHATSAPP
        with admin_tab2:
            st.subheader("➕ नया यूजर जोड़ें")
            with st.form("add_user_form"):
                ac1, ac2 = st.columns(2)
                with ac1:
                    c_name = st.text_input("ग्राहक नाम *")
                    c_mobile = st.text_input("मोबाइल नंबर (WhatsApp) *")
                    c_address = st.text_area("पता *")
                with ac2:
                    c_userid = st.text_input("User ID *")
                    c_pass = st.text_input("Password *")

                if st.form_submit_button("पंजीकृत करें"):
                    if all([c_name, c_mobile, c_userid, c_pass, c_address]):
                        auto_id = f"NK-CUST-{1001 + len(run_query('SELECT * FROM clients'))}"
                        today = datetime.now().strftime("%Y-%m-%d")
                        execute_db("INSERT INTO clients (unique_client_id, name, mobile, address, created_date) VALUES (?, ?, ?, ?, ?)", (auto_id, c_name, c_mobile, c_address, today))
                        execute_db("INSERT INTO users (username, password, role, client_id, is_approved) VALUES (?, ?, 'Customer', ?, 1)", (c_userid, c_pass, auto_id))
                        st.success(f"✅ यूजर बन गया! Client ID: {auto_id}")
                        
                        clean_mobile = ''.join(filter(str.isdigit, c_mobile))
                        if len(clean_mobile) == 10:
                            clean_mobile = "91" + clean_mobile
                        msg = f"नमस्ते {c_name},\nआपका NIKA Services अकाउंट बन गया है।\n\n🆔 *User ID:* {c_userid}\n🔑 *Password:* {c_pass}\n🪪 *Client ID:* {auto_id}"
                        wa_url = f"https://wa.me/{clean_mobile}?text={urllib.parse.quote(msg)}"
                        st.markdown(f'<a href="{wa_url}" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #25D366; color: white; border-radius: 5px; text-decoration: none; font-weight: bold;">📲 WhatsApp पर विवरण भेजें</a>', unsafe_allow_html=True)

        # ADMIN TAB 3: MASTER ACCOUNTS LEDGER REPORT
        with admin_tab3:
            st.subheader("📊 यूजर्स का मास्टर Cashbook Ledger")
            all_accounts = run_query("SELECT * FROM accounts ORDER BY id DESC")
            st.dataframe(all_accounts, use_container_width=True)
            if not all_accounts.empty:
                st.download_button("📥 Master Cashbook Excel", data=convert_df_to_excel(all_accounts), file_name="Master_Accounts.xlsx")

        # ADMIN TAB 4: SERVICES WORK REPORT
        with admin_tab4:
            st.subheader("🛠️ यूजर सर्विसेस वर्क रिपोर्ट (Services Report)")
            all_services = run_query("SELECT * FROM daily_services ORDER BY id DESC")
            st.dataframe(all_services, use_container_width=True)
            if not all_services.empty:
                st.download_button("📥 Services Work Report Excel", data=convert_df_to_excel(all_services), file_name="Services_Report.xlsx")
