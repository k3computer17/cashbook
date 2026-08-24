# database.py
import sqlite3

def init_db():
    conn = sqlite3.connect('software_data.db')
    cursor = conn.cursor()
    
    # अपडेटेड Users Table (सारी डिटेल्स के साथ)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            active INTEGER NOT NULL,
            name TEXT,
            father_name TEXT,
            aadhar_last4 TEXT,
            mobile TEXT,
            address TEXT,
            city TEXT,
            district TEXT,
            state TEXT,
            pin TEXT
        )
    ''')
    
    # बाकी टेबल्स वही रहेंगी...
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cashbook (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            description TEXT,
            amount REAL,
            type TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT,
            date TEXT,
            amount REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS id_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            role TEXT,
            id_number TEXT,
            photo_path TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
