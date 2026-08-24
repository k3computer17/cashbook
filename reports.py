# reports.py
import json
from cashbook import CashBook
from ledger import Ledger

class ReportGenerator:
    def __init__(self):
        self.cb = CashBook()
        self.ledger = Ledger()

    def generate_cash_book_report(self):
        transactions = self.cb.get_all_transactions()
        return json.dumps(transactions, indent=4)

    def generate_ledger_report(self, account_name):
        entries = self.ledger.get_account_entries(account_name)
        return json.dumps(entries, indent=4)