import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="BC CSP Cashbook",
    page_icon="💼",
    layout="wide"
)

# ----------------------------------------------------
# 1. Session State / Login Details (Demo Purpose)
# ----------------------------------------------------
if "user_role" not in st.session_state:
    st.session_state["user_role"] = "Admin"  # 'Admin' या 'User'
if "username" not in st.session_state:
    st.session_state["username"] = "admin"

# Header User Info
col_head1, col_head2 = st.columns([4, 1])
with col_head1:
    st.title(f"👤 Welcome, {st.session_state['username']}")
with col_head2:
    if st.button("🚪 Logout"):
        st.session_state.clear()
        st.rerun()

st.write("---")

# ----------------------------------------------------
# 2. Sidebar Navigation (Dynamic Menu)
# ----------------------------------------------------
st.sidebar.title("📌 Menu Navigation")

# सामान्य यूजर के लिए मेन्यू
menu_options = [
    "1. Customer Transactions",
    "2. Customer Ledger",
    "3. Opening Balances",
    "4. Accounting Forms",
    "5. User ID & KYC",
    "6. Cash & Banking",
    "7. Daily Working"
]

# अगर लॉगिन रोल 'Admin' है, तो Admin Panel का ऑप्शन जोड़ें
if st.session_state.get("user_role") == "Admin":
    menu_options.append("🛡️ Admin Panel (User Management)")

selected_module = st.sidebar.radio("Choose Module:", menu_options)

st.sidebar.write("---")

# ----------------------------------------------------
# 3. Admin Panel UI Function
# ----------------------------------------------------
def render_admin_panel():
    st.header("🛡️ System Admin Panel")
    st.subheader("👥 User Management & Approvals")

    # एग्जांपल डेटा / यूजर लिस्ट
    users = [
        {"username": "SUNI5327", "name": "Sunil", "kyc": "Pending", "active": True},
        {"username": "RAM1234", "name": "Ram Kumar", "kyc": "Approved", "active": True},
        {"username": "AMIT999", "name": "Amit Sharma", "kyc": "Rejected", "active": False},
    ]

    for u in users:
        with st.expander(f"👤 User: {u['name']} ({u['username']})"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.write(f"**KYC Status:** {u['kyc']}")
            with c2:
                new_kyc = st.selectbox(
                    "Update KYC", 
                    ["Pending", "Approved", "Rejected"], 
                    index=["Pending", "Approved", "Rejected"].index(u['kyc']),
                    key=f"kyc_{u['username']}"
                )
            with c3:
                is_active = st.checkbox("Active User", value=u['active'], key=f"act_{u['username']}")
            
            if st.button("💾 Update User", key=f"btn_{u['username']}"):
                st.success(f"User {u['username']} updated successfully!")

# ----------------------------------------------------
# 4. Module Routing Logic
# ----------------------------------------------------
if selected_module == "1. Customer Transactions":
    try:
        from custmartnx_module import render_custmartnx
        render_custmartnx()
    except ModuleNotFoundError:
        st.warning("⚠️ `custmartnx_module.py` file not found.")

elif selected_module == "2. Customer Ledger":
    try:
        from lagedr_module import render_lagedr
        render_lagedr()
    except ModuleNotFoundError:
        st.warning("⚠️ `lagedr_module.py` file not found.")

elif selected_module == "3. Opening Balances":
    try:
        from opeing_module import render_opeing
        render_opeing()
    except ModuleNotFoundError:
        st.warning("⚠️ `opeing_module.py` file not found.")

elif selected_module == "4. Accounting Forms":
    try:
        from Accountingform_module import render_accountingform
        render_accountingform()
    except ModuleNotFoundError:
        st.warning("⚠️ `Accountingform_module.py` file not found.")

elif selected_module == "5. User ID & KYC":
    try:
        from UserIDkyc_module import render_useridkyc
        render_useridkyc()
    except ModuleNotFoundError:
        st.warning("⚠️ `UserIDkyc_module.py` file not found.")

elif selected_module == "6. Cash & Banking":
    try:
        from cashandbanking_module import render_cashandbanking
        render_cashandbanking()
    except ModuleNotFoundError:
        st.warning("⚠️ `cashandbanking_module.py` file not found.")

elif selected_module == "7. Daily Working":
    try:
        from dalyworking_module import render_dalyworking
        render_dalyworking()
    except ModuleNotFoundError:
        st.warning("⚠️ `dalyworking_module.py` file not found.")

elif selected_module == "🛡️ Admin Panel (User Management)":
    render_admin_panel()
