import streamlit as st
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection
import urllib.parse
import pdfplumber
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas

# =========================================================
# 1. PAGE CONFIG & BRANDING
# =========================================================
st.set_page_config(
    page_title="NIKA Accounting & ID/Passbook Portal", 
    page_icon="📄", 
    layout="wide"
)

MY_CONTACT = "8358013017"  # Admin WhatsApp Number
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1GXHT4rDTIu7KghR29PkA0S9AfXTE0mgcKVghTxF63bg/edit?usp=sharing"

# =========================================================
# 2. GOOGLE SHEETS CONNECTION & HELPER FUNCTIONS
# =========================================================
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Google Sheets Connection Error! Streamlit Secrets check karein.")

def load_sheet(sheet_name):
    """Read data from Google Sheets safely"""
    try:
        df = conn.read(spreadsheet=GSHEET_URL, worksheet=sheet_name, ttl=0)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def save_sheet(sheet_name, df):
    """Write/Update data in Google Sheets"""
    try:
        conn.update(spreadsheet=GSHEET_URL, worksheet=sheet_name, data=df)
    except Exception as e:
        st.error(f"डेटा अपडेट करने में समस्या आई: {e}")

def create_whatsapp_link(mobile, text_msg):
    return f"https://wa.me/{mobile}?text={urllib.parse.quote(text_msg)}"

def generate_auto_client_id(clients_df):
    count = len(clients_df) if not clients_df.empty else 0
    return f"NK-CUST-{1001 + count}"

# --- HELPER: GENERATE ID CARD PDF ---
def generate_id_card_pdf(name, client_id, mobile, address):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(250, 160)) # ID Card Dimensions
    c.rect(5, 5, 240, 150)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20, 135, "NIKA SERVICES - ID CARD")
    c.setLineWidth(0.5)
    c.line(20, 128, 230, 128)
    
    c.setFont("Helvetica", 10)
    c.drawString(20, 105, f"ID No: {client_id}")
    c.drawString(20, 85, f"Name: {name}")
    c.drawString(20, 65, f"Mobile: {mobile}")
    c.drawString(20, 45, f"Address: {address[:25]}...")
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# --- HELPER: EXCEL CONVERTER ---
def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# =========================================================
# 3. AUTHENTICATION & SESSION STATE INITIALIZATION
# =========================================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None

st.title("📄 NIKA Multi-Service, Accounts & ID Generator")

# Load Worksheets Data
users_df = load_sheet("users")
clients_df = load_sheet("Clients")
accounts_df = load_sheet("Accounts")  # Daily Accounts Sheet

