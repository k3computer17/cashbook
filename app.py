import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
import json

# Page Config
st.set_page_config(page_title="BC Point Management System", layout="wide")

# Persistent State Initialization
if 'transactions' not in st.session_state:
    st.session_state.transactions = []
if 'ledgers' not in st.session_state:
    st.session_state.ledgers = []
if 'vouchers' not in st.session_state:
    st.session_state.vouchers = []
if 'opening_cash' not in st.session_state:
    st.session_state.opening_cash = 0.0
if 'opening_bank' not in st.session_state:
    st.session_state.opening_bank = 0.0

BASE_ACC_NO = 117100171

# Helper Functions
def get_next_acc_no():
    max_no = BASE_ACC_NO
    for l in st.session_state.ledgers:
        try:
            num = int(l['accNo'])
            if num >= max_no:
                max_no = num + 1
        except ValueError:
            pass
    return str(max_no)

def auto_sync_customer_ledger(acc_no, name, current_opening):
    target = None
    for l in st.session_state.ledgers:
        if (acc_no and acc_no != 'N/A' and str(l['accNo']) == str(acc_no)) or l['name'].lower() == name.lower():
            target = l
            break
    
    if target:
        if not target.get('openingBal') and current_opening:
            target['openingBal'] = current_opening
        return target['accNo']
    else:
        new_acc_no = get_next_acc_no()
        new_ledger = {
            'accNo': new_acc_no,
            'name': name,
            'type': 'Customer',
            'openingBal': current_opening or 0.0,
            'openingType': 'Cr'
        }
        st.session_state.ledgers.append(new_ledger)
        return new_acc_no

def extract_pdf_data(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + " "
    return parse_text(text)

def parse_text(text):
    data = {}
    is_withdrawal = bool(re.search(r'Withdrawal|Nikasi|Cash Out', text, re.I))
    is_deposit = bool(re.search(r'Deposit|Jama|Cash In', text, re.I))
    is_transfer = bool(re.search(r'Transfer|Fund Transfer|Remittance', text, re.I))

    if is_withdrawal:
        data['txnType'] = 'Withdrawal'
    elif is_deposit:
        data['txnType'] = 'Deposit'
    elif is_transfer:
        data['txnType'] = 'Fund Transfer'
    else:
        data['txnType'] = 'Withdrawal'

    name_m = re.search(r'(?:Customer Name\/.*?:\s*|Name\s*:\s*)([A-Za-z\s]+)', text, re.I)
    data['name'] = name_m.group(1).strip() if name_m else ""

    ref_m = re.search(r'(?:Ref\/.*?:\s*|XXXXXXXX)(\d{4})', text, re.I)
    data['aadhaar'] = ref_m.group(1) if ref_m else "----"

    rrn_m = re.search(r'(?:RRN\/.*?:\s*|Journal Number is\s*)(\d+)', text, re.I)
    data['rrn'] = rrn_m.group(1) if rrn_m else ""

    amt_m = re.search(r'(?:Transaction Amount\/.*?:\s*|Total Amount\/.*?:\s*)([\d.]+)', text, re.I)
    data['amount'] = float(amt_m.group(1)) if amt_m else 0.0

    return data

# Live Dashboard Balances Engine
today_in = 0.0
today_out = 0.0
commission_total = 0.0
bank_add = 0.0
bank_deduct = 0.0

for t in st.session_state.transactions:
    actual_cash = t.get('cashPaid', t['amount'])
    if t['type'] == 'Deposit':
        today_in += actual_cash
        bank_deduct += t['amount']
    elif t['type'] in ['Withdrawal', 'Fund Transfer']:
        today_out += actual_cash
        bank_add += t['amount']
    commission_total += t.get('commission', 0.0)

for v in st.session_state.vouchers:
    if v['crDr'] == 'Cr':
        today_in += v['amount']
    elif v['crDr'] == 'Dr':
        today_out += v['amount']

expected_cash = st.session_state.opening_cash + today_in - today_out + commission_total
expected_bank = st.session_state.opening_bank + bank_add - bank_deduct
total_net_balance = expected_cash + expected_bank

# UI Title
st.title("🏦 BC Point Management & Accounting System")

# Master Balance Header Bar
col1, col2, col3, col4 = st.columns(4)
col1.metric("Opening Cash", f"₹{st.session_state.opening_cash:,.2f}")
col2.metric("Live Counter Cash", f"₹{expected_cash:,.2f}")
col3.metric("Bank / Settlement Balance", f"₹{expected_bank:,.2f}")
col4.metric("Total Net Balance", f"₹{total_net_balance:,.2f}")

st.markdown("---")

# Main Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📄 Board 1: Customer Entry & Receipts", 
    "💵 Board 2: Day Closing & Cash Balancing", 
    "📖 Board 3: Ledger Accounts", 
    "📝 Board 4: Accounting Vouchers"
])

