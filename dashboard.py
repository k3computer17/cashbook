# dashboard.py
import sqlite3

class Dashboard:
    def get_summary(self):
        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT SUM(amount) FROM cashbook WHERE type = 'IN'")
        total_income = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT SUM(amount) FROM cashbook WHERE type = 'OUT'")
        total_expense = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT COUNT(DISTINCT account_name) FROM ledger")
        total_accounts = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "Total Income": total_income,
            "Total Expense": total_expense,
            "Current Balance": total_income - total_expense,
            "Total Ledger Accounts": total_accounts
        }