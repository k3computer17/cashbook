# ledger.py
import sqlite3

class Ledger:
    def add_entry(self, account_name, date, amount):
        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ledger (account_name, date, amount) VALUES (?, ?, ?)",
                       (account_name, date, amount))
        conn.commit()
        conn.close()
        return f"Ledger entry updated for {account_name}."

    def get_account_entries(self, account_name):
        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT date, amount FROM ledger WHERE account_name = ?", (account_name,))
        rows = cursor.fetchall()
        conn.close()
        return rows