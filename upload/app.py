from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import os
import uuid

app = Flask(__name__)
app.secret_key = 'hHKJEIEIGJjhgkj13k3jkffdf&*jjkjdf'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///glh.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)




class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    loyalty_points = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(60), nullable=False)
    price = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(30), nullable=False)
    available = db.Column(db.Float, nullable=False, default=0)
    organic = db.Column(db.Boolean, default=False)
    harvest_date = db.Column(db.Date)
    image_url = db.Column(db.String(500), default='')
    image_filename = db.Column(db.String(255), default='')
    farm_name = db.Column(db.String(120), default='')
    location = db.Column(db.String(120), default='')
    description = db.Column(db.Text, default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    farmer = db.relationship('User', backref='products')

    def get_image(self):
        if self.image_filename:
            return '/static/uploads/' + self.image_filename
        if self.image_url:
            return self.image_url
        return ''

    def has_image(self):
        return bool(self.image_filename or self.image_url)

    def freshness(self):
        if not self.harvest_date:
            return None
        diff = (datetime.utcnow().date() - self.harvest_date).days
        if diff <= 0:
            return 'Harvested Today'
        elif diff <= 1:
            return 'Very Fresh'
        elif diff <= 3:
            return 'Fresh'
        return str(diff) + ' days ago'


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    total = db.Column(db.Float, nullable=False)
    scheduled_for = db.Column(db.Date)
    delivery_notes = db.Column(db.Text, default='')
    placed_on = db.Column(db.DateTime, default=datetime.utcnow)

    buyer = db.relationship('User', foreign_keys=[buyer_id])
    farmer_user = db.relationship('User', foreign_keys=[farmer_id])
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')

    def next_status(self):
        flow = ['pending', 'preparing', 'ready', 'dispatched', 'delivered']
        if self.status in flow:
            i = flow.index(self.status)
            if i < len(flow) - 1:
                return flow[i + 1]
        return None

    def next_action(self):
        labels = {
            'pending': 'Accept & Prepare',
            'preparing': 'Mark Ready',
            'ready': 'Dispatch',
            'dispatched': 'Mark Delivered',
        }
        return labels.get(self.status)






class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    product_name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)



class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)







def allowed_file(fn):
    return '.' in fn and fn.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def login_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return f(*a, **kw)
    return wrap


def farmer_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if session.get('role') != 'farmer':
            flash('Access denied.', 'danger')
            return redirect(url_for('index'))
        return f(*a, **kw)
    return wrap


def buyer_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if session.get('role') != 'buyer':
            flash('Access denied.', 'danger')
            return redirect(url_for('index'))
        return f(*a, **kw)
    return wrap


def get_user():
    if 'user_id' not in session:
        return None
    return db.session.get(User, session['user_id'])


def get_cart():
    return session.get('cart', [])


def save_cart(cart):
    session['cart'] = cart
    session.modified = True


@app.context_processor
def globals():
    user = get_user()
    cart = get_cart()
    cart_count = sum(i['qty'] for i in cart)
    unread = 0
    if user:
        unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return dict(user=user, cart_count=cart_count, unread_count=unread)




