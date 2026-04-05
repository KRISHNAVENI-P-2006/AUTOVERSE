from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db, BRANCHES
from functools import wraps
from datetime import date
import os

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
app.config['SESSION_COOKIE_NAME'] = 'autoverse_session'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

def fmt_inr(amount):
    try:
        amount = float(amount)
        if amount >= 10000000: return f"₹{amount/10000000:.2f} Cr"
        elif amount >= 100000: return f"₹{amount/100000:.2f} L"
        else: return f"₹{int(amount):,}"
    except: return "₹0"

app.jinja_env.globals['fmt_inr'] = fmt_inr
app.jinja_env.globals['BRANCHES'] = BRANCHES
init_db()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    role = session.get('role')
    if role == 'admin': return redirect(url_for('admin_dashboard'))
    elif role == 'staff': return redirect(url_for('staff_dashboard'))
    return redirect(url_for('customer_dashboard'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        db = get_db()
        user = db.execute("SELECT * FROM Users WHERE username=?", (username,)).fetchone()
        db.close()
        if user and check_password_hash(user['password'], password):
            session.clear()
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'Welcome back, {username}!', 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'staff':
                return redirect(url_for('staff_dashboard'))
            else:
                return redirect(url_for('customer_dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET','POST'])
def forgot_password():
    found_user = None
    found_role = None
    if request.method == 'POST':
        step = request.form.get('step','find')
        username = request.form.get('username','').strip()
        if step == 'find':
            db = get_db()
            user = db.execute("SELECT username, role FROM Users WHERE username=?", (username,)).fetchone()
            db.close()
            if not user:
                flash('Username not found.', 'danger')
            else:
                found_user = user['username']
                found_role = user['role'].title()
        elif step == 'reset':
            new_pass = request.form.get('new_password','')
            confirm  = request.form.get('confirm_password','')
            if new_pass != confirm:
                flash('Passwords do not match.', 'danger')
                found_user = username; found_role = ''
            elif len(new_pass) < 6:
                flash('Password must be at least 6 characters.', 'danger')
                found_user = username; found_role = ''
            else:
                db = get_db()
                db.execute("UPDATE Users SET password=? WHERE username=?",
                           (generate_password_hash(new_pass), username))
                db.commit(); db.close()
                flash('Password reset successfully! Please log in.', 'success')
                return redirect(url_for('login'))
    return render_template('forgot_password.html', found_user=found_user, found_role=found_role)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        name = request.form['name'].strip()
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('register.html')
        db = get_db()
        try:
            db.execute("INSERT INTO Users (username,password,role) VALUES (?,?,?)",
                       (username, generate_password_hash(password), 'customer'))
            uid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO Customer (name,phone,email,address,user_id) VALUES (?,?,?,?,?)",
                       (name, request.form.get('phone',''), request.form.get('email',''),
                        request.form.get('address',''), uid))
            db.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except:
            flash('Username already taken.', 'danger')
        finally:
            db.close()
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    role = session['role']
    if role == 'admin': return redirect(url_for('admin_dashboard'))
    elif role == 'staff': return redirect(url_for('staff_dashboard'))
    else: return redirect(url_for('customer_dashboard'))

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN PORTAL
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/admin')
@login_required
@role_required('admin')
def admin_dashboard():
    db = get_db()
    stats = {
        'vehicles':    db.execute("SELECT COUNT(*) FROM Vehicle").fetchone()[0],
        'available':   db.execute("SELECT COUNT(*) FROM Vehicle WHERE status='available'").fetchone()[0],
        'sold':        db.execute("SELECT COUNT(*) FROM Vehicle WHERE status='sold'").fetchone()[0],
        'customers':   db.execute("SELECT COUNT(*) FROM Customer").fetchone()[0],
        'staff':       db.execute("SELECT COUNT(*) FROM Sales_Staff").fetchone()[0],
        'sales':       db.execute("SELECT COUNT(*) FROM Sales").fetchone()[0],
        'revenue':     db.execute("SELECT COALESCE(SUM(sale_price),0) FROM Sales").fetchone()[0],
        'inquiries':   db.execute("SELECT COUNT(*) FROM Inquiry").fetchone()[0],
        'pending_inq': db.execute("SELECT COUNT(*) FROM Inquiry WHERE status='open'").fetchone()[0],
    }
    recent_sales = db.execute("""
        SELECT s.sale_id, m.name||' '||v.model as vehicle, c.name as customer,
               ss.name as staff, ss.branch, s.sale_price, s.sale_date
        FROM Sales s JOIN Vehicle v ON s.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        JOIN Customer c ON s.customer_id=c.customer_id
        JOIN Sales_Staff ss ON s.staff_id=ss.staff_id
        ORDER BY s.sale_date DESC LIMIT 6""").fetchall()
    monthly = db.execute("""
        SELECT strftime('%Y-%m', sale_date) as month,
               SUM(sale_price) as revenue, COUNT(*) as count
        FROM Sales GROUP BY month ORDER BY month DESC LIMIT 12""").fetchall()
    branch_revenue = db.execute("""
        SELECT ss.branch, COUNT(s.sale_id) as sales,
               COALESCE(SUM(s.sale_price),0) as revenue
        FROM Sales_Staff ss LEFT JOIN Sales s ON ss.staff_id=s.staff_id
        GROUP BY ss.branch ORDER BY revenue DESC""").fetchall()
    db.close()
    return render_template('admin/dashboard.html', stats=stats, recent_sales=recent_sales,
                           monthly=[dict(r) for r in monthly],
                           branch_revenue=[dict(r) for r in branch_revenue])

@app.route('/admin/manufacturers')
@login_required
@role_required('admin')
def admin_manufacturers():
    db = get_db()
    rows = db.execute("""SELECT m.*, COUNT(v.vehicle_id) as vehicle_count
        FROM Manufacturer m LEFT JOIN Vehicle v ON m.manufacturer_id=v.manufacturer_id
        GROUP BY m.manufacturer_id ORDER BY m.name""").fetchall()
    db.close()
    return render_template('admin/manufacturers.html', manufacturers=rows)

@app.route('/admin/manufacturers/add', methods=['GET','POST'])
@login_required
@role_required('admin')
def admin_add_manufacturer():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO Manufacturer (name,country,founded_year,website) VALUES (?,?,?,?)",
                   (request.form['name'], request.form.get('country',''),
                    request.form.get('founded_year') or None, request.form.get('website','')))
        db.commit(); db.close(); flash('Manufacturer added.', 'success')
        return redirect(url_for('admin_manufacturers'))
    return render_template('admin/manufacturer_form.html', mfr=None, action='Add')

@app.route('/admin/manufacturers/edit/<int:id>', methods=['GET','POST'])
@login_required
@role_required('admin')
def admin_edit_manufacturer(id):
    db = get_db()
    mfr = db.execute("SELECT * FROM Manufacturer WHERE manufacturer_id=?", (id,)).fetchone()
    if request.method == 'POST':
        db.execute("UPDATE Manufacturer SET name=?,country=?,founded_year=?,website=? WHERE manufacturer_id=?",
                   (request.form['name'], request.form.get('country',''),
                    request.form.get('founded_year') or None, request.form.get('website',''), id))
        db.commit(); db.close(); flash('Updated.', 'success')
        return redirect(url_for('admin_manufacturers'))
    db.close()
    return render_template('admin/manufacturer_form.html', mfr=mfr, action='Edit')

