# main.py (Create User Section for Admin)
import streamlit as st
from admin import Admin

admin_obj = Admin()

# यह कोड एडमिन के 'Create New User' वाले मेनू में रहेगा:
st.subheader("➕ Create New User with Complete Details")

with st.form("user_create_form"):
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
        role = st.selectbox("Role", ["User", "Admin"])

    submit_button = st.form_submit_button(label="Generate ID & Save User")

    if submit_button:
        if name and mobile:
            success, u_id, pwd = admin_obj.create_user_with_details(
                name, father_name, aadhar_last4, mobile, address, city, district, state, pin, role
            )
            if success:
                st.success(f"User Created Successfully!")
                st.info(f"**Generated User ID:** `{u_id}`")
                st.warning(f"**One-Time Password:** `{pwd}` (Note this down for the user)")
            else:
                st.error(f"Error: {u_id}")
        else:
            st.error("Please fill at least Name and Mobile Number.")