# =========================================================
# 4. LOGIN & NEW REGISTRATION
# =========================================================
if not st.session_state['logged_in']:
    tab_user_login, tab_admin_login, reg_tab = st.tabs([
        "👤 User Login", 
        "🔐 Admin Login", 
        "📝 New Registration"
    ])

    # ---------------- USER LOGIN ----------------
    with tab_user_login:
        st.subheader("👤 यूजर लॉगिन")
        c_username = st.text_input("User ID", key="c_login_user")
        c_password = st.text_input("Password", type="password", key="c_login_pass")
        
        if st.button("🚀 User Login", key="c_login_btn"):
            if not users_df.empty:
                user_match = users_df[
                    (users_df['username'].astype(str) == c_username) & 
                    (users_df['password'].astype(str) == c_password) & 
                    (users_df['role'].astype(str) == "Customer")
                ]
                if not user_match.empty:
                    user_row = user_match.iloc[0]
                    if int(user_row.get('is_approved', 0)) == 1:
                        st.session_state['logged_in'] = True
                        st.session_state['user_info'] = user_row.to_dict()
                        st.success("✅ लॉगिन सफल हुआ!")
                        st.rerun()
                    else:
                        st.warning("⚠️ आपका खाता अभी स्वीकृति (Approval) के लिए पेंडिंग है।")
                else:
                    st.error("❌ गलत Username या Password!")

    # ---------------- ADMIN LOGIN ----------------
    with tab_admin_login:
        st.subheader("🔐 एडमिन लॉगिन")
        a_username = st.text_input("Admin User ID", key="a_login_user")
        a_password = st.text_input("Admin Password", type="password", key="a_login_pass")
        
        if st.button("👑 Admin Login", key="a_login_btn"):
            if not users_df.empty:
                user_match = users_df[
                    (users_df['username'].astype(str) == a_username) & 
                    (users_df['password'].astype(str) == a_password) & 
                    (users_df['role'].astype(str) == "Admin")
                ]
                if not user_match.empty:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = user_match.iloc[0].to_dict()
                    st.success("✅ एडमिन लॉगिन सफल ہوا!")
                    st.rerun()

    # ---------------- NEW REGISTRATION ----------------
    with reg_tab:
        st.subheader("📝 नया अकाउंट रजिस्ट्रेशन")
        auto_id = generate_auto_client_id(clients_df)
        
        col1, col2 = st.columns(2)
        with col1:
            c_name = st.text_input("👤 पूरा नाम *")
            c_mobile = st.text_input("📱 मोबाइल नंबर *")
        with col2:
            c_userid = st.text_input("🧑‍💻 User ID बनाएं *")
            c_pass = st.text_input("🔑 Password बनाएं *", type="password")

        c_address = st.text_area("🏠 पता *")

        if st.button("✨ Register Account"):
            if not all([c_name, c_userid, c_pass, c_mobile, c_address]):
                st.error("कृपया सभी जानकारी भरें!")
            else:
                today = datetime.now().strftime("%Y-%m-%d")
                new_client = {
                    "id": len(clients_df) + 1,
                    "unique_client_id": auto_id,
                    "name": c_name,
                    "mobile": c_mobile,
                    "address": c_address,
                    "created_date": today
                }
                save_sheet("Clients", pd.concat([clients_df, pd.DataFrame([new_client])], ignore_index=True))

                new_user = {
                    "id": len(users_df) + 1,
                    "username": c_userid,
                    "password": c_pass,
                    "role": "Customer",
                    "client_id": auto_id,
                    "is_approved": 0
                }
                save_sheet("users", pd.concat([users_df, pd.DataFrame([new_user])], ignore_index=True))
                st.success(f"✅ रजिस्ट्रेशन सफल हुआ! ID: {auto_id}")

