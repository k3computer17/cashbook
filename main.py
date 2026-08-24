# main.py
from database import init_db
from admin import Admin
from auth import UserAuth
from cashbook import CashBook
from ledger import Ledger
from dashboard import Dashboard
from reports import ReportGenerator
from idcard import IDCardGenerator

if __name__ == "__main__":
    # 1. सबसे पहले डेटाबेस और टेबल तैयार करें
    init_db()

    # 2. एडमिन और यूज़र टेस्ट
    admin = Admin()
    print(admin.create_user("admin01", "1234", "Admin"))

    auth = UserAuth()
    print(auth.login("admin01", "1234"))

    # 3. कैश बुक टेस्ट
    cb = CashBook()
    print(cb.add_transaction("2026-06-07", "Client Advance", 10000, "IN"))
    print(cb.add_transaction("2026-06-07", "Software License", 3000, "OUT"))

    # 4. लेजर टेस्ट
    ledger = Ledger()
    print(ledger.add_entry("Sharma Ji", "2026-06-07", 5000))

    # 5. डैशबोर्ड समरी
    dash = Dashboard()
    print("Dashboard Summary:", dash.get_summary())

    # 6. रिपोर्ट्स टेस्ट
    rep = ReportGenerator()
    print("Cash Book Report:\n", rep.generate_cash_book_report())

    # 7. आईडी कार्ड टेस्ट
    id_gen = IDCardGenerator()
    print(id_gen.save_id_card_data("Rahul Kumar", "Student", "ID1001", "photo.jpg"))