@app.route('/admin/manufacturers/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_manufacturer(id):
    db = get_db()
    try:
        db.execute("DELETE FROM Manufacturer WHERE manufacturer_id=?", (id,))
        db.commit(); flash('Deleted.', 'success')
    except: flash('Cannot delete: vehicles exist.', 'danger')
    finally: db.close()
    return redirect(url_for('admin_manufacturers'))

@app.route('/admin/vehicles')
@login_required
@role_required('admin')
def admin_vehicles():
    db = get_db()
    search = request.args.get('search',''); status_f = request.args.get('status','')
    q = "SELECT v.*,m.name as manufacturer_name FROM Vehicle v JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id WHERE 1=1"
    params = []
    if search: q += " AND (v.model LIKE ? OR m.name LIKE ?)"; params += [f'%{search}%']*2
    if status_f: q += " AND v.status=?"; params.append(status_f)
    vehicles = db.execute(q+" ORDER BY v.vehicle_id DESC", params).fetchall()
    mfrs = db.execute("SELECT * FROM Manufacturer ORDER BY name").fetchall()
    db.close()
    return render_template('admin/vehicles.html', vehicles=vehicles, manufacturers=mfrs,
                           search=search, status_filter=status_f)

@app.route('/admin/vehicles/add', methods=['GET','POST'])
@login_required
@role_required('admin')
def admin_add_vehicle():
    db = get_db()
    if request.method == 'POST':
        db.execute("""INSERT INTO Vehicle (manufacturer_id,model,year,price,color,available_colors,
                      fuel_type,transmission,mileage,description,image_url,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (request.form['manufacturer_id'],request.form['model'],request.form['year'],
                    request.form['price'],request.form.get('color',''),request.form.get('available_colors',''),
                    request.form.get('fuel_type',''),request.form.get('transmission',''),
                    request.form.get('mileage',0),request.form.get('description',''),
                    request.form.get('image_url',''),request.form.get('status','available')))
        db.commit(); db.close(); flash('Vehicle added.', 'success')
        return redirect(url_for('admin_vehicles'))
    mfrs = db.execute("SELECT * FROM Manufacturer ORDER BY name").fetchall()
    db.close()
    return render_template('admin/vehicle_form.html', vehicle=None, manufacturers=mfrs, action='Add')

@app.route('/admin/vehicles/edit/<int:id>', methods=['GET','POST'])
@login_required
@role_required('admin')
def admin_edit_vehicle(id):
    db = get_db()
    veh = db.execute("SELECT * FROM Vehicle WHERE vehicle_id=?", (id,)).fetchone()
    if request.method == 'POST':
        db.execute("""UPDATE Vehicle SET manufacturer_id=?,model=?,year=?,price=?,color=?,available_colors=?,
                      fuel_type=?,transmission=?,mileage=?,description=?,image_url=?,status=? WHERE vehicle_id=?""",
                   (request.form['manufacturer_id'],request.form['model'],request.form['year'],
                    request.form['price'],request.form.get('color',''),request.form.get('available_colors',''),
                    request.form.get('fuel_type',''),request.form.get('transmission',''),
                    request.form.get('mileage',0),request.form.get('description',''),
                    request.form.get('image_url',''),request.form.get('status','available'),id))
        db.commit(); db.close(); flash('Vehicle updated.', 'success')
        return redirect(url_for('admin_vehicles'))
    mfrs = db.execute("SELECT * FROM Manufacturer ORDER BY name").fetchall()
    db.close()
    return render_template('admin/vehicle_form.html', vehicle=veh, manufacturers=mfrs, action='Edit')

@app.route('/admin/vehicles/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_vehicle(id):
    db = get_db()
    try:
        db.execute("DELETE FROM Vehicle WHERE vehicle_id=?", (id,))
        db.commit(); flash('Deleted.', 'success')
    except: flash('Cannot delete: vehicle has records.', 'danger')
    finally: db.close()
    return redirect(url_for('admin_vehicles'))

@app.route('/admin/customers')
@login_required
@role_required('admin')
def admin_customers():
    db = get_db()
    search = request.args.get('search','')
    q = "SELECT c.*,u.username FROM Customer c LEFT JOIN Users u ON c.user_id=u.user_id WHERE 1=1"
    params = []
    if search: q += " AND (c.name LIKE ? OR c.email LIKE ? OR c.phone LIKE ?)"; params += [f'%{search}%']*3
    rows = db.execute(q+" ORDER BY c.customer_id DESC", params).fetchall()
    db.close()
    return render_template('admin/customers.html', customers=rows, search=search)

@app.route('/admin/customers/add', methods=['GET','POST'])
@login_required
@role_required('admin')
def admin_add_customer():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO Customer (name,phone,email,address) VALUES (?,?,?,?)",
                   (request.form['name'],request.form.get('phone',''),request.form.get('email',''),request.form.get('address','')))
        db.commit(); db.close(); flash('Customer added.', 'success')
        return redirect(url_for('admin_customers'))
    return render_template('admin/customer_form.html', customer=None, action='Add')

@app.route('/admin/customers/edit/<int:id>', methods=['GET','POST'])
@login_required
@role_required('admin')
def admin_edit_customer(id):
    db = get_db()
    cust = db.execute("SELECT * FROM Customer WHERE customer_id=?", (id,)).fetchone()
    if request.method == 'POST':
        db.execute("UPDATE Customer SET name=?,phone=?,email=?,address=? WHERE customer_id=?",
                   (request.form['name'],request.form.get('phone',''),request.form.get('email',''),request.form.get('address',''),id))
        db.commit(); db.close(); flash('Updated.', 'success')
        return redirect(url_for('admin_customers'))
    db.close()
    return render_template('admin/customer_form.html', customer=cust, action='Edit')

@app.route('/admin/customers/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_customer(id):
    db = get_db()
    try:
        db.execute("DELETE FROM Customer WHERE customer_id=?", (id,))
        db.commit(); flash('Deleted.', 'success')
    except: flash('Cannot delete: customer has records.', 'danger')
    finally: db.close()
    return redirect(url_for('admin_customers'))

@app.route('/admin/staff')
@login_required
@role_required('admin')
def admin_staff():
    db = get_db()
    rows = db.execute("""SELECT ss.*, u.username,
               COUNT(s.sale_id) as sales_count, COALESCE(SUM(s.sale_price),0) as total_sales
        FROM Sales_Staff ss LEFT JOIN Users u ON ss.user_id=u.user_id
        LEFT JOIN Sales s ON ss.staff_id=s.staff_id
        GROUP BY ss.staff_id ORDER BY ss.branch, ss.name""").fetchall()
    db.close()
    return render_template('admin/staff.html', staff_list=rows)

@app.route('/admin/staff/add', methods=['GET','POST'])
@login_required
@role_required('admin')
def admin_add_staff():
    if request.method == 'POST':
        db = get_db()
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        uid = None
        if username and password:
            try:
                db.execute("INSERT INTO Users (username,password,role) VALUES (?,?,?)",
                           (username, generate_password_hash(password), 'staff'))
                uid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            except:
                flash('Username taken.', 'danger'); db.close()
                return redirect(url_for('admin_add_staff'))
        db.execute("INSERT INTO Sales_Staff (name,phone,email,branch,salary,user_id) VALUES (?,?,?,?,?,?)",
                   (request.form['name'],request.form.get('phone',''),request.form.get('email',''),
                    request.form.get('branch',''),request.form.get('salary',0) or 0, uid))
        db.commit(); db.close(); flash('Staff added.', 'success')
        return redirect(url_for('admin_staff'))
    return render_template('admin/staff_form.html', staff=None, action='Add')

@app.route('/admin/staff/edit/<int:id>', methods=['GET','POST'])
@login_required
@role_required('admin')
def admin_edit_staff(id):
    db = get_db()
    s = db.execute("SELECT ss.*,u.username FROM Sales_Staff ss LEFT JOIN Users u ON ss.user_id=u.user_id WHERE ss.staff_id=?", (id,)).fetchone()
    if request.method == 'POST':
        db.execute("UPDATE Sales_Staff SET name=?,phone=?,email=?,branch=?,salary=? WHERE staff_id=?",
                   (request.form['name'],request.form.get('phone',''),request.form.get('email',''),
                    request.form.get('branch',''),request.form.get('salary',0) or 0, id))
        new_pass = request.form.get('new_password','')
        if new_pass and s['user_id']:
            db.execute("UPDATE Users SET password=? WHERE user_id=?",
                       (generate_password_hash(new_pass), s['user_id']))
        db.commit(); db.close(); flash('Staff updated.', 'success')
        return redirect(url_for('admin_staff'))
    db.close()
    return render_template('admin/staff_form.html', staff=s, action='Edit')

@app.route('/admin/staff/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_staff(id):
    db = get_db()
    try:
        db.execute("DELETE FROM Sales_Staff WHERE staff_id=?", (id,))
        db.commit(); flash('Deleted.', 'success')
    except: flash('Cannot delete: staff has records.', 'danger')
    finally: db.close()
    return redirect(url_for('admin_staff'))

@app.route('/admin/sales')
@login_required
@role_required('admin')
def admin_sales():
    db = get_db()
    rows = db.execute("""SELECT s.*, m.name||' '||v.model as vehicle, v.year,
               c.name as customer_name, ss.name as staff_name, ss.branch
        FROM Sales s JOIN Vehicle v ON s.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        JOIN Customer c ON s.customer_id=c.customer_id
        JOIN Sales_Staff ss ON s.staff_id=ss.staff_id
        ORDER BY s.sale_date DESC""").fetchall()
    db.close()
    return render_template('admin/sales.html', sales=rows)

@app.route('/admin/sales/add', methods=['GET','POST'])
@login_required
@role_required('admin')
def admin_add_sale():
    db = get_db()
    if request.method == 'POST':
        vid = request.form['vehicle_id']
        try:
            db.execute("INSERT INTO Sales (vehicle_id,customer_id,staff_id,sale_price,sale_date,notes) VALUES (?,?,?,?,?,?)",
                       (vid,request.form['customer_id'],request.form['staff_id'],
                        request.form['sale_price'],request.form['sale_date'],request.form.get('notes','')))
            db.execute("UPDATE Vehicle SET status='sold' WHERE vehicle_id=?", (vid,))
            db.commit(); flash('Sale recorded!', 'success'); db.close()
            return redirect(url_for('admin_sales'))
        except Exception as e: flash(f'Error: {e}', 'danger')
    vehicles  = db.execute("SELECT v.*,m.name as mfr FROM Vehicle v JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id WHERE v.status='available'").fetchall()
    customers = db.execute("SELECT * FROM Customer ORDER BY name").fetchall()
    staff_list= db.execute("SELECT * FROM Sales_Staff ORDER BY branch,name").fetchall()
    db.close()
    return render_template('admin/sale_form.html', vehicles=vehicles, customers=customers,
                           staff_list=staff_list, today=date.today().isoformat())

@app.route('/admin/sales/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_sale(id):
    db = get_db()
    sale = db.execute("SELECT vehicle_id FROM Sales WHERE sale_id=?", (id,)).fetchone()
    if sale:
        db.execute("DELETE FROM Sales WHERE sale_id=?", (id,))
        db.execute("UPDATE Vehicle SET status='available' WHERE vehicle_id=?", (sale['vehicle_id'],))
        db.commit(); flash('Sale deleted.', 'success')
    db.close()
    return redirect(url_for('admin_sales'))

@app.route('/admin/inquiries')
@login_required
@role_required('admin')
def admin_inquiries():
    db = get_db()
    branch_f = request.args.get('branch',''); status_f = request.args.get('status','')
    q = """SELECT i.*, c.name as customer_name, m.name||' '||v.model as vehicle,
               ss.name as staff_name,
               (SELECT COUNT(*) FROM InquiryMessage im WHERE im.inquiry_id=i.inquiry_id) as msg_count,
               (SELECT sent_at FROM InquiryMessage im WHERE im.inquiry_id=i.inquiry_id ORDER BY sent_at DESC LIMIT 1) as last_msg_at,
               (SELECT message FROM InquiryMessage im WHERE im.inquiry_id=i.inquiry_id ORDER BY sent_at DESC LIMIT 1) as last_msg
        FROM Inquiry i JOIN Customer c ON i.customer_id=c.customer_id
        JOIN Vehicle v ON i.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        LEFT JOIN Sales_Staff ss ON i.staff_id=ss.staff_id WHERE 1=1"""
    params = []
    if branch_f: q += " AND i.branch=?"; params.append(branch_f)
    if status_f: q += " AND i.status=?"; params.append(status_f)
    rows = db.execute(q+" ORDER BY COALESCE(last_msg_at, i.inquiry_date) DESC", params).fetchall()
    # Unread count for badge
    unread = db.execute("""SELECT COUNT(*) FROM InquiryMessage
        WHERE sender_role='customer' AND is_read=0""").fetchone()[0]
    db.close()
    return render_template('admin/inquiries.html', inquiries=rows,
                           branch_filter=branch_f, status_filter=status_f,
                           unread=unread, branches=BRANCHES)

@app.route('/admin/inquiries/<int:id>', methods=['GET','POST'])
@login_required
@role_required('admin')
def admin_inquiry_chat(id):
    db = get_db()
    inq = db.execute("""SELECT i.*, c.name as customer_name, m.name||' '||v.model as vehicle, v.image_url
        FROM Inquiry i JOIN Customer c ON i.customer_id=c.customer_id
        JOIN Vehicle v ON i.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        WHERE i.inquiry_id=?""", (id,)).fetchone()
    if not inq:
        flash('Inquiry not found.', 'danger')
        return redirect(url_for('admin_inquiries'))
    if request.method == 'POST':
        action = request.form.get('action','send')
        if action == 'send':
            msg = request.form.get('message','').strip()
            if msg:
                db.execute("INSERT INTO InquiryMessage (inquiry_id,sender_role,sender_name,message,sent_at,is_read) VALUES (?,?,?,?,?,0)",
                           (id,'admin','Admin',msg,date.today().isoformat()+' '+__import__('datetime').datetime.now().strftime('%H:%M')))
                db.commit()
        elif action == 'close':
            db.execute("UPDATE Inquiry SET status='closed' WHERE inquiry_id=?", (id,))
            db.commit()
        elif action == 'assign':
            db.execute("UPDATE Inquiry SET staff_id=? WHERE inquiry_id=?",
                       (request.form.get('staff_id') or None, id))
            db.commit()
        db.close()
        return redirect(url_for('admin_inquiry_chat', id=id))
    # Mark customer messages as read
    db.execute("UPDATE InquiryMessage SET is_read=1 WHERE inquiry_id=? AND sender_role='customer'", (id,))
    db.commit()
    messages = db.execute("SELECT * FROM InquiryMessage WHERE inquiry_id=? ORDER BY sent_at", (id,)).fetchall()
    staff_list = db.execute("SELECT * FROM Sales_Staff WHERE branch=? ORDER BY name", (inq['branch'],)).fetchall()
    db.close()
    return render_template('admin/inquiry_chat.html', inquiry=inq, messages=messages, staff_list=staff_list)

@app.route('/admin/inquiries/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_inquiry(id):
    db = get_db()
    db.execute("DELETE FROM Inquiry WHERE inquiry_id=?", (id,))
    db.commit(); db.close(); flash('Deleted.', 'success')
    return redirect(url_for('admin_inquiries'))

@app.route('/admin/reports')
@login_required
@role_required('admin')
def admin_reports():
    db = get_db()
    monthly = db.execute("""SELECT strftime('%Y-%m', sale_date) as month,
               COUNT(*) as sales_count, SUM(sale_price) as revenue, AVG(sale_price) as avg_price
        FROM Sales GROUP BY month ORDER BY month DESC LIMIT 12""").fetchall()
    staff_perf = db.execute("""SELECT ss.name, ss.branch, COUNT(s.sale_id) as sales_count,
               COALESCE(SUM(s.sale_price),0) as total_revenue
        FROM Sales_Staff ss LEFT JOIN Sales s ON ss.staff_id=s.staff_id
        GROUP BY ss.staff_id ORDER BY total_revenue DESC""").fetchall()
    top_vehicles = db.execute("""SELECT m.name as manufacturer, v.model, v.year,
               COUNT(s.sale_id) as times_sold, COALESCE(SUM(s.sale_price),0) as revenue
        FROM Vehicle v JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        LEFT JOIN Sales s ON v.vehicle_id=s.vehicle_id
        GROUP BY v.vehicle_id ORDER BY times_sold DESC LIMIT 10""").fetchall()
    fuel_stats = db.execute("""SELECT v.fuel_type, COUNT(s.sale_id) as count,
               COALESCE(SUM(s.sale_price),0) as revenue
        FROM Vehicle v LEFT JOIN Sales s ON v.vehicle_id=s.vehicle_id
        GROUP BY v.fuel_type ORDER BY count DESC""").fetchall()
    mfr_rev = db.execute("""SELECT m.name, COUNT(s.sale_id) as sales,
               COALESCE(SUM(s.sale_price),0) as revenue
        FROM Manufacturer m JOIN Vehicle v ON m.manufacturer_id=v.manufacturer_id
        LEFT JOIN Sales s ON v.vehicle_id=s.vehicle_id
        GROUP BY m.manufacturer_id ORDER BY revenue DESC""").fetchall()
    branch_rev = db.execute("""SELECT ss.branch,
               COUNT(DISTINCT s.sale_id) as sales_count,
               COALESCE(SUM(s.sale_price),0) as revenue,
               COALESCE(AVG(s.sale_price),0) as avg_sale,
               COUNT(DISTINCT i.inquiry_id) as inquiries
        FROM Sales_Staff ss
        LEFT JOIN Sales s ON ss.staff_id=s.staff_id
        LEFT JOIN Inquiry i ON i.branch=ss.branch
        GROUP BY ss.branch ORDER BY revenue DESC""").fetchall()
    totals = db.execute("""SELECT COUNT(*) as total_sales,
               COALESCE(SUM(sale_price),0) as total_revenue,
               COALESCE(AVG(sale_price),0) as avg_sale,
               COALESCE(MAX(sale_price),0) as max_sale
        FROM Sales""").fetchone()
    db.close()
    def rd(rows): return [dict(r) for r in rows]
    return render_template('admin/reports.html', monthly=rd(monthly), staff_perf=rd(staff_perf),
                           top_vehicles=rd(top_vehicles), fuel_stats=rd(fuel_stats),
                           mfr_rev=rd(mfr_rev), branch_rev=rd(branch_rev), totals=dict(totals))

@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    db = get_db()
    rows = db.execute("SELECT * FROM Users ORDER BY role, username").fetchall()
    db.close()
    return render_template('admin/users.html', users=rows)

@app.route('/admin/users/add', methods=['GET','POST'])
@login_required
@role_required('admin')
def admin_add_user():
    if request.method == 'POST':
        db = get_db()
        try:
            db.execute("INSERT INTO Users (username,password,role) VALUES (?,?,?)",
                       (request.form['username'],generate_password_hash(request.form['password']),request.form['role']))
            db.commit(); flash('User added.', 'success')
        except: flash('Username taken.', 'danger')
        finally: db.close()
        return redirect(url_for('admin_users'))
    return render_template('admin/user_form.html', user=None, action='Add')

@app.route('/admin/users/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_user(id):
    if id == session['user_id']:
        flash('Cannot delete yourself.', 'danger')
    else:
        db = get_db()
        db.execute("DELETE FROM Users WHERE user_id=?", (id,))
        db.commit(); db.close(); flash('User deleted.', 'success')
    return redirect(url_for('admin_users'))

# ═══════════════════════════════════════════════════════════════════════════════
# STAFF PORTAL
# ═══════════════════════════════════════════════════════════════════════════════

def get_staff_record():
    db = get_db()
    s = db.execute("SELECT * FROM Sales_Staff WHERE user_id=?", (session['user_id'],)).fetchone()
    db.close()
    return s

@app.route('/staff')
@login_required
@role_required('staff')
def staff_dashboard():
    staff = get_staff_record()
    if not staff:
        flash('Staff record not found. Contact admin.', 'danger')
        return redirect(url_for('logout'))
    db = get_db()
    branch = staff['branch']
    stats = {
        'my_sales':    db.execute("SELECT COUNT(*) FROM Sales WHERE staff_id=?", (staff['staff_id'],)).fetchone()[0],
        'my_revenue':  db.execute("SELECT COALESCE(SUM(sale_price),0) FROM Sales WHERE staff_id=?", (staff['staff_id'],)).fetchone()[0],
        'branch_inq':  db.execute("SELECT COUNT(*) FROM Inquiry WHERE branch=?", (branch,)).fetchone()[0],
        'pending_inq': db.execute("SELECT COUNT(*) FROM Inquiry WHERE branch=? AND status='pending'", (branch,)).fetchone()[0],
        'available':   db.execute("SELECT COUNT(*) FROM Vehicle WHERE status='available'").fetchone()[0],
    }
    recent_inq = db.execute("""SELECT i.*, c.name as customer_name,
               m.name||' '||v.model as vehicle
        FROM Inquiry i JOIN Customer c ON i.customer_id=c.customer_id
        JOIN Vehicle v ON i.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        WHERE i.branch=? ORDER BY i.inquiry_date DESC LIMIT 5""", (branch,)).fetchall()
    recent_sales = db.execute("""SELECT s.*, m.name||' '||v.model as vehicle,
               c.name as customer_name
        FROM Sales s JOIN Vehicle v ON s.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        JOIN Customer c ON s.customer_id=c.customer_id
        WHERE s.staff_id=? ORDER BY s.sale_date DESC LIMIT 5""", (staff['staff_id'],)).fetchall()
    db.close()
    return render_template('staff/dashboard.html', staff=staff, stats=stats,
                           recent_inq=recent_inq, recent_sales=recent_sales)

@app.route('/staff/vehicles')
@login_required
@role_required('staff')
def staff_vehicles():
    db = get_db()
    search = request.args.get('search',''); status_f = request.args.get('status','')
    q = "SELECT v.*,m.name as manufacturer_name FROM Vehicle v JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id WHERE 1=1"
    params = []
    if search: q += " AND (v.model LIKE ? OR m.name LIKE ?)"; params += [f'%{search}%']*2
    if status_f: q += " AND v.status=?"; params.append(status_f)
    vehicles = db.execute(q+" ORDER BY v.vehicle_id DESC", params).fetchall()
    mfrs = db.execute("SELECT * FROM Manufacturer ORDER BY name").fetchall()
    db.close()
    return render_template('staff/vehicles.html', vehicles=vehicles, manufacturers=mfrs,
                           search=search, status_filter=status_f)

@app.route('/staff/vehicles/add', methods=['GET','POST'])
@login_required
@role_required('staff')
def staff_add_vehicle():
    db = get_db()
    if request.method == 'POST':
        db.execute("""INSERT INTO Vehicle (manufacturer_id,model,year,price,color,available_colors,
                      fuel_type,transmission,mileage,description,image_url,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (request.form['manufacturer_id'],request.form['model'],request.form['year'],
                    request.form['price'],request.form.get('color',''),request.form.get('available_colors',''),
                    request.form.get('fuel_type',''),request.form.get('transmission',''),
                    request.form.get('mileage',0),request.form.get('description',''),
                    request.form.get('image_url',''),request.form.get('status','available')))
        db.commit(); db.close(); flash('Vehicle added.', 'success')
        return redirect(url_for('staff_vehicles'))
    mfrs = db.execute("SELECT * FROM Manufacturer ORDER BY name").fetchall()
    db.close()
    return render_template('staff/vehicle_form.html', vehicle=None, manufacturers=mfrs, action='Add')

@app.route('/staff/vehicles/edit/<int:id>', methods=['GET','POST'])
@login_required
@role_required('staff')
def staff_edit_vehicle(id):
    db = get_db()
    veh = db.execute("SELECT * FROM Vehicle WHERE vehicle_id=?", (id,)).fetchone()
    if request.method == 'POST':
        db.execute("""UPDATE Vehicle SET manufacturer_id=?,model=?,year=?,price=?,color=?,available_colors=?,
                      fuel_type=?,transmission=?,mileage=?,description=?,image_url=?,status=? WHERE vehicle_id=?""",
                   (request.form['manufacturer_id'],request.form['model'],request.form['year'],
                    request.form['price'],request.form.get('color',''),request.form.get('available_colors',''),
                    request.form.get('fuel_type',''),request.form.get('transmission',''),
                    request.form.get('mileage',0),request.form.get('description',''),
                    request.form.get('image_url',''),request.form.get('status','available'),id))
        db.commit(); db.close(); flash('Updated.', 'success')
        return redirect(url_for('staff_vehicles'))
    mfrs = db.execute("SELECT * FROM Manufacturer ORDER BY name").fetchall()
    db.close()
    return render_template('staff/vehicle_form.html', vehicle=veh, manufacturers=mfrs, action='Edit')

@app.route('/staff/customers')
@login_required
@role_required('staff')
def staff_customers():
    db = get_db()
    rows = db.execute("SELECT * FROM Customer ORDER BY name").fetchall()
    db.close()
    return render_template('staff/customers.html', customers=rows)

@app.route('/staff/sales')
@login_required
@role_required('staff')
def staff_sales():
    staff = get_staff_record()
    db = get_db()
    rows = db.execute("""SELECT s.*, m.name||' '||v.model as vehicle, v.year,
               c.name as customer_name
        FROM Sales s JOIN Vehicle v ON s.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        JOIN Customer c ON s.customer_id=c.customer_id
        WHERE s.staff_id=? ORDER BY s.sale_date DESC""", (staff['staff_id'],)).fetchall()
    db.close()
    return render_template('staff/sales.html', sales=rows, staff=staff)

@app.route('/staff/sales/add', methods=['GET','POST'])
@login_required
@role_required('staff')
def staff_add_sale():
    staff = get_staff_record()
    db = get_db()
    if request.method == 'POST':
        vid = request.form['vehicle_id']
        try:
            db.execute("INSERT INTO Sales (vehicle_id,customer_id,staff_id,sale_price,sale_date,notes) VALUES (?,?,?,?,?,?)",
                       (vid,request.form['customer_id'],staff['staff_id'],
                        request.form['sale_price'],request.form['sale_date'],request.form.get('notes','')))
            db.execute("UPDATE Vehicle SET status='sold' WHERE vehicle_id=?", (vid,))
            db.commit(); flash('Sale recorded!', 'success'); db.close()
            return redirect(url_for('staff_sales'))
        except Exception as e: flash(f'Error: {e}', 'danger')
    vehicles  = db.execute("SELECT v.*,m.name as mfr FROM Vehicle v JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id WHERE v.status='available'").fetchall()
    customers = db.execute("SELECT * FROM Customer ORDER BY name").fetchall()
    db.close()
    return render_template('staff/sale_form.html', vehicles=vehicles,
                           customers=customers, staff=staff, today=date.today().isoformat())

@app.route('/staff/inquiries')
@login_required
@role_required('staff')
def staff_inquiries():
    staff = get_staff_record()
    db = get_db()
    status_f = request.args.get('status','')
    q = """SELECT i.*, c.name as customer_name, c.phone as customer_phone,
               m.name||' '||v.model as vehicle,
               (SELECT COUNT(*) FROM InquiryMessage im WHERE im.inquiry_id=i.inquiry_id) as msg_count,
               (SELECT COUNT(*) FROM InquiryMessage im WHERE im.inquiry_id=i.inquiry_id AND im.sender_role='customer' AND im.is_read=0) as unread_count,
               (SELECT message FROM InquiryMessage im WHERE im.inquiry_id=i.inquiry_id ORDER BY sent_at DESC LIMIT 1) as last_msg
        FROM Inquiry i JOIN Customer c ON i.customer_id=c.customer_id
        JOIN Vehicle v ON i.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        WHERE i.branch=?"""
    params = [staff['branch']]
    if status_f: q += " AND i.status=?"; params.append(status_f)
    rows = db.execute(q+" ORDER BY i.inquiry_date DESC", params).fetchall()
    total_unread = db.execute("""SELECT COUNT(*) FROM InquiryMessage im
        JOIN Inquiry i ON im.inquiry_id=i.inquiry_id
        WHERE i.branch=? AND im.sender_role='customer' AND im.is_read=0""", (staff['branch'],)).fetchone()[0]
    db.close()
    return render_template('staff/inquiries.html', inquiries=rows, staff=staff,
                           status_filter=status_f, total_unread=total_unread)

@app.route('/staff/inquiries/<int:id>', methods=['GET','POST'])
@login_required
@role_required('staff')
def staff_inquiry_chat(id):
    staff = get_staff_record()
    db = get_db()
    inq = db.execute("""SELECT i.*, c.name as customer_name, c.phone as customer_phone,
               m.name||' '||v.model as vehicle, v.image_url
        FROM Inquiry i JOIN Customer c ON i.customer_id=c.customer_id
        JOIN Vehicle v ON i.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        WHERE i.inquiry_id=? AND i.branch=?""", (id, staff['branch'])).fetchone()
    if not inq:
        flash('Not found in your branch.', 'danger')
        return redirect(url_for('staff_inquiries'))
    if request.method == 'POST':
        action = request.form.get('action','send')
        if action == 'send':
            msg = request.form.get('message','').strip()
            if msg:
                db.execute("INSERT INTO InquiryMessage (inquiry_id,sender_role,sender_name,message,sent_at,is_read) VALUES (?,?,?,?,?,0)",
                           (id,'staff',staff['name'],msg,date.today().isoformat()+' '+__import__('datetime').datetime.now().strftime('%H:%M')))
                db.execute("UPDATE Inquiry SET staff_id=? WHERE inquiry_id=?", (staff['staff_id'], id))
                db.commit()
        elif action == 'close':
            db.execute("UPDATE Inquiry SET status='closed' WHERE inquiry_id=?", (id,))
            db.commit()
        db.close()
        return redirect(url_for('staff_inquiry_chat', id=id))
    db.execute("UPDATE InquiryMessage SET is_read=1 WHERE inquiry_id=? AND sender_role='customer'", (id,))
    db.commit()
    messages = db.execute("SELECT * FROM InquiryMessage WHERE inquiry_id=? ORDER BY sent_at", (id,)).fetchall()
    db.close()
    return render_template('staff/inquiry_chat.html', inquiry=inq, messages=messages, staff=staff)

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMER PORTAL
# ═══════════════════════════════════════════════════════════════════════════════

def get_customer_record():
    db = get_db()
    c = db.execute("SELECT * FROM Customer WHERE user_id=?", (session['user_id'],)).fetchone()
    db.close()
    return c

@app.route('/customer')
@login_required
@role_required('customer')
def customer_dashboard():
    cust = get_customer_record()
    if not cust:
        flash('Profile not found. Contact support.', 'danger')
        return redirect(url_for('logout'))
    db = get_db()
    my_inquiries = db.execute("""SELECT i.*,
               m.name||' '||v.model as vehicle,
               i.status, i.inquiry_date,
               ss.name as staff_name, ss.phone as staff_phone,
               (SELECT message FROM InquiryMessage WHERE inquiry_id=i.inquiry_id AND sender_role!='customer' ORDER BY sent_at DESC LIMIT 1) as last_response,
               (SELECT COUNT(*) FROM InquiryMessage WHERE inquiry_id=i.inquiry_id AND sender_role!='customer' AND is_read=0) as unread_count
        FROM Inquiry i JOIN Vehicle v ON i.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        LEFT JOIN Sales_Staff ss ON i.staff_id=ss.staff_id
        WHERE i.customer_id=? ORDER BY i.inquiry_date DESC LIMIT 5""", (cust['customer_id'],)).fetchall()
    my_purchases = db.execute("""SELECT s.*, m.name||' '||v.model as vehicle,
               v.year, v.image_url
        FROM Sales s JOIN Vehicle v ON s.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        WHERE s.customer_id=? ORDER BY s.sale_date DESC LIMIT 3""", (cust['customer_id'],)).fetchall()
    wishlist_count = db.execute("SELECT COUNT(*) FROM Wishlist WHERE customer_id=?", (cust['customer_id'],)).fetchone()[0]
    featured = db.execute("""SELECT v.*,m.name as manufacturer_name FROM Vehicle v
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        WHERE v.status='available' ORDER BY RANDOM() LIMIT 4""").fetchall()
    db.close()
    return render_template('customer/dashboard.html', cust=cust, my_inquiries=my_inquiries,
                           my_purchases=my_purchases, wishlist_count=wishlist_count, featured=featured)

@app.route('/customer/browse')
@login_required
@role_required('customer')
def customer_browse():
    db = get_db()
    cust = get_customer_record()
    search = request.args.get('search',''); fuel_f = request.args.get('fuel','')
    mfr_f = request.args.get('mfr',''); sort_f = request.args.get('sort','price_asc')
    q = """SELECT v.*, m.name as manufacturer_name FROM Vehicle v
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id WHERE v.status='available'"""
    params = []
    if search: q += " AND (v.model LIKE ? OR m.name LIKE ?)"; params += [f'%{search}%']*2
    if fuel_f: q += " AND v.fuel_type=?"; params.append(fuel_f)
    if mfr_f: q += " AND v.manufacturer_id=?"; params.append(mfr_f)
    sort_map = {'price_asc':'v.price ASC','price_desc':'v.price DESC','newest':'v.year DESC'}
    vehicles = db.execute(q+f" ORDER BY {sort_map.get(sort_f,'v.price ASC')}", params).fetchall()
    wishlist_ids = set()
    if cust:
        wl = db.execute("SELECT vehicle_id FROM Wishlist WHERE customer_id=?", (cust['customer_id'],)).fetchall()
        wishlist_ids = {r['vehicle_id'] for r in wl}
    manufacturers = db.execute("SELECT * FROM Manufacturer ORDER BY name").fetchall()
    db.close()
    return render_template('customer/browse.html', vehicles=vehicles, manufacturers=manufacturers,
                           wishlist_ids=wishlist_ids, search=search, fuel_filter=fuel_f,
                           mfr_filter=mfr_f, sort_filter=sort_f)

@app.route('/customer/vehicle/<int:id>')
@login_required
@role_required('customer')
def customer_vehicle_detail(id):
    db = get_db()
    cust = get_customer_record()
    veh = db.execute("""SELECT v.*, m.name as manufacturer_name, m.country, m.website
        FROM Vehicle v JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        WHERE v.vehicle_id=?""", (id,)).fetchone()
    if not veh:
        flash('Vehicle not found.', 'danger')
        return redirect(url_for('customer_browse'))
    in_wishlist = False
    if cust:
        in_wishlist = bool(db.execute("SELECT 1 FROM Wishlist WHERE customer_id=? AND vehicle_id=?",
                                      (cust['customer_id'], id)).fetchone())
    db.close()
    price = veh['price']
    emi_plans = []
    for months in [12, 24, 36, 48, 60, 84]:
        down = price * 0.10; loan = price - down; r = 8.5/100/12
        emi = loan * r * (1+r)**months / ((1+r)**months - 1)
        emi_plans.append({'months': months, 'emi': round(emi), 'down': round(down)})
    return render_template('customer/vehicle_detail.html', vehicle=veh,
                           emi_plans=emi_plans, in_wishlist=in_wishlist, cust=cust)

@app.route('/customer/wishlist')
@login_required
@role_required('customer')
def customer_wishlist():
    cust = get_customer_record()
    db = get_db()
    items = db.execute("""SELECT v.*, m.name as manufacturer_name, w.added_date
        FROM Wishlist w JOIN Vehicle v ON w.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        WHERE w.customer_id=? ORDER BY w.added_date DESC""", (cust['customer_id'],)).fetchall()
    db.close()
    return render_template('customer/wishlist.html', items=items, cust=cust)

@app.route('/customer/wishlist/toggle/<int:vid>', methods=['POST'])
@login_required
@role_required('customer')
def customer_toggle_wishlist(vid):
    cust = get_customer_record()
    db = get_db()
    exists = db.execute("SELECT 1 FROM Wishlist WHERE customer_id=? AND vehicle_id=?",
                        (cust['customer_id'], vid)).fetchone()
    if exists:
        db.execute("DELETE FROM Wishlist WHERE customer_id=? AND vehicle_id=?", (cust['customer_id'], vid))
        msg = 'Removed from wishlist.'
    else:
        db.execute("INSERT INTO Wishlist (customer_id,vehicle_id,added_date) VALUES (?,?,?)",
                   (cust['customer_id'], vid, date.today().isoformat()))
        msg = 'Added to wishlist!'
    db.commit(); db.close()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'removed' if exists else 'added', 'message': msg})
    flash(msg, 'success')
    return redirect(request.referrer or url_for('customer_browse'))

