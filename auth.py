# auth.py
import sqlite3

class UserAuth:
    def login(self, user_id, password):
        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT password, active FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            db_password, active = result
            if active == 1 and db_password == password:
                return f"Login successful! Welcome {user_id}."
            return "Account blocked or incorrect password."
        return "User ID not found."
