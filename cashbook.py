# cashbook.py
import sqlite3

class CashBook:
    def add_transaction(self, date, description, amount, trans_type):
        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO cashbook (date, description, amount, type) VALUES (?, ?, ?, ?)",
                       (date, description, amount, trans_type))
        conn.commit()
        conn.close()
        return "Transaction added successfully."

    def get_all_transactions(self):
        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT date, description, amount, type FROM cashbook")
        rows = cursor.fetchall()
        conn.close()
        return rows