@app.route('/customer/inquiries')
@login_required
@role_required('customer')
def customer_inquiries():
    cust = get_customer_record()
    db = get_db()
    rows = db.execute("""SELECT i.*, m.name||' '||v.model as vehicle, v.image_url,
               (SELECT COUNT(*) FROM InquiryMessage im WHERE im.inquiry_id=i.inquiry_id) as msg_count,
               (SELECT COUNT(*) FROM InquiryMessage im WHERE im.inquiry_id=i.inquiry_id AND im.sender_role!='customer' AND im.is_read=0) as unread_count,
               (SELECT message FROM InquiryMessage im WHERE im.inquiry_id=i.inquiry_id ORDER BY sent_at DESC LIMIT 1) as last_msg,
               (SELECT sent_at FROM InquiryMessage im WHERE im.inquiry_id=i.inquiry_id ORDER BY sent_at DESC LIMIT 1) as last_msg_at
        FROM Inquiry i JOIN Vehicle v ON i.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        WHERE i.customer_id=? ORDER BY COALESCE(last_msg_at, i.inquiry_date) DESC""", (cust['customer_id'],)).fetchall()
    total_unread = sum(r['unread_count'] for r in rows)
    db.close()
    return render_template('customer/inquiries.html', inquiries=rows, cust=cust, total_unread=total_unread)