# =========================================================
# 5. AUTHENTICATED PORTAL
# =========================================================
else:
    st.sidebar.write(f"Logged in: **{st.session_state['user_info']['username']}** ({st.session_state['user_info']['role']})")
    if st.sidebar.button("🚪 Logout"):
        st.session_state['logged_in'] = False
        st.session_state['user_info'] = None
        st.rerun()

    user_role = st.session_state['user_info']['role']
    user_id = st.session_state['user_info']['username']

    # ---------------------------------------------------------
    # USER DASHBOARD
    # ---------------------------------------------------------
    if user_role == "Customer":
        u_tab1, u_tab2, u_tab3 = st.tabs(["📊 दैनिक हिसाब-किताब", "📁 PDF अपलोड व ID Generator", "📥 Excel डाउनलोड"])

        # ------------ 1. DAILY ACCOUNTS ------------
        with u_tab1:
            st.subheader("📊 दैनिक आय-व्यय ट्रैकर")
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                t_type = st.selectbox("प्रकार", ["Income (आय)", "Expense (खर्च)"])
            with col_b:
                t_amount = st.number_input("राशि (₹)", min_value=1.0, step=10.0)
            with col_c:
                t_desc = st.text_input("विवरण (Note)")

            if st.button("➕ एंट्री सेव करें"):
                new_entry = {
                    "username": user_id,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "type": t_type,
                    "amount": t_amount,
                    "description": t_desc
                }
                updated_acc = pd.concat([accounts_df, pd.DataFrame([new_entry])], ignore_index=True)
                save_sheet("Accounts", updated_acc)
                st.success("✅ हिसाब सेव हो गया!")
                st.rerun()

            st.markdown("---")
            st.subheader("📋 आपकी पुरानी एंट्रीज")
            if not accounts_df.empty and 'username' in accounts_df.columns:
                my_acc = accounts_df[accounts_df['username'] == user_id]
                st.dataframe(my_acc, use_container_width=True)

        # ------------ 2. PDF UPLOAD & ID CARD GENERATOR ------------
        with u_tab2:
            st.subheader("📁 नया PDF अपलोड करें (डेटा एक्सट्रैक्शन)")
            uploaded_pdf = st.file_uploader("PDF फ़ाइल चुनें", type=["pdf"])

            if uploaded_pdf is not None:
                with pdfplumber.open(uploaded_pdf) as pdf:
                    extracted_text = ""
                    for page in pdf.pages:
                        extracted_text += page.extract_text() or ""
                
                st.success("✅ PDF से डेटा एक्सट्रैक्ट हो गया!")
                st.text_area("एक्सट्रैक्ट किया गया टेक्स्ट:", extracted_text, height=150)

            st.markdown("---")
            st.subheader("🪪 ID Card / Passbook जनरेट करें")
            client_data = clients_df[clients_df['unique_client_id'] == st.session_state['user_info'].get('client_id')] if not clients_df.empty else pd.DataFrame()

            if not client_data.empty:
                c_row = client_data.iloc[0]
                pdf_bytes = generate_id_card_pdf(c_row['name'], c_row['unique_client_id'], c_row['mobile'], c_row['address'])
                
                st.download_button(
                    label="🪪 ID Card PDF डाउनलोड करें",
                    data=pdf_bytes,
                    file_name=f"ID_Card_{c_row['unique_client_id']}.pdf",
                    mime="application/pdf"
                )

        # ------------ 3. EXCEL DOWNLOAD ------------
        with u_tab3:
            st.subheader("📥 अपना डेटा Excel में डाउनलोड करें")
            if not accounts_df.empty and 'username' in accounts_df.columns:
                my_acc = accounts_df[accounts_df['username'] == user_id]
                excel_data = convert_df_to_excel(my_acc)
                st.download_button(
                    label="📊 Accounts Data (Excel) डाउनलोड करें",
                    data=excel_data,
                    file_name=f"My_Accounts_{user_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    # ---------------------------------------------------------
    # MASTER ADMIN DASHBOARD
    # ---------------------------------------------------------
    elif user_role == "Admin":
        st.sidebar.title("👑 Master Admin Control")
        admin_choice = st.sidebar.radio("Navigation", ["👥 सभी यूजर्स का डेटा", "⚙️ Approvals", "📊 मास्टर Excel डाउनलोड"])

        if admin_choice == "👥 सभी यूजर्स का डेटा":
            st.title("👥 सभी यूजर्स का हिसाब-किताब")
            st.dataframe(accounts_df, use_container_width=True)

        elif admin_choice == "⚙️ Approvals":
            st.title("⚙️ Pending Approvals")
            if not users_df.empty and 'is_approved' in users_df.columns:
                pending = users_df[users_df['is_approved'].fillna(0).astype(int) == 0]
                for idx, row in pending.iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"User: **{row['username']}** | Client ID: {row.get('client_id')}")
                    with col2:
                        if st.button(f"Approve", key=f"app_{row['id']}"):
                            users_df.loc[users_df['id'] == row['id'], 'is_approved'] = 1
                            save_sheet("users", users_df)
                            st.success("Approved!")
                            st.rerun()

        elif admin_choice == "📊 मास्टर Excel डाउनलोड":
            st.title("📊 पूरे सिस्टम का Excel डेटा")
            if not accounts_df.empty:
                master_excel = convert_df_to_excel(accounts_df)
                st.download_button(
                    label="📥 पूरा Accounts Data Excel में डाउनलोड करें",
                    data=master_excel,
                    file_name="Master_Accounts_Data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