@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        pw = request.form.get('password', '')
        pw2 = request.form.get('password_confirm', '')
        role = request.form.get('role', 'buyer')

        if not name or not email:
            flash('Name and email are required.', 'danger')
            return redirect(url_for('register'))
        if len(pw) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return redirect(url_for('register'))
        if pw != pw2:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))
        if role not in ('buyer', 'farmer'):
            flash('Pick buyer or producer.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))

        u = User(full_name=name, email=email, role=role)
        u.set_password(pw)
        if role == 'buyer':
            u.loyalty_points = 50
        db.session.add(u)
        db.session.flush()

        msg = 'Welcome to GLH! '
        msg += 'You got 50 welcome points.' if role == 'buyer' else 'Start adding your products.'
        db.session.add(Notification(user_id=u.id, message=msg))
        db.session.commit()

        session['user_id'] = u.id
        session['role'] = u.role
        flash('Account created!', 'success')
        return redirect(url_for('dashboard') if role == 'farmer' else url_for('marketplace'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        pw = request.form.get('password', '')
        u = User.query.filter_by(email=email, is_active=True).first()
        if u and u.check_password(pw):
            session['user_id'] = u.id
            session['role'] = u.role
            flash('Welcome back, ' + u.full_name + '!', 'success')
            return redirect(url_for('dashboard') if u.role == 'farmer' else url_for('marketplace'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('index'))




@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')




@app.route('/marketplace')
def marketplace():
    q = request.args.get('q', '').strip()
    cat = request.args.get('category', '')
    loc = request.args.get('location', '')
    organic = request.args.get('organic') == '1'

    query = Product.query.filter_by(is_active=True)
    if q:
        query = query.filter(Product.name.ilike('%' + q + '%'))
    if cat:
        query = query.filter_by(category=cat)
    if loc:
        query = query.filter_by(location=loc)
    if organic:
        query = query.filter_by(organic=True)

    products = query.order_by(Product.created_at.desc()).all()

    cats = [r[0] for r in db.session.query(Product.category).filter(Product.is_active == True).distinct() if r[0]]
    locs = [r[0] for r in db.session.query(Product.location).filter(Product.is_active == True, Product.location != '').distinct() if r[0]]

    return render_template('marketplace.html', products=products,
                           categories=sorted(cats), locations=sorted(locs),
                           current_cat=cat, current_loc=loc,
                           current_q=q, organic_only=organic)


@app.route('/product/<int:id>')
def product_detail(id):
    p = Product.query.get_or_404(id)
    if not p.is_active:
        abort(404)
    related = Product.query.filter(Product.category == p.category, Product.id != p.id, Product.is_active == True).limit(4).all()
    return render_template('product_detail.html', product=p, related=related)




@app.route('/cart/add/<int:id>', methods=['POST'])
@login_required
@buyer_required
def cart_add(id):
    p = Product.query.get_or_404(id)
    qty = float(request.form.get('qty', 1))
    if qty <= 0:
        qty = 1
    cart = get_cart()
    for item in cart:
        if item['product_id'] == id:
            item['qty'] += qty
            save_cart(cart)
            flash('Updated ' + p.name + ' in basket.', 'success')
            return redirect(request.referrer or url_for('marketplace'))

    cart.append({
        'product_id': p.id,
        'name': p.name,
        'price': p.price,
        'unit': p.unit,
        'qty': qty,
        'farmer_id': p.farmer_id,
        'image': p.get_image()
    })
    save_cart(cart)
    flash(p.name + ' added to basket.', 'success')
    return redirect(request.referrer or url_for('marketplace'))


@app.route('/cart/update/<int:id>', methods=['POST'])
@login_required
@buyer_required
def cart_update(id):
    qty = float(request.form.get('qty', 0))
    cart = get_cart()
    if qty <= 0:
        cart = [i for i in cart if i['product_id'] != id]
    else:
        for item in cart:
            if item['product_id'] == id:
                item['qty'] = qty
    save_cart(cart)
    return redirect(url_for('cart_view'))


@app.route('/cart/remove/<int:id>', methods=['POST'])
@login_required
@buyer_required
def cart_remove(id):
    cart = [i for i in get_cart() if i['product_id'] != id]
    save_cart(cart)
    flash('Removed from basket.', 'info')
    return redirect(url_for('cart_view'))


@app.route('/cart')
@login_required
@buyer_required
def cart_view():
    cart = get_cart()
    total = sum(i['price'] * i['qty'] for i in cart)
    return render_template('cart.html', cart=cart, total=total)




@app.route('/checkout', methods=['GET', 'POST'])
@login_required
@buyer_required
def checkout():
    cart = get_cart()
    if not cart:
        flash('Basket is empty.', 'warning')
        return redirect(url_for('marketplace'))
    total = sum(i['price'] * i['qty'] for i in cart)

    if request.method == 'POST':
        sched = request.form.get('scheduled_for', '')
        notes = request.form.get('delivery_notes', '').strip()
        sched_date = None
        if sched:
            try:
                sched_date = datetime.strptime(sched, '%Y-%m-%d').date()
            except ValueError:
                pass

        u = get_user()
        # grouping them by farmers
        groups = {}
        for item in cart:
            groups.setdefault(item['farmer_id'], []).append(item)

        for fid, items in groups.items():
            t = sum(i['price'] * i['qty'] for i in items)
            o = Order(buyer_id=u.id, farmer_id=fid, total=t,
                      scheduled_for=sched_date, delivery_notes=notes)
            db.session.add(o)
            db.session.flush()
            for item in items:
                db.session.add(OrderItem(order_id=o.id, product_id=item['product_id'],
                                         product_name=item['name'], quantity=item['qty'],
                                         unit_price=item['price']))
                prod = db.session.get(Product, item['product_id'])
                if prod:
                    prod.available = max(0, prod.available - item['qty'])
            u.loyalty_points += int(t)
            db.session.add(Notification(user_id=fid,
                                        message='New order #' + str(o.id) + ' — £' + format(t, '.2f')))

        db.session.commit()
        save_cart([])
        flash('Order placed!', 'success')
        return redirect(url_for('my_orders'))

    return render_template('checkout.html', cart=cart, total=total)




@app.route('/my-orders')
@login_required
@buyer_required
def my_orders():
    u = get_user()
    orders = Order.query.filter_by(buyer_id=u.id).order_by(Order.placed_on.desc()).all()
    return render_template('my_orders.html', orders=orders)


@app.route('/order/<int:id>')
@login_required
def order_detail(id):
    o = Order.query.get_or_404(id)
    u = get_user()
    if o.buyer_id != u.id and o.farmer_id != u.id:
        abort(403)
    return render_template('order_detail.html', order=o)


@app.route('/order/<int:id>/cancel', methods=['POST'])
@login_required
@buyer_required
def cancel_order(id):
    o = Order.query.get_or_404(id)
    u = get_user()
    if o.buyer_id != u.id:
        abort(403)
    if o.status != 'pending':
        flash('Only pending orders can be cancelled.', 'warning')
        return redirect(url_for('order_detail', id=o.id))
    o.status = 'cancelled'
    for item in o.items:
        prod = db.session.get(Product, item.product_id)
        if prod:
            prod.available += item.quantity
    db.session.add(Notification(user_id=o.farmer_id, message='Order #' + str(o.id) + ' cancelled.'))
    db.session.commit()
    flash('Order cancelled.', 'info')
    return redirect(url_for('my_orders'))



@app.route('/dashboard')
@login_required
@farmer_required
def dashboard():
    u = get_user()
    total_sales = db.session.query(db.func.sum(Order.total)).filter(
        Order.farmer_id == u.id, Order.status != 'cancelled').scalar() or 0
    active = Product.query.filter_by(farmer_id=u.id, is_active=True).count()
    pending = Order.query.filter_by(farmer_id=u.id, status='pending').count()
    orders = Order.query.filter_by(farmer_id=u.id).order_by(Order.placed_on.desc()).all()
    return render_template('dashboard.html', total_sales=total_sales,
                           active_listings=active, pending_count=pending, orders=orders)


@app.route('/order/<int:id>/advance', methods=['POST'])
@login_required
@farmer_required
def advance_order(id):
    o = Order.query.get_or_404(id)
    u = get_user()
    if o.farmer_id != u.id:
        abort(403)
    nxt = o.next_status()
    if nxt:
        o.status = nxt
        db.session.add(Notification(user_id=o.buyer_id,
                                    message='Order #' + str(o.id) + ' is now ' + nxt.upper() + '.'))
        db.session.commit()
        flash('Order #' + str(o.id) + ' → ' + nxt.upper(), 'success')
    return redirect(url_for('dashboard'))




@app.route('/my-products')
@login_required
@farmer_required
def manage_products():
    u = get_user()
    products = Product.query.filter_by(farmer_id=u.id).order_by(Product.created_at.desc()).all()
    return render_template('manage_products.html', products=products)


@app.route('/product/add', methods=['GET', 'POST'])
@login_required
@farmer_required
def add_product():
    if request.method == 'POST':
        u = get_user()
        name = request.form.get('name', '').strip()
        price_str = request.form.get('price', '0')
        try:
            price = float(price_str)
        except ValueError:
            price = 0

        if not name or price <= 0:
            flash('Name and valid price required.', 'danger')
            return redirect(url_for('add_product'))

        category = request.form.get('category', 'Vegetables')
        unit = request.form.get('unit', 'kg')
        try:
            available = float(request.form.get('available', '0'))
        except ValueError:
            available = 0
        organic = request.form.get('organic') == '1'
        farm_name = request.form.get('farm_name', '').strip()
        location = request.form.get('location', '').strip()
        description = request.form.get('description', '').strip()
        image_url = request.form.get('image_url', '').strip()

        hd = None
        hd_str = request.form.get('harvest_date', '')
        if hd_str:
            try:
                hd = datetime.strptime(hd_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        image_filename = ''
        file = request.files.get('image_file')
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            image_filename = uuid.uuid4().hex + '.' + ext
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
            image_url = ''

        p = Product(farmer_id=u.id, name=name, category=category, price=price,
                    unit=unit, available=available, organic=organic, harvest_date=hd,
                    image_url=image_url, image_filename=image_filename,
                    farm_name=farm_name, location=location, description=description)
        db.session.add(p)
        db.session.commit()
        flash(name + ' added!', 'success')
        return redirect(url_for('manage_products'))

    return render_template('product_form.html', product=None, editing=False)


@app.route('/product/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@farmer_required
def edit_product(id):
    p = Product.query.get_or_404(id)
    u = get_user()
    if p.farmer_id != u.id:
        abort(403)

    if request.method == 'POST':
        p.name = request.form.get('name', p.name).strip()
        p.category = request.form.get('category', p.category)
        try:
            p.price = float(request.form.get('price', p.price))
        except ValueError:
            pass
        p.unit = request.form.get('unit', p.unit)
        try:
            p.available = float(request.form.get('available', p.available))
        except ValueError:
            pass
        p.organic = request.form.get('organic') == '1'
        p.farm_name = request.form.get('farm_name', '').strip()
        p.location = request.form.get('location', '').strip()
        p.description = request.form.get('description', '').strip()

        hd_str = request.form.get('harvest_date', '')
        if hd_str:
            try:
                p.harvest_date = datetime.strptime(hd_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        new_url = request.form.get('image_url', '').strip()
        file = request.files.get('image_file')
        if file and file.filename and allowed_file(file.filename):
            # delete old upload
            if p.image_filename:
                old = os.path.join(app.config['UPLOAD_FOLDER'], p.image_filename)
                if os.path.exists(old):
                    os.remove(old)
            ext = file.filename.rsplit('.', 1)[1].lower()
            p.image_filename = uuid.uuid4().hex + '.' + ext
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], p.image_filename))
            p.image_url = ''
        elif new_url:
            if p.image_filename:
                old = os.path.join(app.config['UPLOAD_FOLDER'], p.image_filename)
                if os.path.exists(old):
                    os.remove(old)
                p.image_filename = ''
            p.image_url = new_url

        db.session.commit()
        flash(p.name + ' updated.', 'success')
        return redirect(url_for('manage_products'))

    return render_template('product_form.html', product=p, editing=True)


@app.route('/product/delete/<int:id>', methods=['POST'])
@login_required
@farmer_required
def delete_product(id):
    p = Product.query.get_or_404(id)
    u = get_user()
    if p.farmer_id != u.id:
        abort(403)
    p.is_active = False
    db.session.commit()
    flash(p.name + ' removed.', 'info')
    return redirect(url_for('manage_products'))


# ════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ════════════════════════════════════════════════════════════

@app.route('/notifications')
@login_required
def notifications():
    u = get_user()
    notifs = Notification.query.filter_by(user_id=u.id).order_by(Notification.created_at.desc()).all()
    Notification.query.filter_by(user_id=u.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('notifications.html', notifications=notifs)




@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    u = get_user()
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            u.full_name = request.form.get('full_name', u.full_name).strip()
            new_email = request.form.get('email', u.email).strip().lower()
            if new_email != u.email:
                if User.query.filter_by(email=new_email).first():
                    flash('Email already in use.', 'danger')
                    return redirect(url_for('account'))
                u.email = new_email
            db.session.commit()
            flash('Profile updated.', 'success')

        elif action == 'change_password':
            cur = request.form.get('current_password', '')
            new = request.form.get('new_password', '')
            new2 = request.form.get('new_password_confirm', '')
            if not u.check_password(cur):
                flash('Current password is wrong.', 'danger')
            elif len(new) < 6:
                flash('Min 6 characters.', 'danger')
            elif new != new2:
                flash('Passwords do not match.', 'danger')
            else:
                u.set_password(new)
                db.session.commit()
                flash('Password changed.', 'success')

        elif action == 'delete_account':
            if request.form.get('confirm_delete') == 'DELETE':
                u.is_active = False
                db.session.commit()
                session.clear()
                flash('Account deleted.', 'info')
                return redirect(url_for('index'))
            flash('Type DELETE to confirm.', 'danger')

        return redirect(url_for('account'))

    return render_template('account.html')




@app.errorhandler(403)
def err403(e):
    return render_template('error.html', code=403, msg='Access denied.'), 403

@app.errorhandler(404)
def err404(e):
    return render_template('error.html', code=404, msg='Page not found.'), 404


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)