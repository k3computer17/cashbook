import streamlit as st
import random
import string

# Page Config
st.set_page_config(page_title="BC CSP Cashbook", page_icon="💼", layout="wide")

# Helper: Auto Generate User ID & Password
def generate_user_id(name):
    clean_name = "".join(e for e in name if e.isalnum()).upper()[:4]
    random_num = random.randint(1000, 9999)
    return f"{clean_name}{random_num}"

def generate_random_password():
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(8))

# Session State Initial Data
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_role" not in st.session_state:
    st.session_state["user_role"] = None
if "username" not in st.session_state:
    st.session_state["username"] = ""

if "users_db" not in st.session_state:
    # Initial Demo User
    st.session_state["users_db"] = {
        "SUNI5327": {
            "password": "1234",
            "first_login": True,
            "name": "Sunil Kumar",
            "father_name": "Ramesh Kumar",
            "city": "Jaipur",
            "pin": "302001",
            "dob": "1995-05-15",
            "pan": "ABCDE1234F",
            "mobile": "9876543210",
            "plan_type": "Paid",
            "status": "Active"
        }
    }

# ----------------------------------------------------
# 1. LOGIN & RECOVERY PAGES
# ----------------------------------------------------
def render_login_page():
    st.title("🔐 BC CSP Cashbook Portal")
    
    tab_user, tab_forgot_pwd, tab_forgot_uid, tab_admin = st.tabs([
        "👤 User Login", 
        "🔑 Forgot Password", 
        "🆔 Forgot User ID", 
        "🛡️ Admin Login"
    ])

    # --- USER LOGIN ---
    with tab_user:
        u_id = st.text_input("User ID", key="l_uid").strip().upper()
        u_pass = st.text_input("Password", type="password", key="l_upass")
        
        if st.button("Login as User", type="primary"):
            users = st.session_state["users_db"]
            if u_id in users and users[u_id]["password"] == u_pass:
                if users[u_id]["status"] == "Active":
                    st.session_state["logged_in"] = True
                    st.session_state["user_role"] = "User"
                    st.session_state["username"] = u_id
                    st.rerun()
                else:
                    st.error("आपका अकाउंट Active नहीं है। एडमिन से संपर्क करें।")
            else:
                st.error("गलत User ID या Password!")

    # --- FORGOT PASSWORD ---
    with tab_forgot_pwd:
        st.subheader("🔑 Reset Password")
        fp_uid = st.text_input("Enter User ID", key="fp_uid").strip().upper()
        fp_dob = st.date_input("Date of Birth", key="fp_dob")
        fp_pan = st.text_input("PAN Card Number", key="fp_pan").strip().upper()
        fp_new_pass = st.text_input("New Password", type="password", key="fp_npass")
        
        if st.button("Reset Password"):
            users = st.session_state["users_db"]
            if fp_uid in users:
                u = users[fp_uid]
                if u["dob"] == str(fp_dob) and u["pan"] == fp_pan:
                    users[fp_uid]["password"] = fp_new_pass
                    users[fp_uid]["first_login"] = False
                    st.success("पासवर्ड सफलतापूर्वक बदल दिया गया है! अब लॉगिन करें।")
                else:
                    st.error("DOB या PAN विवरण मेल नहीं खा रहा है!")
            else:
                st.error("User ID नहीं मिली!")

    # --- FORGOT USER ID ---
    with tab_forgot_uid:
        st.subheader("🆔 Recover User ID")
        fi_mobile = st.text_input("Registered Mobile No.", key="fi_mob").strip()
        fi_dob = st.date_input("Date of Birth", key="fi_dob")
        fi_pan = st.text_input("PAN Card Number", key="fi_pan").strip().upper()
        
        if st.button("Find My User ID"):
            found = False
            for uid, u in st.session_state["users_db"].items():
                if u["mobile"] == fi_mobile and u["dob"] == str(fi_dob) and u["pan"] == fi_pan:
                    st.success(f"आपकी User ID है: **{uid}**")
                    found = True
                    break
            if not found:
                st.error("दिए गए विवरण के अनुसार कोई यूजर ID नहीं मिली!")

    # --- ADMIN LOGIN ---
    with tab_admin:
        a_id = st.text_input("Admin ID", key="l_aid")
        a_pass = st.text_input("Admin Password", type="password", key="l_apass")
        
        if st.button("Login as Admin", type="primary"):
            if a_id == "admin" and a_pass == "admin123":
                st.session_state["logged_in"] = True
                st.session_state["user_role"] = "Admin"
                st.session_state["username"] = "admin"
                st.rerun()
            else:
                st.error("गलत Admin Credentials!")

# ----------------------------------------------------
# 2. FIRST TIME PASSWORD CHANGE
# ----------------------------------------------------
def render_first_time_password_change(uid):
    st.warning("⚠️ **पहली बार लॉगिन:** सुरक्षा कारणों से कृपया अपना नया पासवर्ड बनाएं।")
    n_pass1 = st.text_input("New Password", type="password", key="ftp1")
    n_pass2 = st.text_input("Confirm New Password", type="password", key="ftp2")
    
    if st.button("Save New Password & Continue"):
        if n_pass1 and n_pass1 == n_pass2:
            st.session_state["users_db"][uid]["password"] = n_pass1
            st.session_state["users_db"][uid]["first_login"] = False
            st.success("पासवर्ड सफलतापूर्वक अपडेट हो गया!")
            st.rerun()
        else:
            st.error("दोनों पासवर्ड एक समान होने चाहिए!")

