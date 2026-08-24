# main.py (Final Streamlit Web Application)
import streamlit as st
import sqlite3
from database import init_db
from admin import Admin
from auth import UserAuth
from cashbook import CashBook
from ledger import Ledger
from dashboard import Dashboard
from reports import ReportGenerator
from idcard import IDCardGenerator

# पेज की सेटिंग
st.set_page_config(page_title="CashBook & ID Card Manager", page_icon="💼", layout="wide")

# 1. डेटाबेस इनिशियलाइज करें
init_db()

# ऑब्जेक्ट्स बनाएं
admin_obj = Admin()
auth_obj = UserAuth()
cb_obj = CashBook()
ledger_obj = Ledger()
dash_obj = Dashboard()
rep_obj = ReportGenerator()
id_gen_obj = IDCardGenerator()

# सेशन स्टेट मैनेज करने के लिए
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""
    st.session_state.role = ""

# --- 1. लॉगिन स्क्रीन (जब तक यूजर लॉगिन नहीं है) ---
if not st.session_state.logged_in:
    st.title("🔐 Software Login")
    
    # पहली बार के लिए डिफ़ॉल्ट एडमिन बना दें (ताकि आप आसानी से लॉगिन कर सकें)
    admin_obj.create_user_with_details(
        name="System Admin", father_name="Admin", aadhar_last4="0000", 
        mobile="9999999999", address="Office", city="City", 
        district="Dist", state="State", pin="000000", role="Admin"
    )

    with st.form("login_form"):
        u_id = st.text_input("User ID")
        pwd = st.text_input("Password (One-Time Password if new)", type="password")
        submit_login = st.form_submit_button("Login")

        if submit_login:
            conn = sqlite3.connect('software_data.db')
            cursor = conn.cursor()
            cursor.execute("SELECT password, role, active FROM users WHERE user_id = ?", (u_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                db_pwd, role, active = result
                if active == 1 and db_pwd == pwd:
                    st.session_state.logged_in = True
                    st.session_state.user_id = u_id
                    st.session_state.role = role
                    st.success(f"Welcome {u_id}!")
                    st.rerun()
                else:
                    st.error("Account blocked or incorrect password!")
            else:
                st.error("User ID not found!")

# --- 2. लॉगिन होने के बाद का पैनल ---
else:
    # साइडबार में यूजर की जानकारी और लॉगआउट बटन
    st.sidebar.title("Navigation")
    st.sidebar.write(f"👤 Logged in: **{st.session_state.user_id}**")
    st.sidebar.write(f"🛡️ Role: **{st.session_state.role}**")
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.user_id = ""
        st.session_state.role = ""
        st.rerun()

    # ==========================================
    # A. अगर लॉगिन करने वाला एडमिन (Admin) है
    # ==========================================
    if st.session_state.role.lower() == "admin":
        st.sidebar.markdown("---")
        admin_menu = st.sidebar.radio("Admin Options", ["👑 Dashboard", "➕ Create New User", "📊 All Reports"])

        if admin_menu == "👑 Dashboard":
            st.title("Admin Dashboard")
            summary = dash_obj.get_summary()
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Income", f"₹ {summary['Total Income']}")
            col2.metric("Total Expense", f"₹ {summary['Total Expense']}")
            col3.metric("Current Balance", f"₹ {summary['Current Balance']}")

        elif admin_menu == "➕ Create New User":
            st.title("➕ Create New User (Admin Panel)")
            st.write("एडमिन यहीं से नए यूजर की पूरी जानकारी भरकर उसकी आईडी और पासवर्ड जनरेट कर सकता है:")

            with st.form("new_user_form"):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("Full Name")
                    father_name = st.text_input("Father's Name")
                    aadhar_last4 = st.text_input("Aadhar Last 4 Digits", max_chars=4)
                    mobile = st.text_input("Mobile Number", max_chars=10)
                    address = st.text_area("Address")
                with col2:
                    city = st.text_input("City")
                    district = st.text_input("District")
                    state = st.text_input("State")
                    pin = st.text_input("PIN Code", max_chars=6)
                    role = st.selectbox("Assign Role", ["User", "Admin"])

                submit_user = st.form_submit_button("Generate ID & Save User")

                if submit_user:
                    if name and mobile:
                        success, u_id, pwd = admin_obj.create_user_with_details(
                            name, father_name, aadhar_last4, mobile, address, city, district, state, pin, role
                        )
                        if success:
                            st.success("User Created Successfully!")
                            st.info(f"**New User ID:** `{u_id}`")
                            st.warning(f"**One-Time Password:** `{pwd}` (इसे नोट करके यूजर को दे दें)")
                        else:
                            st.error(f"Error: {u_id}")
                    else:
                        st.error("Please fill at least Name and Mobile Number.")

        elif admin_menu == "📊 All Reports":
            st.title("System Reports")
            if st.button("Generate Cash Book Report"):
                st.text(rep_obj.generate_cash_book_report())

    # ==========================================
    # B. अगर लॉगिन करने वाला सामान्य यूजर (User) है
    # ==========================================
    else:
        st.sidebar.markdown("---")
        user_menu = st.sidebar.radio("User Menu", ["📈 Dashboard", "💰 Cash Book", "📒 Ledger", "🪪 ID Card Generator"])

        if user_menu == "📈 Dashboard":
            st.title("User Dashboard")
            summary = dash_obj.get_summary()
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Income", f"₹ {summary['Total Income']}")
            col2.metric("Total Expense", f"₹ {summary['Total Expense']}")
            col3.metric("Current Balance", f"₹ {summary['Total Balance']}")

        elif user_menu == "💰 Cash Book":
            st.title("💰 Cash Book Entries")
            with st.form("cashbook_form"):
                date = st.date_input("Date")
                desc = st.text_input("Description / Party Name")
                amount = st.number_input("Amount", min_value=0.0)
                t_type = st.selectbox("Transaction Type", ["IN", "OUT"])
                submit_cb = st.form_submit_button("Save Transaction")

                if submit_cb:
                    res = cb_obj.add_transaction(str(date), desc, amount, t_type)
                    st.success(res)

        elif user_menu == "📒 Ledger":
            st.title("📒 Ledger Accounts")
            with st.form("ledger_form"):
                acc_name = st.text_input("Account Name")
                amount = st.number_input("Amount Entry", min_value=0.0)
                date = st.date_input("Entry Date")
                submit_ledger = st.form_submit_button("Add Ledger Entry")

                if submit_ledger:
                    res = ledger_obj.add_entry(acc_name, str(date), amount)
                    st.success(res)

        elif user_menu == "🪪 ID Card Generator":
            st.title("🪪 ID Card Generator")
            with st.form("idcard_form"):
                name = st.text_input("Full Name")
                role = st.text_input("Role / Designation")
                id_num = st.text_input("ID Number")
                photo = st.text_input("Photo File Name")
                submit_id = st.form_submit_button("Save ID Card Data")

                if submit_id:
                    res = id_gen_obj.save_id_card_data(name, role, id_num, photo)
                    st.success(res)
