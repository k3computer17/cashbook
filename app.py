import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="BC CSP Cashbook System",
    page_icon="💼",
    layout="wide"
)

# ----------------------------------------------------
# 1. Session State Initialization (Demo Data)
# ----------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_role" not in st.session_state:
    st.session_state["user_role"] = None
if "username" not in st.session_state:
    st.session_state["username"] = ""

# Sample Users Database Store (Session Based)
if "users_db" not in st.session_state:
    st.session_state["users_db"] = {
        "SUNI5327": {
            "password": "1234",
            "name": "Sunil Kumar",
            "phone": "9876543210",
            "plan_type": "Paid",  # 'Demo' या 'Paid'
            "status": "Active",   # 'Active' या 'Inactive'
            "expiry_date": "2026-12-31"
        }
    }

# ----------------------------------------------------
# 2. Login Page Function
# ----------------------------------------------------
def render_login_page():
    st.title("🔐 BC CSP Cashbook Login")
    
    tab_user, tab_admin = st.tabs(["👤 User Login", "🛡️ Admin Login"])

    # --- USER LOGIN ---
    with tab_user:
        u_id = st.text_input("User ID", key="usr_id_in")
        u_pass = st.text_input("Password", type="password", key="usr_pass_in")
        
        if st.button("Login as User", type="primary"):
            users = st.session_state["users_db"]
            if u_id in users and users[u_id]["password"] == u_pass:
                if users[u_id]["status"] == "Active":
                    st.session_state["logged_in"] = True
                    st.session_state["user_role"] = "User"
                    st.session_state["username"] = u_id
                    st.success(f"Welcome {users[u_id]['name']}!")
                    st.rerun()
                else:
                    st.error("आपका अकाउंट इनएक्टिव है। कृपया एडमिन से संपर्क करें।")
            else:
                st.error("गलत User ID या Password!")

    # --- ADMIN LOGIN ---
    with tab_admin:
        a_id = st.text_input("Admin ID", key="adm_id_in")
        a_pass = st.text_input("Admin Password", type="password", key="adm_pass_in")
        
        if st.button("Login as Admin", type="primary"):
            if a_id == "admin" and a_pass == "admin123":
                st.session_state["logged_in"] = True
                st.session_state["user_role"] = "Admin"
                st.session_state["username"] = "admin"
                st.success("Admin Login Successful!")
                st.rerun()
            else:
                st.error("गलत Admin Credentials!")

# ----------------------------------------------------
# 3. Admin Panel (User Creation, Edit, Delete, View)
# ----------------------------------------------------
def render_admin_panel():
    st.header("🛡️ Admin Dashboard - User Management")
    
    # ➕ 1. Create New User
    with st.expander("➕ Create New User ID", expanded=False):
        with st.form("create_user_form"):
            c1, c2 = st.columns(2)
            with c1:
                new_uid = st.text_input("Assign User ID (e.g. USER101)")
                new_pass = st.text_input("Password")
                new_name = st.text_input("Full Name")
            with c2:
                new_phone = st.text_input("Mobile No.")
                plan_type = st.selectbox("Plan Type", ["Demo", "Paid"])
                expiry = st.date_input("Validity / Expiry Date")
            
            submit_create = st.form_submit_button("✅ Create User")
            if submit_create:
                if new_uid and new_pass:
                    st.session_state["users_db"][new_uid] = {
                        "password": new_pass,
                        "name": new_name,
                        "phone": new_phone,
                        "plan_type": plan_type,
                        "status": "Active",
                        "expiry_date": str(expiry)
                    }
                    st.success(f"User '{new_uid}' Created Successfully!")
                    st.rerun()
                else:
                    st.error("User ID और Password अनिवार्य हैं!")

    st.write("---")
    st.subheader("📋 All Users List & Controls")

    # 📋 2. View, Edit, and Delete Users
    users = st.session_state["users_db"]
    
    for uid, uinfo in list(users.items()):
        with st.expander(f"👤 {uinfo['name']} ({uid}) - [{uinfo['plan_type']}] - Status: {uinfo['status']}"):
            ec1, ec2, ec3 = st.columns(3)
            
            with ec1:
                e_name = st.text_input("Name", value=uinfo["name"], key=f"name_{uid}")
                e_phone = st.text_input("Phone", value=uinfo["phone"], key=f"phone_{uid}")
            with ec2:
                e_pass = st.text_input("Password", value=uinfo["password"], key=f"pass_{uid}")
                e_plan = st.selectbox("Plan Type", ["Demo", "Paid"], index=0 if uinfo["plan_type"] == "Demo" else 1, key=f"plan_{uid}")
            with ec3:
                e_status = st.selectbox("Account Status", ["Active", "Inactive"], index=0 if uinfo["status"] == "Active" else 1, key=f"status_{uid}")
            
            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                if st.button("💾 Save Changes", key=f"save_{uid}"):
                    st.session_state["users_db"][uid].update({
                        "name": e_name,
                        "phone": e_phone,
                        "password": e_pass,
                        "plan_type": e_plan,
                        "status": e_status
                    })
                    st.success("User updated!")
                    st.rerun()
            
            with col_btn2:
                if st.button("🗑️ Delete User", key=f"del_{uid}", type="secondary"):
                    del st.session_state["users_db"][uid]
                    st.warning("User deleted!")
                    st.rerun()

