# admin.py
import sqlite3
import random

class Admin:
    def create_user_with_details(self, name, father_name, aadhar_last4, mobile, address, city, district, state, pin, role="User"):
        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        
        # ऑटोमैटिक यूजर आईडी जनरेट करना (जैसे: USER1049 या मोबाइल के आखिरी 4 अंक मिलाकर)
        rand_num = random.randint(1000, 9999)
        user_id = f"USR{mobile[-4:]}{rand_num}" if mobile else f"USR{rand_num}"
        
        # वन-टाइम पासवर्ड जनरेट करना (जैसे: OTP@8421)
        one_time_password = f"OTP@{random.randint(1000, 9999)}"
        
        try:
            cursor.execute('''
                INSERT INTO users (user_id, password, role, active, name, father_name, aadhar_last4, mobile, address, city, district, state, pin)
                VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, one_time_password, role, name, father_name, aadhar_last4, mobile, address, city, district, state, pin))
            
            conn.commit()
            return True, user_id, one_time_password
        except Exception as e:
            return False, str(e), ""
        finally:
            conn.close()
