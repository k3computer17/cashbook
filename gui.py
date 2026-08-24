# gui.py
import tkinter as tk
from tkinter import messagebox
import sqlite3

class SoftwareApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CashBook & ID Card Manager")
        self.root.geometry("400x350")
        
        # लॉगिन विंडो बनाना
        self.create_login_screen()

    def create_login_screen(self):
        # पुराना सब साफ करें
        for widget in self.root.winfo_children():
            widget.destroy()

        tk.Label(self.root, text="Software Login", font=("Arial", 16, "bold")).pack(pady=20)

        tk.Label(self.root, text="User ID:").pack(anchor="w", padx=50)
        self.user_entry = tk.Entry(self.root, width=30)
        self.user_entry.pack(pady=5, padx=50)

        tk.Label(self.root, text="Password:").pack(anchor="w", padx=50)
        self.pass_entry = tk.Entry(self.root, show="*", width=30)
        self.pass_entry.pack(pady=5, padx=50)

        tk.Button(self.root, text="Login", bg="green", fg="white", width=15, command=self.verify_login).pack(pady=20)

    def verify_login(self):
        u_id = self.user_entry.get()
        pwd = self.pass_entry.get()

        conn = sqlite3.connect('software_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT password, active FROM users WHERE user_id = ?", (u_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            db_pwd, active = result
            if active == 1 and db_pwd == pwd:
                messagebox.showinfo("Success", f"Welcome {u_id}!")
                self.open_dashboard(u_id)
            else:
                messagebox.showerror("Error", "Account blocked or incorrect password!")
        else:
            messagebox.showerror("Error", "User ID not found!")

    def open_dashboard(self, user_id):
        # डैशबोर्ड विंडो
        for widget in self.root.winfo_children():
            widget.destroy()

        tk.Label(self.root, text=f"Dashboard - Welcome, {user_id}", font=("Arial", 14, "bold")).pack(pady=20)
        
        tk.Button(self.root, text="1. Cash Book Entry", width=25, command=lambda: messagebox.showinfo("Info", "Cash Book module clicked")).pack(pady=5)
        tk.Button(self.root, text="2. ID Card Generator", width=25, command=lambda: messagebox.showinfo("Info", "ID Card module clicked")).pack(pady=5)
        tk.Button(self.root, text="3. Ledger & Reports", width=25, command=lambda: messagebox.showinfo("Info", "Reports module clicked")).pack(pady=5)
        
        tk.Button(self.root, text="Logout", bg="red", fg="white", width=15, command=self.create_login_screen).pack(pady=20)

if __name__ == "__main__":
    root = tk.Tk()
    app = SoftwareApp(root)
    root.mainloop()