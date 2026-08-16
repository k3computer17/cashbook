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
    
    # Accounts/Ledger Table (Updated with Account Type & Tx ID)
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
    
    # Opening Balance Table
    c.execute('''CREATE TABLE IF NOT EXISTS opening_balances (
                    username TEXT PRIMARY KEY,
                    cash_op REAL DEFAULT 0.0,
                    savings_op REAL DEFAULT 0.0,
                    current_op REAL DEFAULT 0.0,
                    od_op REAL DEFAULT 0.0
                )''')
    
    # Default Admin
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role, is_approved) VALUES ('admin', 'admin123', 'Admin', 1)")
    
    conn.commit()
    conn.close()

init_db()

# =========================================================
# 2. HELPER FUNCTIONS FOR LOCAL DB & BALANCES
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
    """पेस्ट टेक्स्ट या PDF से Amount और Transaction ID एक्सट्रैक्ट करता है"""
    amount_match = re.search(r'(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{2})?)', text, re.IGNORECASE)
    tx_match = re.search(r'(?:Txn|Ref|UPI|IMPS|UTR)\s*(?:No|ID)?[:\s]*([A-Za-z0-9]+)', text, re.IGNORECASE)
    
    amount = float(amount_match.group(1).replace(',', '')) if amount_match else 0.0
    tx_id = tx_match.group(1) if tx_match else ""
    return amount, tx_id