@app.route('/customer/inquiries/<int:id>', methods=['GET','POST'])
@login_required
@role_required('customer')
def customer_inquiry_chat(id):
    cust = get_customer_record()
    db = get_db()
    inq = db.execute("""SELECT i.*, m.name||' '||v.model as vehicle, v.image_url,
               ss.name as staff_name, ss.phone as staff_phone
        FROM Inquiry i JOIN Vehicle v ON i.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        LEFT JOIN Sales_Staff ss ON i.staff_id=ss.staff_id
        WHERE i.inquiry_id=? AND i.customer_id=?""", (id, cust['customer_id'])).fetchone()
    if not inq:
        flash('Inquiry not found.', 'danger')
        return redirect(url_for('customer_inquiries'))
    if request.method == 'POST':
        if inq['status'] == 'closed':
            flash('This inquiry is closed.', 'warning')
        else:
            msg = request.form.get('message','').strip()
            if msg:
                db.execute("INSERT INTO InquiryMessage (inquiry_id,sender_role,sender_name,message,sent_at,is_read) VALUES (?,?,?,?,?,0)",
                           (id,'customer',cust['name'],msg,date.today().isoformat()+' '+__import__('datetime').datetime.now().strftime('%H:%M')))
                db.commit()
        db.close()
        return redirect(url_for('customer_inquiry_chat', id=id))
    db.execute("UPDATE InquiryMessage SET is_read=1 WHERE inquiry_id=? AND sender_role!='customer'", (id,))
    db.commit()
    messages = db.execute("SELECT * FROM InquiryMessage WHERE inquiry_id=? ORDER BY sent_at", (id,)).fetchall()
    db.close()
    return render_template('customer/inquiry_chat.html', inquiry=inq, messages=messages, cust=cust)