# BOARD 1: CUSTOMER RECEIPTS & ENTRY
with tab1:
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("📄 Customer Transaction Importer & Entry")
        
        # PDF / Text Import
        uploaded_pdf = st.file_uploader("Import Receipt PDF", type=["pdf"])
        pasted_text = st.text_area("Paste Receipt Text Directly")
        
        auto_data = {}
        if uploaded_pdf:
            auto_data = extract_pdf_data(uploaded_pdf)
        elif pasted_text:
            auto_data = parse_text(pasted_text)

        dt_val = st.date_input("Date", datetime.now())
        tm_val = st.time_input("Time", datetime.now().time())
        
        # Ledger Dropdown Selection
        ledger_opts = {"": "-- Direct Customer Entry --"}
        for l in st.session_state.ledgers:
            ledger_opts[l['accNo']] = f"{l['name']} (Acc: {l['accNo']})"
        
        selected_ledger_acc = st.selectbox("Select Existing Ledger (Optional)", list(ledger_opts.keys()), format_func=lambda x: ledger_opts[x])
        
        default_name = auto_data.get('name', '')
        default_opening = 0.0
        if selected_ledger_acc:
            for l in st.session_state.ledgers:
                if str(l['accNo']) == str(selected_ledger_acc):
                    default_name = l['name']
                    default_opening = float(l.get('openingBal', 0.0))
                    break

        cust_name = st.text_input("Customer Name", value=default_name)
        aadhaar = st.text_input("Ref Last 4 Digits", value=auto_data.get('aadhaar', '----'), max_chars=4)
        rrn = st.text_input("RRN / Journal Ref No.", value=auto_data.get('rrn', ''))
        
        txn_type_idx = 0
        if auto_data.get('txnType') == 'Deposit':
            txn_type_idx = 1
        elif auto_data.get('txnType') == 'Fund Transfer':
            txn_type_idx = 2

        txn_type = st.selectbox("Transaction Type", ["Withdrawal", "Deposit", "Fund Transfer"], index=txn_type_idx)
        opening_bal = st.number_input("Customer Opening Balance ₹", value=default_opening)
        txn_amt = st.number_input("Txn Amount ₹", value=float(auto_data.get('amount', 0.0)))
        actual_cash = st.number_input("Actual Cash Handed Over / Received ₹", value=txn_amt)
        commission = st.number_input("Commission / Fee ₹", value=0.0)

        if st.button("💾 Save Entry", type="primary"):
            if not cust_name or txn_amt <= 0:
                st.error("⚠️ Customer Name aur Valid Amount enter karein!")
            else:
                final_acc_no = auto_sync_customer_ledger(selected_ledger_acc, cust_name, opening_bal)
                dt_str = f"{dt_val} {tm_val.strftime('%H:%M:%S')}"
                entry = {
                    "dateTime": dt_str,
                    "dateISO": str(dt_val),
                    "accNo": final_acc_no,
                    "name": cust_name,
                    "aadhaar": aadhaar,
                    "rrn": rrn,
                    "type": txn_type,
                    "custOpeningBalance": opening_bal,
                    "amount": txn_amt,
                    "cashPaid": actual_cash,
                    "commission": commission
                }
                st.session_state.transactions.append(entry)
                st.success(f"✅ Transaction successfully saved for Acc No: {final_acc_no}!")
                st.rerun()

    with c2:
        st.subheader("🔍 Search Customer Ledger")
        search_query = st.text_input("Enter Account No, Customer Name, or RRN")
        
        if search_query:
            q = search_query.lower()
            results = [
                t for t in st.session_state.transactions 
                if q in str(t.get('accNo', '')).lower() or q in t['name'].lower() or q in t.get('rrn', '').lower()
            ]
            if results:
                st.write(f"### 📋 Transactions for '{search_query}'")
                df_res = pd.DataFrame(results)
                st.dataframe(df_res[['dateTime', 'accNo', 'name', 'type', 'amount', 'cashPaid']], use_container_width=True)
            else:
                st.warning("Koi matching record nahi mila.")

# BOARD 2: DAY CLOSING & CASH BALANCING
with tab2:
    st.subheader("📊 Cash Counter, Bank & Day Closing Assistant")
    c1, c2 = st.columns(2)
    
    with c1:
        st.session_state.opening_cash = st.number_input("Morning Opening Counter Cash (Gulla) ₹", value=st.session_state.opening_cash)
        st.session_state.opening_bank = st.number_input("Opening Bank / Portal Balance ₹", value=st.session_state.opening_bank)
        actual_counter = st.number_input("Evening Actual Physical Counter Cash ₹", value=0.0)
        
        if st.button("📋 Generate Final Closing Summary"):
            diff = actual_counter - expected_cash
            st.markdown("---")
            st.write("### 📝 Day Closing Summary")
            st.write(f"- Opening Counter Cash: **₹{st.session_state.opening_cash:,.2f}**")
            st.write(f"- Expected Closing Cash: **₹{expected_cash:,.2f}**")
            st.write(f"- Physical Cash in Counter: **₹{actual_counter:,.2f}**")
            
            if diff == 0:
                st.success("✅ Cash Counter Matched Perfectly!")
            elif diff > 0:
                st.warning(f"⚠️ ₹{diff:,.2f} EXTRA Cash in Counter")
            else:
                st.error(f"❌ ₹{abs(diff):,.2f} SHORT Cash in Counter")

            st.write(f"- Expected Closing Bank Balance: **₹{expected_bank:,.2f}**")
            st.write(f"### 💰 Total Business Net Worth: ₹{(expected_bank + actual_counter):,.2f}")

    with c2:
        st.info(f"""
        **Day Summary Statistics:**
        - Total Cash Received (+): **₹{today_in:,.2f}**
        - Total Cash Paid (-): **₹{today_out:,.2f}**
        - Total Commission Earned (+): **₹{commission_total:,.2f}**
        - Net Expected Counter Cash: **₹{expected_cash:,.2f}**
        - Net Expected Bank Balance: **₹{expected_bank:,.2f}**
        """)

