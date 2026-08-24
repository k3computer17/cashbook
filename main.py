# main.py (Admin Section Addition)
import pandas as pd

# यह कोड एडमिन वाले हिस्से में 'Manage Users' मेनू के अंदर डालें:
elif admin_menu == "👥 Manage Users & Export":
    st.title("👥 All Users Management")
    
    users_data = admin_obj.get_all_users()
    
    if users_data:
        # डेटा को Pandas DataFrame में बदलना ताकि टेबल और एक्सेल डाउनलोड बन सके
        df = pd.DataFrame(users_data, columns=["User ID", "Role", "Name", "Father Name", "Mobile", "Email", "City", "State"])
        
        # स्क्रीन पर टेबल दिखाना
        st.dataframe(df)
        
        # 1. Excel / CSV Export बटन
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
