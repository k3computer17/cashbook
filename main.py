# main.py (Streamlit Web Version with Role-based Access)
import streamlit as st
from database import init_db
from admin import Admin
from auth import UserAuth
from cashbook import CashBook
from ledger import Ledger
from dashboard import Dashboard
from reports import ReportGenerator
from idcard import IDCardGenerator

# 1. डेटाबेस इनिशियलाइज करें
init_db()

st.title("💼 CashBook & ID Card Management System")

# ऑब्जेक्ट्स बनाएं
admin_obj = Admin()
auth_obj = UserAuth()
cb_obj = CashBook()
ledger_obj = Ledger()
dash_obj = Dashboard()
rep_obj = ReportGenerator()
id_gen_obj = IDCardGenerator()

# सेशन स्टेट में लॉगिन स्टेटस ट्रैक करने के लिए
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""
    st.session_state.role = ""

# --- लॉगिन स्क्रीन ---
if not st.session_state.logged_in:
    st.subheader("🔐 Please Login to Continue")
    
    # पहली बार के लिए डिफ़ॉल्ट एडमिन बना दें ताकि आसानी हो
    admin_obj.create_user("admin", "1234", "Admin")

    u_id = st.text_input("User ID")
    pwd = st.text_input("Password", type="password")

    if st.button("Login"):
        # डेटाबेस से चेक करें
        import sqlite3
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
                st.success(f"Welcome {u_id} ({role})!")
                st.rerun()
            else:
                st.error("Account blocked or incorrect password!")
        else:
            st.error("User ID not found!")

# --- लॉगिन होने के बाद का पैनल ---
else:
    st.sidebar.write(f"👤 Logged in as: **{st.session_state.user_id}**")
    st.sidebar.write(f"🛡️ Role: **{st.session_state.role}**")
    
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user_id = ""
        st.session_state.role = ""
        st.rerun()

    # 1. अगर यूज़र 'Admin' है तो उसे एडमिन पैनल और नए यूज़र बनाने का ऑप्शन मिलेगा
    if st.session_state.role.lower() == "admin":
        st.sidebar.header("Admin Controls")
        menu = st.sidebar.selectbox("Choose Action", ["Dashboard", "Create New User", "All Reports"])

        if menu == "Dashboard":
            st.subheader("👑 Admin Dashboard")
            summary = dash_obj.get_summary()
            st.json(summary)

        elif menu == "Create New User":
            st.subheader("➕ Create New User / Admin ID")
            new_uid = st.text_input("New User ID")
            new_pwd = st.text_input("New Password", type="password")
            new_role = st.selectbox("Role", ["User", "Admin"])

            if st.button("Create User"):
                if new_uid and new_pwd:
                    res = admin_obj.create_user(new_uid, new_pwd, new_role)
                    st.success(res)
                else:
                    st.error("Please fill all fields.")

        elif menu == "All Reports":
            st.subheader("📊 System Reports")
            if st.button("Get Cash Book Report"):
                st.text(rep_obj.generate_cash_book_report())

    # 2. अगर यूज़र सामान्य 'User' है तो उसे कैशबुक, आईडी कार्ड और सारी चीज़ें मिलेंगी
    else:
        st.sidebar.header("User Menu")
        menu = st.sidebar.selectbox("Choose Module", ["Dashboard", "Cash Book", "Ledger", "ID Card Generator"])

        if menu == "Dashboard":
            st.subheader("📈 My Dashboard")
            summary = dash_obj.get_summary()
            st.json(summary)

        elif menu == "Cash Book":
            st.subheader("💰 Cash Book Entries")
            date = st.date_input("Date")
            desc = st.text_input("Description / Party Name")
            amount = st.number_input("Amount", min_value=0.0)
            t_type = st.selectbox("Transaction Type", ["IN", "OUT"])

            if st.button("Save Transaction"):
                res = cb_obj.add_transaction(str(date), desc, amount, t_type)
                st.success(res)

        elif menu == "Ledger":
            st.subheader("📒 Ledger Accounts")
            acc_name = st.text_input("Account Name")
            amount = st.number_input("Amount Entry", min_value=0.0)
            date = st.date_input("Entry Date")

            if st.button("Add Ledger Entry"):
                res = ledger_obj.add_entry(acc_name, str(date), amount)
                st.success(res)

        elif menu == "ID Card Generator":
            st.subheader("🪪 ID Card Generator")
            name = st.text_input("Full Name")
            role = st.text_input("Role / Designation")
            id_num = st.text_input("ID Number")
            photo = st.text_input("Photo File Name")

            if st.button("Save ID Card Data"):
                res = id_gen_obj.save_id_card_data(name, role, id_num, photo)
                st.success(res)
