import sqlite3
import hashlib
import json
from datetime import datetime

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_db():
    conn = sqlite3.connect('erp_data.db')
    c = conn.cursor()
    
    # 1. Create standard tables if they don't exist
    c.execute('''CREATE TABLE IF NOT EXISTS products 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, 
                  stock INTEGER, price REAL, cost_price REAL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS sales 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, items_json TEXT, 
                  total_price REAL, total_cost REAL, date TEXT, cashier TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
    
    # 2. AUTO-MIGRATION LOGIC (Fixes KeyError: 'total_cost')
    # Check for missing columns in products
    c.execute("PRAGMA table_info(products)")
    existing_prod_cols = [info[1] for info in c.fetchall()]
    if 'cost_price' not in existing_prod_cols:
        c.execute("ALTER TABLE products ADD COLUMN cost_price REAL DEFAULT 0.0")

    # Check for missing columns in sales
    c.execute("PRAGMA table_info(sales)")
    existing_sales_cols = [info[1] for info in c.fetchall()]
    if 'total_cost' not in existing_sales_cols:
        c.execute("ALTER TABLE sales ADD COLUMN total_cost REAL DEFAULT 0.0")
    if 'items_json' not in existing_sales_cols:
        c.execute("ALTER TABLE sales ADD COLUMN items_json TEXT")
    if 'cashier' not in existing_sales_cols:
        c.execute("ALTER TABLE sales ADD COLUMN cashier TEXT")
    
    # 3. Default Admin (1234)
    admin_pass = hash_password("1234")
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin', ?, 'Admin')", (admin_pass,))
    
    conn.commit()
    conn.close()

def register_user(username, password, role):
    conn = sqlite3.connect('erp_data.db')
    c = conn.cursor()
    hashed = hash_password(password)
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?)", (username, hashed, role))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def update_product_details(name, stock, price, cost):
    conn = sqlite3.connect('erp_data.db')
    c = conn.cursor()
    c.execute("UPDATE products SET stock=?, price=?, cost_price=? WHERE name=?", (stock, price, cost, name))
    conn.commit()
    conn.close()

def record_bulk_sale(cart_list, total_price, total_cost, cashier):
    conn = sqlite3.connect('erp_data.db')
    c = conn.cursor()
    items_json = json.dumps(cart_list)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute("INSERT INTO sales (items_json, total_price, total_cost, date, cashier) VALUES (?, ?, ?, ?, ?)",
              (items_json, total_price, total_cost, date_str, cashier))
    inv_id = c.lastrowid
    
    for item in cart_list:
        c.execute("UPDATE products SET stock = stock - ? WHERE name = ?", (item['qty'], item['name']))
        
    conn.commit()
    conn.close()
    return inv_id, date_str

def add_new_product(name, stock, price, cost):
    conn = sqlite3.connect('erp_data.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO products (name, stock, price, cost_price) VALUES (?, ?, ?, ?)", (name, stock, price, cost))
        conn.commit()
        return True
    except: return False
    finally: conn.close()