# ----------------------------------------------------
# 3. ADMIN PANEL
# ----------------------------------------------------
def render_admin_panel():
    st.header("🛡️ Admin Panel - User Management")
    
    # Create User Form
    with st.expander("➕ Create New User ID", expanded=False):
        with st.form("add_user_form"):
            c1, c2 = st.columns(2)
            with c1:
                u_name = st.text_input("Full Name *")
                u_fname = st.text_input("Father's Name *")
                u_city = st.text_input("City *")
                u_pin = st.text_input("PIN Code *")
            with c2:
                u_dob = st.date_input("Date of Birth *")
                u_pan = st.text_input("PAN Card Number *").upper()
                u_mob = st.text_input("Mobile Number *")
                u_plan = st.selectbox("Plan Type", ["Demo", "Paid"])

            submit_btn = st.form_submit_button("⚡ Auto-Generate User ID & Password")

            if submit_btn:
                if u_name and u_pan and u_mob:
                    auto_uid = generate_user_id(u_name)
                    auto_pass = generate_random_password()
                    
                    st.session_state["users_db"][auto_uid] = {
                        "password": auto_pass,
                        "first_login": True,
                        "name": u_name,
                        "father_name": u_fname,
                        "city": u_city,
                        "pin": u_pin,
                        "dob": str(u_dob),
                        "pan": u_pan,
                        "mobile": u_mob,
                        "plan_type": u_plan,
                        "status": "Active"
                    }
                    st.success(f"✅ User ID Generated Successfully!")
                    st.info(f"**Generated User ID:** {auto_uid}\n\n**Temporary Password:** {auto_pass}")
                else:
                    st.error("कृपया सभी आवश्यक फ़ील्ड्स भरें!")

    st.write("---")
    st.subheader("📋 Registered Users List")

    # List & Edit Users
    for uid, uinfo in list(st.session_state["users_db"].items()):
        with st.expander(f"👤 {uinfo['name']} ({uid}) | Mobile: {uinfo['mobile']} | Plan: {uinfo['plan_type']}"):
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                st.write(f"**Father Name:** {uinfo['father_name']}")
                st.write(f"**City / PIN:** {uinfo['city']} - {uinfo['pin']}")
                st.write(f"**DOB:** {uinfo['dob']}")
            with ec2:
                st.write(f"**PAN:** {uinfo['pan']}")
                e_plan = st.selectbox("Plan", ["Demo", "Paid"], index=0 if uinfo["plan_type"] == "Demo" else 1, key=f"p_{uid}")
                e_status = st.selectbox("Status", ["Active", "Inactive"], index=0 if uinfo["status"] == "Active" else 1, key=f"s_{uid}")
            with ec3:
                e_pass = st.text_input("Reset Password", value=uinfo["password"], key=f"pw_{uid}")
                
            b1, b2 = st.columns(2)
            with b1:
                if st.button("💾 Update", key=f"up_{uid}"):
                    st.session_state["users_db"][uid]["plan_type"] = e_plan
                    st.session_state["users_db"][uid]["status"] = e_status
                    st.session_state["users_db"][uid]["password"] = e_pass
                    st.success("Updated!")
                    st.rerun()
            with b2:
                if st.button("🗑️ Delete", key=f"del_{uid}"):
                    del st.session_state["users_db"][uid]
                    st.warning("Deleted!")
                    st.rerun()

# ----------------------------------------------------
# 4. MAIN ROUTING LOGIC
# ----------------------------------------------------
if not st.session_state["logged_in"]:
    render_login_page()
else:
    uid = st.session_state["username"]
    role = st.session_state["user_role"]
    
    # Header
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title(f"BC CSP Cashbook ({role})")
    with col2:
        if st.button("🚪 Logout"):
            st.session_state.clear()
            st.rerun()

    st.write("---")

    # Flow Control
    if role == "Admin":
        render_admin_panel()
    else:
        # Check First Time Login
        if st.session_state["users_db"][uid].get("first_login", False):
            render_first_time_password_change(uid)
        else:
            # Show 7 Modules for User
            st.sidebar.title("📌 Navigation")
            module = st.sidebar.radio("Modules", [
                "1. Customer Transactions",
                "2. Customer Ledger",
                "3. Opening Balances",
                "4. Accounting Forms",
                "5. User ID & KYC",
                "6. Cash & Banking",
                "7. Daily Working"
            ])

            if module == "1. Customer Transactions":
                try:
                    from custmartnx_module import render_custmartnx
                    render_custmartnx()
                except ModuleNotFoundError:
                    st.warning("`custmartnx_module.py` not found.")
            # इसी तरह बाकी 6 मॉड्युल्स कॉल होंगे...