@app.route('/customer/inquiries/add', methods=['GET','POST'])
@login_required
@role_required('customer')
def customer_add_inquiry():
    cust = get_customer_record()
    db = get_db()
    if request.method == 'POST':
        branch = request.form['branch']
        vid = request.form['vehicle_id']
        msg = request.form.get('message','').strip()
        db.execute("INSERT INTO Inquiry (customer_id,vehicle_id,branch,inquiry_date,status) VALUES (?,?,?,?,?)",
                   (cust['customer_id'],vid,branch,date.today().isoformat(),'open'))
        inq_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        if msg:
            db.execute("INSERT INTO InquiryMessage (inquiry_id,sender_role,sender_name,message,sent_at,is_read) VALUES (?,?,?,?,?,0)",
                       (inq_id,'customer',cust['name'],msg,date.today().isoformat()+' '+__import__('datetime').datetime.now().strftime('%H:%M')))
        db.commit(); db.close()
        flash(f'Inquiry sent to {branch}!', 'success')
        return redirect(url_for('customer_inquiry_chat', id=inq_id))
    vid = request.args.get('vehicle_id','')
    vehicles = db.execute("SELECT v.*,m.name as mfr FROM Vehicle v JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id WHERE v.status='available'").fetchall()
    db.close()
    return render_template('customer/inquiry_form.html', vehicles=vehicles, cust=cust,
                           preselect_vid=vid, branches=BRANCHES)