def get_user_balances(username):
    """Opening Balance और Transcations के आधार पर Closing Balances की गणना करता है"""
    op = run_query("SELECT * FROM opening_balances WHERE username=?", (username,))
    
    cash_op = op.iloc[0]['cash_op'] if not op.empty else 0.0
    savings_op = op.iloc[0]['savings_op'] if not op.empty else 0.0
    current_op = op.iloc[0]['current_op'] if not op.empty else 0.0
    od_op = op.iloc[0]['od_op'] if not op.empty else 0.0
    
    df = run_query("SELECT * FROM accounts WHERE username=?", (username,))
    
    def calc_balance(acc_name, base_val):
        sub_df = df[df['account_type'] == acc_name]
        dep = sub_df[sub_df['type'] == 'Deposit (जमा)']['amount'].sum()
        wth = sub_df[sub_df['type'] == 'Withdrawal (निकासी)']['amount'].sum()
        return base_val + dep - wth

    return {
        "Cash": {"opening": cash_op, "closing": calc_balance("Cash", cash_op)},
        "Bank Savings": {"opening": savings_op, "closing": calc_balance("Bank Savings", savings_op)},
        "Bank Current": {"opening": current_op, "closing": calc_balance("Bank Current", current_op)},
        "Bank OD": {"opening": od_op, "closing": calc_balance("Bank OD", od_op)}
    }

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
        # BALANCES SUMMARY CARDS
        st.subheader("📊 आपके खातों का Opening एवं Closing बैलेंस")
        balances = get_user_balances(user_id)
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("💵 Cash Balance", f"₹{balances['Cash']['closing']:,}", f"Opening: ₹{balances['Cash']['opening']:,}")
        with c2:
            st.metric("🏦 Bank Savings", f"₹{balances['Bank Savings']['closing']:,}", f"Opening: ₹{balances['Bank Savings']['opening']:,}")
        with c3:
            st.metric("🏦 Bank Current", f"₹{balances['Bank Current']['closing']:,}", f"Opening: ₹{balances['Bank Current']['opening']:,}")
        with c4:
            st.metric("💳 Bank OD", f"₹{balances['Bank OD']['closing']:,}", f"Opening: ₹{balances['Bank OD']['opening']:,}")

        st.write("---")
        
        u_tab1, u_tab2, u_tab3, u_tab4 = st.tabs(["✍️ डेली एंट्री (Manual/Text/PDF)", "📋 कैशबुक (Edit/Delete)", "⚙️ Opening Balance सेट करें", "🪪 ID Card & Excel"])

        # TAB 1: DAILY ENTRY
        with u_tab1:
            st.subheader("➕ नई एंट्री दर्ज करें")
            entry_mode = st.radio("एंट्री मोड चुनें:", ["Manual Form", "Copy-Paste Text", "PDF Upload"], horizontal=True)

            auto_amount = 0.0
            auto_tx_id = ""

            if entry_mode == "Copy-Paste Text":
                pasted_text = st.text_area("यहाँ बैंक का SMS या रसीद का टेक्स्ट पेस्ट करें:")
                if pasted_text:
                    auto_amount, auto_tx_id = parse_text_or_pdf(pasted_text)
                    st.info(f"एक्सट्रैक्ट हुआ -> Amount: ₹{auto_amount} | Txn ID: {auto_tx_id}")

            elif entry_mode == "PDF Upload":
                uploaded_pdf = st.file_uploader("बैंक स्टेटमेंट/रसीद की PDF अपलोड करें:", type=["pdf"])
                if uploaded_pdf:
                    with pdfplumber.open(uploaded_pdf) as pdf:
                        extracted_text = "".join([page.extract_text() or "" for page in pdf.pages])
                    auto_amount, auto_tx_id = parse_text_or_pdf(extracted_text)
                    st.info(f"PDF से एक्सट्रैक्ट हुआ -> Amount: ₹{auto_amount} | Txn ID: {auto_tx_id}")

            with st.form("new_tx_form"):
                fc1, fc2 = st.columns(2)
                with fc1:
                    t_account = st.selectbox("खाता चुनें (Account Type)", ["Cash", "Bank Savings", "Bank Current", "Bank OD"])
                    t_type = st.selectbox("लेनदेन का प्रकार", ["Deposit (जमा)", "Withdrawal (निकासी)"])
                    t_amount = st.number_input("राशि (₹)", min_value=0.0, value=float(auto_amount))
                
                with fc2:
                    t_tx_id = st.text_input("Transaction / UPI / Ref No", value=str(auto_tx_id))
                    t_desc = st.text_input("विवरण / ग्राहक का नाम / नोट")
                    t_date = st.date_input("तारीख", datetime.now())

                if st.form_submit_button("✅ एंट्री सेव करें"):
                    if t_amount > 0:
                        date_str = f"{t_date.strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M')}"
                        execute_db("""INSERT INTO accounts (username, date, type, amount, account_type, tx_id, description) 
                                      VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                                   (user_id, date_str, t_type, t_amount, t_account, t_tx_id, t_desc))
                        st.success("✅ एंट्री सफलतापूर्वक दर्ज हो गई!")
                        st.rerun()
                    else:
                        st.error("⚠️ कृपया सही राशि दर्ज करें!")

        # TAB 2: EDIT / DELETE LEDGER ENTRIES
        with u_tab2:
            st.subheader("📋 आपकी कैशबुक एंट्रीज़")
            my_entries = run_query("SELECT id, date, account_type, type, amount, tx_id, description FROM accounts WHERE username=? ORDER BY id DESC", (user_id,))
            
            if not my_entries.empty:
                st.dataframe(my_entries, use_container_width=True)
                st.write("---")
                
                selected_id = st.selectbox("बदलने या मिटाने के लिए एंट्री ID चुनें:", my_entries['id'].tolist())
                row_to_edit = my_entries[my_entries['id'] == selected_id].iloc[0]

                with st.expander(f"⚙️ Selected Entry ID #{selected_id} का विवरण बदलें"):
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        acc_opts = ["Cash", "Bank Savings", "Bank Current", "Bank OD"]
                        acc_idx = acc_opts.index(row_to_edit['account_type']) if row_to_edit['account_type'] in acc_opts else 0
                        e_acc = st.selectbox("Account Type", acc_opts, index=acc_idx)
                        e_type = st.selectbox("Type", ["Deposit (जमा)", "Withdrawal (निकासी)"], index=0 if "Deposit" in row_to_edit['type'] else 1)
                        e_amount = st.number_input("Amount", value=float(row_to_edit['amount']), key="edit_amt")
                    with e_col2:
                        e_tx = st.text_input("Txn ID", value=str(row_to_edit['tx_id']), key="edit_tx")
                        e_desc = st.text_input("Description", value=str(row_to_edit['description']), key="edit_desc")

                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        if st.button("💾 अपडेट (Update) करें"):
                            execute_db("""UPDATE accounts SET account_type=?, type=?, amount=?, tx_id=?, description=? WHERE id=?""", 
                                       (e_acc, e_type, e_amount, e_tx, e_desc, selected_id))
                            st.success("✅ एंट्री अपडेट हो गई!")
                            st.rerun()
                    
                    with btn_c2:
                        if st.button("🗑️ डिलीट (Delete) करें"):
                            execute_db("DELETE FROM accounts WHERE id=?", (selected_id,))
                            st.warning("⚠️ एंट्री डिलीट कर दी गई!")
                            st.rerun()
            else:
                st.info("अभी कोई एंट्री दर्ज नहीं की गई है।")

        # TAB 3: OPENING BALANCE
        with u_tab3:
            st.subheader("⚙️ Opening Balances सेट करें")
            curr_op = run_query("SELECT * FROM opening_balances WHERE username=?", (user_id,))
            
            op_c = curr_op.iloc[0]['cash_op'] if not curr_op.empty else 0.0
            op_s = curr_op.iloc[0]['savings_op'] if not curr_op.empty else 0.0
            op_cur = curr_op.iloc[0]['current_op'] if not curr_op.empty else 0.0
            op_od = curr_op.iloc[0]['od_op'] if not curr_op.empty else 0.0

            with st.form("op_form"):
                o1, o2 = st.columns(2)
                with o1:
                    new_op_c = st.number_input("Cash Opening Balance (₹)", value=float(op_c))
                    new_op_s = st.number_input("Bank Savings Opening Balance (₹)", value=float(op_s))
                with o2:
                    new_op_cur = st.number_input("Bank Current Opening Balance (₹)", value=float(op_cur))
                    new_op_od = st.number_input("Bank OD Opening Balance (₹)", value=float(op_od))

                if st.form_submit_button("💾 Opening Balances सेव करें"):
                    execute_db("""INSERT INTO opening_balances (username, cash_op, savings_op, current_op, od_op)
                                  VALUES (?, ?, ?, ?, ?)
                                  ON CONFLICT(username) DO UPDATE SET
                                  cash_op=excluded.cash_op,
                                  savings_op=excluded.savings_op,
                                  current_op=excluded.current_op,
                                  od_op=excluded.od_op""",
                               (user_id, new_op_c, new_op_s, new_op_cur, new_op_od))
                    st.success("✅ Opening Balances अपडेट हो गए हैं!")
                    st.rerun()

        # TAB 4: ID CARD & EXCEL DOWNLOAD
        with u_tab4:
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
                st.download_button("📊 Excel डेटा डाउनलोड करें", data=convert_df_to_excel(my_acc), file_name="My_Accounts.xlsx")

    # ------------------ MASTER ADMIN PANEL ------------------
    elif user_role == "Admin":
        st.title("👑 Admin Control Panel")
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["👥 यूजर्स डेटा & ID लिस्ट", "➕ नया यूजर जोड़ें", "📊 खातों का डेटा & Excel"])

        # TAB 1: User IDs & Details List
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
                st.download_button("📥 सभी यूजर्स डेटा Excel Export करें", 
                                   data=convert_df_to_excel(users_data), 
                                   file_name="All_Users_Details.xlsx")
                st.write("---")
                st.dataframe(users_data[['username', 'password', 'client_id', 'name', 'mobile', 'address', 'created_date']], use_container_width=True)
            else:
                st.info("अभी कोई यूजर पंजीकृत नहीं है।")

        # TAB 2: Add New User & WhatsApp Direct Send
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
                        
                        clean_mobile = ''.join(filter(str.isdigit, c_mobile))
                        if len(clean_mobile) == 10:
                            clean_mobile = "91" + clean_mobile
                        
                        whatsapp_msg = f"नमस्ते {c_name},\nआपका NIKA Services अकाउंट बन गया है।\n\n🆔 *User ID:* {c_userid}\n🔑 *Password:* {c_pass}\n🪪 *Client ID:* {auto_id}\n\nधन्यवाद!"
                        encoded_msg = urllib.parse.quote(whatsapp_msg)
                        wa_url = f"https://wa.me/{clean_mobile}?text={encoded_msg}"
                        
                        st.markdown(f'<a href="{wa_url}" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #25D366; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">📲 WhatsApp पर ID & Password भेजें</a>', unsafe_allow_html=True)
                else:
                    st.error("⚠️ सभी फील्ड भरना अनिवार्य है!")

        # TAB 3: Master Accounts Data Export
        with admin_tab3:
            st.subheader("📊 सभी लेनदेन (Master Accounts Data)")
            all_accounts = run_query("SELECT * FROM accounts ORDER BY id DESC")
            st.dataframe(all_accounts, use_container_width=True)
            if not all_accounts.empty:
                st.download_button("📥 Master Transactions Excel डाउनलोड", 
                                   data=convert_df_to_excel(all_accounts), 
                                   file_name="Master_Transactions_Data.xlsx")
