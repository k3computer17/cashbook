# main.py (All-in-One Clean App without external admin.py dependency)
import streamlit as st
import sqlite3
import pandas as pd
import shutil
import os
from datetime import datetime
from database import init_db
from auth import UserAuth
from cashbook import CashBook
from ledger import Ledger
from dashboard import Dashboard
from reports import ReportGenerator
from idcard import IDCardGenerator

# --- डायरेक्ट एडमिन क्लास (ताकि कोई एरर न आए) ---
class AdminDirect:
    def create_user_with_details(self, name, father_name, aadhar_last4, mobile, email, address, city, district, state, pin, role="User"):
        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        import random
        rand_num = random.randint(1000, 9999)
        user_id = f"USR{mobile[-4:]}{rand_num}" if mobile else f"USR{rand_num}"
        one_time_password = f"OTP@{random.randint(1000, 9999)}"
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, password, role, active, name, father_name, aadhar_last4, mobile, email, address, city, district, state, pin)
                VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, one_time_password, role, name, father_name, aadhar_last4, mobile, email, address, city, district, state, pin))
            conn.commit()
            return True, user_id, one_time_password
        except Exception as e:
            return False, str(e), ""
        finally:
            conn.close()

    def get_all_users(self):
        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT user_id, role, name, father_name, mobile, email, city, state FROM users")
            rows = cursor.fetchall()
        except Exception as e:
            rows = []
        finally:
            conn.close()
        return rows

    def delete_user(self, user_id):
        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return f"User {user_id} deleted successfully."

# --- ऑटो-बैकअप सिस्टम ---
def take_database_backup():
    backup_dir = "database_backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    today_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = os.path.join(backup_dir, f"software_data_backup_{today_date}.db")
    if os.path.exists("software_data.db"):
        shutil.copy("software_data.db", backup_file)

take_database_backup()

# पेज की सेटिंग
st.set_page_config(page_title="CashBook & ID Card Manager", page_icon="💼", layout="wide")

# 1. डेटाबेस इनिशियलाइज करें
init_db()

# ऑब्जेक्ट्स बनाएं
admin_obj = AdminDirect()
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

# --- 1. लॉगिन स्क्रीन ---
if not st.session_state.logged_in:
    st.title("🔐 Software Login")
    
    try:
        admin_obj.create_user_with_details(
            name="System Admin", father_name="Admin", aadhar_last4="0000", 
            mobile="9999999999", email="admin@software.com", address="Office", 
            city="City", district="Dist", state="State", pin="000000", role="Admin"
        )
    except:
        pass

    with st.form("login_form"):
        u_id = st.text_input("User ID (Default: admin)")
        pwd = st.text_input("Password (Default: 1234 for main admin)", type="password")
        submit_login = st.form_submit_button("Login")

        if submit_login:
            if u_id == "admin" and pwd == "1234":
                st.session_state.logged_in = True
                st.session_state.user_id = "admin"
                st.session_state.role = "Admin"
                st.success("Welcome Admin!")
                st.rerun()
            else:
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
    st.sidebar.title("Navigation")
    st.sidebar.write(f"👤 Logged in: **{st.session_state.user_id}**")
    st.sidebar.write(f"🛡️ Role: **{st.session_state.role}**")
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.user_id = ""
        st.session_state.role = ""
        st.rerun()

    # ==========================================
    # A. एडमिन पैनल (Admin Options)
    # ==========================================
    if st.session_state.role.lower() == "admin":
        st.sidebar.markdown("---")
        admin_menu = st.sidebar.radio("Admin Options", ["👑 Dashboard", "➕ Create New User", "👥 Manage Users & Export", "📊 All Reports"])

        if admin_menu == "👑 Dashboard":
            st.title("Admin Dashboard")
            summary = dash_obj.get_summary()
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Income", f"₹ {summary['Total Income']}")
            col2.metric("Total Expense", f"₹ {summary['Total Expense']}")
            col3.metric("Current Balance", f"₹ {summary['Current Balance']}")

        elif admin_menu == "➕ Create New User":
            st.title("➕ Create New User (Admin Panel)")
            with st.form("new_user_form"):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("Full Name")
                    father_name = st.text_input("Father's Name")
                    aadhar_last4 = st.text_input("Aadhar Last 4 Digits", max_chars=4)
                    mobile = st.text_input("Mobile Number", max_chars=10)
                    email = st.text_input("Email ID")
                with col2:
                    address = st.text_input("Address")
                    city = st.text_input("City")
                    district = st.text_input("District")
                    state = st.text_input("State")
                    pin = st.text_input("PIN Code", max_chars=6)
                    role = st.selectbox("Assign Role", ["User", "Admin"])

                submit_user = st.form_submit_button("Generate ID & Save User")

                if submit_user:
                    if name and mobile:
                        success, u_id, pwd = admin_obj.create_user_with_details(
                            name, father_name, aadhar_last4, mobile, email, address, city, district, state, pin, role
                        )
                        if success:
                            st.success("User Created Successfully!")
                            st.info(f"**New User ID:** `{u_id}`")
                            st.warning(f"**One-Time Password:** `{pwd}` (इसे नोट करके सुरक्षित रख लें)")
                        else:
                            st.error(f"Error: {u_id}")
                    else:
                        st.error("Please fill at least Name and Mobile Number.")

        elif admin_menu == "👥 Manage Users & Export":
            st.title("👥 All Users Management & Excel Export")
            users_data = admin_obj.get_all_users()
            
            if users_data:
                df = pd.DataFrame(users_data, columns=["User ID", "Role", "Name", "Father Name", "Mobile", "Email", "City", "State"])
                st.dataframe(df)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Users List as Excel (CSV)",
                    data=csv,
                    file_name="users_list.csv",
                    mime="text/csv",
                )
                
                st.markdown("---")
                st.subheader("❌ Delete User")
                del_user_id = st.selectbox("Select User ID to Delete", df["User ID"].tolist())
                if st.button("Delete User"):
                    if del_user_id == "admin":
                        st.error("Main Admin cannot be deleted!")
                    else:
                        res = admin_obj.delete_user(del_user_id)
                        st.success(res)
                        st.rerun()
            else:
                st.info("No users found in the database.")

        elif admin_menu == "📊 All Reports":
            st.title("System Reports")
            if st.button("Generate Cash Book Report"):
                st.text(rep_obj.generate_cash_book_report())

    # ==========================================
    # B. सामान्य यूजर पैनल (User Menu)
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