# ── Test Drive ─────────────────────────────────────────────────────────────────

@app.route('/customer/test-drive', methods=['GET','POST'])
@login_required
@role_required('customer')
def customer_test_drive():
    cust = get_customer_record()
    db = get_db()
    if request.method == 'POST':
        db.execute("""INSERT INTO TestDrive (customer_id,vehicle_id,branch,preferred_date,preferred_time,status,notes,booked_at)
                      VALUES (?,?,?,?,?,?,?,?)""",
                   (cust['customer_id'], request.form['vehicle_id'], request.form['branch'],
                    request.form['preferred_date'], request.form['preferred_time'],
                    'pending', request.form.get('notes',''), date.today().isoformat()))
        db.commit()
        flash('Test drive booked! The showroom will confirm your slot.', 'success')
        db.close()
        return redirect(url_for('customer_test_drive'))
    vehicles = db.execute("SELECT v.*,m.name as mfr FROM Vehicle v JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id WHERE v.status='available' ORDER BY m.name,v.model").fetchall()
    my_bookings = db.execute("""SELECT td.*, m.name||' '||v.model as vehicle
        FROM TestDrive td JOIN Vehicle v ON td.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        WHERE td.customer_id=? ORDER BY td.preferred_date DESC""", (cust['customer_id'],)).fetchall()
    # Check booked slots for selected branch/date (for availability display)
    sel_branch = request.args.get('branch','')
    sel_date = request.args.get('date','')
    booked_slots = []
    if sel_branch and sel_date:
        booked_slots = [r['preferred_time'] for r in db.execute(
            "SELECT preferred_time FROM TestDrive WHERE branch=? AND preferred_date=? AND status NOT IN ('cancelled')",
            (sel_branch, sel_date)).fetchall()]
    db.close()
    return render_template('customer/test_drive.html', vehicles=vehicles, cust=cust,
                           my_bookings=my_bookings, branches=BRANCHES,
                           booked_slots=booked_slots, sel_branch=sel_branch, sel_date=sel_date)

