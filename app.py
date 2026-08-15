from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'njiamauzo_secret_key_2026'

# Usanidi wa Hifadhidata ya SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///njiamauzo_web.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

SUPPORT_PHONE = "+255755248789"

# 1. Modeli ya Kategoria
class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)

# 2. Modeli ya Bidhaa / Matangazo
class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    stock_quantity = db.Column(db.Integer, default=1)
    location = db.Column(db.String(100), nullable=False)
    seller_phone = db.Column(db.String(20), default=SUPPORT_PHONE, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('Category', backref=db.backref('products', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'price': self.price,
            'location': self.location,
            'seller_phone': self.seller_phone,
            'category': self.category.name if self.category else 'Jumla'
        }

# 3. Modeli ya Bei za Masoko
class MarketPrice(db.Model):
    __tablename__ = 'market_prices'
    id = db.Column(db.Integer, primary_key=True)
    commodity = db.Column(db.String(100), nullable=False)
    market_name = db.Column(db.String(100), nullable=False)
    average_price = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), default='Kg')
    date = db.Column(db.Date, default=datetime.utcnow().date)

# Kuunda hifadhidata na kuweka data za awali
with app.app_context():
    db.create_all()
    if not Category.query.first():
        default_cats = [
            Category(name="Mazao ya Kilimo", description="Nafaka, mboga mboga na matunda"),
            Category(name="Bidhaa za Mifugo", description="Nyama, maziwa, na mayai"),
            Category(name="Pembejeo na Vifaa", description="Zana za shamba na mbolea")
        ]
        db.session.add_all(default_cats)
        db.session.commit()


# --- WEB ROUTES ---

@app.route('/')
def index():
    selected_category = request.args.get('category')
    search_query = request.args.get('q')

    products_query = Product.query
    
    if selected_category:
        products_query = products_query.join(Category).filter(Category.name == selected_category)
    
    if search_query:
        products_query = products_query.filter(Product.title.ilike(f"%{search_query}%"))

    products = products_query.order_by(Product.created_at.desc()).all()
    categories = Category.query.all()
    market_prices = MarketPrice.query.order_by(MarketPrice.date.desc()).limit(10).all()

    return render_template(
        'index.html', 
        products=products, 
        categories=categories, 
        market_prices=market_prices,
        support_phone=SUPPORT_PHONE
    )

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product, support_phone=SUPPORT_PHONE)

@app.route('/add-product', methods=['GET', 'POST'])
def add_product_web():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        price = request.form.get('price')
        stock = request.form.get('stock_quantity', 1)
        location = request.form.get('location')
        seller_phone = request.form.get('seller_phone', SUPPORT_PHONE)
        category_id = request.form.get('category_id')

        if not title or not price or not location or not category_id:
            flash('Tafadhali jaza sehemu zote muhimu!', 'danger')
            return redirect(url_for('add_product_web'))

        new_prod = Product(
            title=title,
            description=description,
            price=float(price),
            stock_quantity=int(stock),
            location=location,
            seller_phone=seller_phone,
            category_id=int(category_id)
        )
        db.session.add(new_prod)
        db.session.commit()
        
        flash('Tangazo lako limefanikiwa kuwekwa!', 'success')
        return redirect(url_for('index'))

    categories = Category.query.all()
    return render_template('add_product.html', categories=categories, support_phone=SUPPORT_PHONE)


# --- LIVE SEARCH API (Inafanya kazi Automatically kupitia JavaScript) ---
@app.route('/api/search', methods=['GET'])
def api_search():
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    
    prod_query = Product.query
    if query:
        prod_query = prod_query.filter(Product.title.ilike(f"%{query}%"))
    if category:
        prod_query = prod_query.join(Category).filter(Category.name == category)
        
    results = prod_query.all()
    return jsonify([p.to_dict() for p in results])


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
