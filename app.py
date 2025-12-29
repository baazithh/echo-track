import streamlit as st
import pandas as pd
import sqlite3
import json
import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from database_manager import init_db, record_bulk_sale, add_new_product, register_user, update_product_details, hash_password

init_db()
st.set_page_config(page_title="EcoTrack Pro ERP v2025", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'user_role': None, 'user_name': None, 'cart': []})

# --- PDF GENERATOR ---
def generate_bulk_pdf(inv_id, date, cart, total, cashier):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, "OFFICIAL TAX INVOICE", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 10, f"Inv: #{inv_id} | Date: {date} | Cashier: {cashier}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)
    
    pdf.set_font("Helvetica", 'B', 10)
    pdf.cell(90, 8, "Item Description", border=1)
    pdf.cell(30, 8, "Qty", border=1)
    pdf.cell(30, 8, "Rate", border=1)
    pdf.cell(30, 8, "Amount", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_font("Helvetica", size=10)
    for item in cart:
        pdf.cell(90, 8, item['name'], border=1)
        pdf.cell(30, 8, str(item['qty']), border=1)
        pdf.cell(30, 8, f"{item['price']:.2f}", border=1)
        pdf.cell(30, 8, f"{(item['price']*item['qty']):.2f}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.ln(5)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(150, 10, "TOTAL (INR):", align='R')
    pdf.cell(30, 10, f"{total:,.2f}", align='R')
    return bytes(pdf.output())

# --- LOGIN ---
def login_page():
    st.title("🔐 EcoTrack Enterprise Access")
    t1, t2 = st.tabs(["Login", "Register Staff"])
    with t1:
        with st.form("l"):
            u, p = st.text_input("Username"), st.text_input("Password", type="password")
            if st.form_submit_button("Sign In"):
                conn = sqlite3.connect('erp_data.db')
                res = conn.execute("SELECT role, password FROM users WHERE username=?", (u,)).fetchone()
                conn.close()
                if res and res[1] == hash_password(p):
                    st.session_state.update({'logged_in': True, 'user_role': res[0], 'user_name': u})
                    st.rerun()
                else: st.error("Access Denied: Invalid Credentials")
    with t2:
        with st.form("r"):
            nu, np = st.text_input("New ID"), st.text_input("New Pass", type="password")
            nr = st.selectbox("Role", ["Sales", "Admin"])
            if st.form_submit_button("Create"):
                if register_user(nu, np, nr): st.success("Created!")
                else: st.error("Error creating user")

# --- ADMIN DASHBOARD ---
def admin_dashboard():
    st.sidebar.header(f"Admin: {st.session_state['user_name']}")
    choice = st.sidebar.radio("Navigate", ["Financial Intelligence", "Inventory Control", "System Backup"])
    conn = sqlite3.connect('erp_data.db')

    if choice == "Financial Intelligence":
        st.header("📈 Profit & Revenue Analytics")
        sales_df = pd.read_sql("SELECT * FROM sales", conn)
        if not sales_df.empty and 'total_cost' in sales_df.columns:
            rev = sales_df['total_price'].sum()
            cost = sales_df['total_cost'].sum()
            profit = rev - cost
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Revenue", f"₹{rev:,.2f}")
            c2.metric("Net Profit", f"₹{profit:,.2f}", f"{((profit/rev)*100 if rev>0 else 0):.1f}% Margin")
            c3.metric("Cost of Goods", f"₹{cost:,.2f}")
            st.dataframe(sales_df, width='stretch')
        else: st.info("Analytics will appear after your first sale.")

    elif choice == "Inventory Control":
        st.header("📦 Product Catalog")
        df = pd.read_sql("SELECT * FROM products", conn)
        st.dataframe(df, width='stretch')
        st.subheader("Edit or Add Products")
        with st.form("p_edit"):
            name = st.text_input("Item Name")
            c1, c2, c3 = st.columns(3)
            stock = c1.number_input("Stock", min_value=0)
            price = c2.number_input("Selling Price", min_value=0.0)
            cost = c3.number_input("Cost Price", min_value=0.0)
            if st.form_submit_button("Commit Changes"):
                if name in df['name'].values:
                    update_product_details(name, stock, price, cost)
                else:
                    add_new_product(name, stock, price, cost)
                st.rerun()

    elif choice == "System Backup":
        st.header("🛠️ System Maintenance")
        st.write("Keep your business data safe. Use the buttons below to export your data.")
        
        # 1. SQLite Database Backup
        if os.path.exists("erp_data.db"):
            with open("erp_data.db", "rb") as f:
                db_bytes = f.read()
            st.download_button(
                label="📥 Download Full Database (.db)",
                data=db_bytes,
                file_name=f"erp_backup_{pd.Timestamp.now().strftime('%Y%m%d')}.db",
                mime="application/x-sqlite3",
                width='stretch'
            )
        
        # 2. CSV Sales Report
        st.divider()
        st.subheader("Sales Export")
        sales_df = pd.read_sql("SELECT * FROM sales", conn)
        if not sales_df.empty:
            csv = sales_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📊 Export Sales History to CSV",
                data=csv,
                file_name="sales_report.csv",
                mime="text/csv",
                width='stretch'
            )
        else:
            st.info("No sales history to export yet.")

    conn.close()

# --- USER DASHBOARD (POS) ---
def user_dashboard():
    st.sidebar.header(f"Staff: {st.session_state['user_name']}")
    st.header("🛒 Point of Sale Terminal")
    conn = sqlite3.connect('erp_data.db')
    df = pd.read_sql("SELECT * FROM products", conn)
    
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.subheader("Add to Order")
        item_list = df['name'].tolist() if not df.empty else []
        item_sel = st.selectbox("Search Item", item_list)
        qty_sel = st.number_input("Qty", min_value=1, step=1)
        if st.button("Add to Cart"):
            if item_sel:
                p_data = df[df['name'] == item_sel].iloc[0]
                if p_data['stock'] >= qty_sel:
                    st.session_state.cart.append({'name':item_sel, 'qty':qty_sel, 'price':p_data['price'], 'cost':p_data['cost_price']})
                    st.rerun()
                else: st.error("Low Stock!")

    with col2:
        st.subheader("Checkout Basket")
        if st.session_state.cart:
            c_df = pd.DataFrame(st.session_state.cart)
            st.table(c_df[['name', 'qty', 'price']])
            total_val = sum(x['price']*x['qty'] for x in st.session_state.cart)
            total_cost = sum(x['cost']*x['qty'] for x in st.session_state.cart)
            st.write(f"## Grand Total: ₹{total_val:,.2f}")
            if st.button("Generate Invoice"):
                inv_id, date = record_bulk_sale(st.session_state.cart, total_val, total_cost, st.session_state['user_name'])
                pdf = generate_bulk_pdf(inv_id, date, st.session_state.cart, total_val, st.session_state['user_name'])
                st.download_button("📥 Print Invoice", pdf, file_name=f"Invoice_{inv_id}.pdf")
                st.session_state.cart = []
                st.success("Sale Completed")
        else: st.info("Basket is empty")
    
    if st.sidebar.button("Clear Basket"):
        st.session_state.cart = []
        st.rerun()
    conn.close()

# --- MAIN ---
if st.session_state['logged_in']:
    if st.sidebar.button("Logout"):
        st.session_state.update({'logged_in': False, 'cart': []})
        st.rerun()
    if st.session_state['user_role'] == "Admin": admin_dashboard()
    else: user_dashboard()
else: login_page()