@app.route('/customer/test-drive/cancel/<int:id>', methods=['POST'])
@login_required
@role_required('customer')
def customer_cancel_test_drive(id):
    cust = get_customer_record()
    db = get_db()
    db.execute("UPDATE TestDrive SET status='cancelled' WHERE booking_id=? AND customer_id=?",
               (id, cust['customer_id']))
    db.commit(); db.close()
    flash('Test drive cancelled.', 'info')
    return redirect(url_for('customer_test_drive'))

# Staff test drive management
@app.route('/staff/test-drives')
@login_required
@role_required('staff')
def staff_test_drives():
    staff = get_staff_record()
    db = get_db()
    bookings = db.execute("""SELECT td.*, m.name||' '||v.model as vehicle,
               c.name as customer_name, c.phone as customer_phone
        FROM TestDrive td JOIN Vehicle v ON td.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        JOIN Customer c ON td.customer_id=c.customer_id
        WHERE td.branch=? ORDER BY td.preferred_date DESC, td.preferred_time""",
        (staff['branch'],)).fetchall()
    db.close()
    return render_template('staff/test_drives.html', bookings=bookings, staff=staff)

@app.route('/staff/test-drives/<int:id>/update', methods=['POST'])
@login_required
@role_required('staff')
def staff_update_test_drive(id):
    db = get_db()
    db.execute("UPDATE TestDrive SET status=? WHERE booking_id=?",
               (request.form['status'], id))
    db.commit(); db.close()
    flash('Booking updated.', 'success')
    return redirect(url_for('staff_test_drives'))

