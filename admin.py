# admin.py
import sqlite3

class Admin:
    def create_user(self, user_id, password, role="User"):
        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (user_id, password, role, active) VALUES (?, ?, ?, ?)", 
                           (user_id, password, role, 1))
            conn.commit()
            return f"User {user_id} created successfully."
        except sqlite3.IntegrityError:
            return "User already exists!"
        finally:
            conn.close()

    def block_user(self, user_id):
        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET active = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return f"User {user_id} blocked."
