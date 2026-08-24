# main.py (Streamlit Web Version)
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

st.title("💼 CashBook & ID Card Manager")
st.sidebar.header("Navigation")
menu = st.sidebar.selectbox("Choose Module", ["Login / Dashboard", "Cash Book", "ID Card Generator", "Reports"])

# ऑब्जेक्ट्स बनाएं
admin = Admin()
auth = UserAuth()
cb = CashBook()
ledger = Ledger()
dash = Dashboard()
rep = ReportGenerator()
id_gen = IDCardGenerator()

if menu == "Login / Dashboard":
    st.subheader("User Authentication & Summary")
    
    # लॉगिन फॉर्म
    user_id = st.text_input("User ID")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        # अगर एडमिन नहीं है तो पहले टेस्ट यूजर बना दें
        admin.create_user("admin01", "1234", "Admin")
        
        # लॉगिन चेक करें
        login_msg = auth.login(user_id, password)
        if "successful" in login_msg:
            st.success(login_msg)
            
            # डैशबोर्ड समरी दिखाएं
            summary = dash.get_summary()
            st.write("### Financial Summary")
            st.json(summary)
        else:
            st.error(login_msg)

elif menu == "Cash Book":
    st.subheader("Cash Book Entry")
    date = st.date_input("Date")
    desc = st.text_input("Description")
    amount = st.number_input("Amount", min_value=0.0)
    t_type = st.selectbox("Type", ["IN", "OUT"])
    
    if st.button("Add Transaction"):
        res = cb.add_transaction(str(date), desc, amount, t_type)
        st.success(res)

elif menu == "ID Card Generator":
    st.subheader("Generate ID Card Data")
    name = st.text_input("Full Name")
    role = st.text_input("Role / Class")
    id_num = st.text_input("ID Number")
    photo = st.text_input("Photo Path / File Name")
    
    if st.button("Save ID Card"):
        res = id_gen.save_id_card_data(name, role, id_num, photo)
        st.success(res)

elif menu == "Reports":
    st.subheader("System Reports")
    if st.button("Generate Cash Book Report"):
        report_data = rep.generate_cash_book_report()
        st.text(report_data)
