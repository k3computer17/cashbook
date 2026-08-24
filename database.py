# database.py (Updated with Force Table Reset for Migration)
import sqlite3

def init_db():
    conn = sqlite3.connect('software_data.db')
    cursor = conn.cursor()
    
    # पुरानी users टेबल को पूरी तरह हटाकर नए कॉलम्स के साथ दोबारा बनाना ताकि एरर कभी न आए
    cursor.execute("DROP TABLE IF EXISTS users")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            password TEXT,
            role TEXT,
            active INTEGER DEFAULT 1,
            name TEXT,
            father_name TEXT,
            aadhar_last4 TEXT,
            mobile TEXT,
            email TEXT,
            address TEXT,
            city TEXT,
            district TEXT,
            state TEXT,
            pin TEXT
        )
    ''')

    # Cashbook टेबल
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cashbook (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            description TEXT,
            amount REAL,
            type TEXT
        )
    ''')

    # Ledger टेबल
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT,
            date TEXT,
            amount REAL
        )
    ''')

    # ID Card टेबल
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS idcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            role TEXT,
            id_num TEXT,
            photo TEXT
        )
    ''')

    conn.commit()
    conn.close()