# idcard.py
import sqlite3

class IDCardGenerator:
    def save_id_card_data(self, name, role, id_number, photo_path):
        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO id_cards (name, role, id_number, photo_path) VALUES (?, ?, ?, ?)",
                       (name, role, id_number, photo_path))
        conn.commit()
        conn.close()
        return f"ID Card data saved for {name} in database."