# BOARD 3: LEDGER CREATION & LIST
with tab3:
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("📖 Create New Ledger Account")
        next_acc = get_next_acc_no()
        st.text_input("Account Number", value=next_acc, disabled=True)
        l_name = st.text_input("Ledger / Customer Name")
        l_type = st.selectbox("Ledger Group / Type", ["Customer", "Sale", "Purchase", "Income", "Expenses"])
        l_opening = st.number_input("Opening Balance (₹)", value=0.0)
        l_side = st.selectbox("Balance Side", ["Cr", "Dr"])

        if st.button("💾 Save Ledger", type="primary"):
            if not l_name:
                st.error("Ledger Name Zaroori Hai!")
            else:
                new_l = {
                    "accNo": next_acc,
                    "name": l_name,
                    "type": l_type,
                    "openingBal": l_opening,
                    "openingType": l_side
                }
                st.session_state.ledgers.append(new_l)
                st.success(f"✅ Ledger '{l_name}' Created Successfully!")
                st.rerun()

    with c2:
        st.subheader("📋 Master Ledger Accounts List")
        if st.session_state.ledgers:
            df_l = pd.DataFrame(st.session_state.ledgers)
            st.dataframe(df_l, use_container_width=True)
        else:
            st.info("Koi Ledger account nahi hai.")

# BOARD 4: ACCOUNTING VOUCHERS
with tab4:
    st.subheader("📝 Accounting Voucher Entry (Sale, Purchase, Income, Expense, Cr/Dr)")
    v_c1, v_c2 = st.columns(2)
    
    with v_c1:
        v_dt = st.date_input("Voucher Date", datetime.now())
        v_ledger_opts = {l['accNo']: f"{l['name']} (Acc: {l['accNo']})" for l in st.session_state.ledgers}
        if not v_ledger_opts:
            st.warning("Pehle Board 3 se ek Ledger Account banayein!")
            v_selected_acc = None
        else:
            v_selected_acc = st.selectbox("Select Ledger Account", list(v_ledger_opts.keys()), format_func=lambda x: v_ledger_opts[x])
        
        v_type = st.selectbox("Voucher Type", ["Sale", "Purchase", "Income", "Expenses", "Receipt", "Payment"])

    with v_c2:
        v_amount = st.number_input("Amount ₹", value=0.0)
        v_side = st.selectbox("Entry Side (Cr/Dr)", ["Cr", "Dr"])
        v_remarks = st.text_input("Remarks / Description")

        if st.button("💾 Save Voucher Entry", type="primary"):
            if not v_selected_acc or v_amount <= 0:
                st.error("⚠️ Sahi Ledger aur Valid Amount select karein!")
            else:
                target_l = next((l for l in st.session_state.ledgers if str(l['accNo']) == str(v_selected_acc)), None)
                l_name = target_l['name'] if target_l else 'N/A'
                v_entry = {
                    "dateTime": str(v_dt),
                    "accNo": v_selected_acc,
                    "ledgerName": l_name,
                    "type": v_type,
                    "amount": v_amount,
                    "crDr": v_side,
                    "remarks": v_remarks or "-"
                }
                st.session_state.vouchers.append(v_entry)
                st.success("✅ Voucher Entry Saved!")
                st.rerun()

    st.markdown("---")
    st.subheader("📋 Master Voucher Daybook")
    if st.session_state.vouchers:
        st.dataframe(pd.DataFrame(st.session_state.vouchers), use_container_width=True)

# MASTER TRANSACTIONS TABLE & EXCEL EXPORT
st.markdown("---")
st.subheader("📋 Master Daybook & Transactions")

if st.session_state.transactions:
    df_txn = pd.DataFrame(st.session_state.transactions)
    st.dataframe(df_txn, use_container_width=True)

    # Export to Excel
    @st.cache_data
    def convert_df_to_excel(df):
        return df.to_csv(index=False).encode('utf-8')

    csv_data = convert_df_to_excel(df_txn)
    st.download_button(
        label="📥 Export Transactions to CSV/Excel",
        data=csv_data,
        file_name=f"Master_DayBook_{datetime.now().strftime('%Y-%m-%d')}.csv",
        mime="text/csv"
    )
else:
    st.info("Abhi tak koi transaction entry nahi huyi hai.")
