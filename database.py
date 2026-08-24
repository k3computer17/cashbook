# database.py
import sqlite3

def init_db():
    conn = sqlite3.connect('software_data.db')
    cursor = conn.cursor()
    
    # 1. Users Table (Admin & User ID के लिए)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            active INTEGER NOT NULL
        )
    ''')
    
    # 2. CashBook Table (कैश बुक लेन-देन के लिए)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cashbook (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            description TEXT,
            amount REAL,
            type TEXT
        )
    ''')
    
    # 3. Ledger Table (खाता बही के लिए)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT,
            date TEXT,
            amount REAL
        )
    ''')
    
    # 4. ID Cards Table (आईडी कार्ड डेटा के लिए)
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

if __name__ == "__main__":
    init_db()
    print("Database and Tables created successfully!")