# Admin test drive overview
@app.route('/admin/test-drives')
@login_required
@role_required('admin')
def admin_test_drives():
    db = get_db()
    branch_f = request.args.get('branch','')
    q = """SELECT td.*, m.name||' '||v.model as vehicle,
               c.name as customer_name, c.phone as customer_phone
        FROM TestDrive td JOIN Vehicle v ON td.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        JOIN Customer c ON td.customer_id=c.customer_id WHERE 1=1"""
    params = []
    if branch_f: q += " AND td.branch=?"; params.append(branch_f)
    bookings = db.execute(q+" ORDER BY td.preferred_date DESC, td.preferred_time", params).fetchall()
    db.close()
    return render_template('admin/test_drives.html', bookings=bookings, branch_filter=branch_f, branches=BRANCHES)

# Notification API endpoints
@app.route('/api/notifications')
@login_required
def get_notifications():
    db = get_db()
    role = session['role']
    uid = session['user_id']
    data = {'inquiry_unread': 0, 'test_drive_pending': 0}
    if role == 'customer':
        cust = db.execute("SELECT customer_id FROM Customer WHERE user_id=?", (uid,)).fetchone()
        if cust:
            data['inquiry_unread'] = db.execute("""SELECT COUNT(*) FROM InquiryMessage im
                JOIN Inquiry i ON im.inquiry_id=i.inquiry_id
                WHERE i.customer_id=? AND im.sender_role!='customer' AND im.is_read=0""",
                (cust['customer_id'],)).fetchone()[0]
    elif role == 'staff':
        s = db.execute("SELECT * FROM Sales_Staff WHERE user_id=?", (uid,)).fetchone()
        if s:
            data['inquiry_unread'] = db.execute("""SELECT COUNT(*) FROM InquiryMessage im
                JOIN Inquiry i ON im.inquiry_id=i.inquiry_id
                WHERE i.branch=? AND im.sender_role='customer' AND im.is_read=0""",
                (s['branch'],)).fetchone()[0]
            data['test_drive_pending'] = db.execute(
                "SELECT COUNT(*) FROM TestDrive WHERE branch=? AND status='pending'",
                (s['branch'],)).fetchone()[0]
    elif role == 'admin':
        data['inquiry_unread'] = db.execute("""SELECT COUNT(*) FROM InquiryMessage
            WHERE sender_role='customer' AND is_read=0""").fetchone()[0]
        data['test_drive_pending'] = db.execute(
            "SELECT COUNT(*) FROM TestDrive WHERE status='pending'").fetchone()[0]
    db.close()
    return jsonify(data)

@app.route('/customer/purchases')
@login_required
@role_required('customer')
def customer_purchases():
    cust = get_customer_record()
    db = get_db()
    rows = db.execute("""SELECT s.*, m.name||' '||v.model as vehicle, v.year,
               v.image_url, v.color, v.fuel_type,
               ss.name as staff_name, ss.branch, ss.phone as staff_phone
        FROM Sales s JOIN Vehicle v ON s.vehicle_id=v.vehicle_id
        JOIN Manufacturer m ON v.manufacturer_id=m.manufacturer_id
        JOIN Sales_Staff ss ON s.staff_id=ss.staff_id
        WHERE s.customer_id=? ORDER BY s.sale_date DESC""", (cust['customer_id'],)).fetchall()
    db.close()
    return render_template('customer/purchases.html', purchases=rows, cust=cust)

@app.route('/customer/profile', methods=['GET','POST'])
@login_required
@role_required('customer')
def customer_profile():
    cust = get_customer_record()
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_profile':
            db.execute("UPDATE Customer SET name=?,phone=?,email=?,address=? WHERE customer_id=?",
                       (request.form['name'],request.form.get('phone',''),
                        request.form.get('email',''),request.form.get('address',''),cust['customer_id']))
            db.commit(); flash('Profile updated.', 'success')
        elif action == 'change_password':
            current = request.form.get('current_password','')
            new_p = request.form.get('new_password','')
            confirm = request.form.get('confirm_password','')
            user = db.execute("SELECT * FROM Users WHERE user_id=?", (session['user_id'],)).fetchone()
            if not check_password_hash(user['password'], current):
                flash('Current password is incorrect.', 'danger')
            elif new_p != confirm:
                flash('Passwords do not match.', 'danger')
            elif len(new_p) < 6:
                flash('Min 6 characters.', 'danger')
            else:
                db.execute("UPDATE Users SET password=? WHERE user_id=?",
                           (generate_password_hash(new_p), session['user_id']))
                db.commit(); flash('Password changed!', 'success')
        db.close()
        return redirect(url_for('customer_profile'))
    db.close()
    return render_template('customer/profile.html', cust=cust)

@app.route('/api/test-drive-slots')
@login_required
def test_drive_slots_api():
    branch = request.args.get('branch','')
    date = request.args.get('date','')
    if not branch or not date:
        return jsonify({'booked': []})
    db = get_db()
    booked = [r['preferred_time'] for r in db.execute(
        "SELECT preferred_time FROM TestDrive WHERE branch=? AND preferred_date=? AND status NOT IN ('cancelled')",
        (branch, date)).fetchall()]
    db.close()
    return jsonify({'booked': booked})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
    