# ----------------------------------------------------
# 4. Main Application Routing
# ----------------------------------------------------
if not st.session_state["logged_in"]:
    render_login_page()
else:
    # Header Section
    col_h1, col_h2 = st.columns([4, 1])
    with col_h1:
        st.title(f"BC CSP Cashbook - ({st.session_state['user_role']})")
    with col_h2:
        if st.button("🚪 Logout"):
            st.session_state.clear()
            st.rerun()

    st.write("---")

    # ADMIN view
    if st.session_state["user_role"] == "Admin":
        render_admin_panel()

    # USER view (Show 7 Modules)
    else:
        st.sidebar.title("📌 User Modules")
        user_module = st.sidebar.radio(
            "Go to Module:",
            [
                "1. Customer Transactions",
                "2. Customer Ledger",
                "3. Opening Balances",
                "4. Accounting Forms",
                "5. User ID & KYC",
                "6. Cash & Banking",
                "7. Daily Working"
            ]
        )

        if user_module == "1. Customer Transactions":
            try:
                from custmartnx_module import render_custmartnx
                render_custmartnx()
            except ModuleNotFoundError:
                st.warning("⚠️ `custmartnx_module.py` file not found.")

        elif user_module == "2. Customer Ledger":
            try:
                from lagedr_module import render_lagedr
                render_lagedr()
            except ModuleNotFoundError:
                st.warning("⚠️ `lagedr_module.py` file not found.")

        elif user_module == "3. Opening Balances":
            try:
                from opeing_module import render_opeing
                render_opeing()
            except ModuleNotFoundError:
                st.warning("⚠️ `opeing_module.py` file not found.")

        elif user_module == "4. Accounting Forms":
            try:
                from Accountingform_module import render_accountingform
                render_accountingform()
            except ModuleNotFoundError:
                st.warning("⚠️ `Accountingform_module.py` file not found.")

        elif user_module == "5. User ID & KYC":
            try:
                from UserIDkyc_module import render_useridkyc
                render_useridkyc()
            except ModuleNotFoundError:
                st.warning("⚠️ `UserIDkyc_module.py` file not found.")

        elif user_module == "6. Cash & Banking":
            try:
                from cashandbanking_module import render_cashandbanking
                render_cashandbanking()
            except ModuleNotFoundError:
                st.warning("⚠️ `cashandbanking_module.py` file not found.")

        elif user_module == "7. Daily Working":
            try:
                from dalyworking_module import render_dalyworking
                render_dalyworking()
            except ModuleNotFoundError:
                st.warning("⚠️ `dalyworking_module.py` file not found.")
