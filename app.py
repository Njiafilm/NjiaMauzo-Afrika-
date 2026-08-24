import os, sqlite3, secrets
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

BASE=os.path.dirname(os.path.abspath(__file__)); DB=os.path.join(BASE,'njiamauzo.db')
app=Flask(__name__,template_folder=BASE); app.secret_key=os.environ.get('SECRET_KEY','CHANGE_THIS_SECRET_KEY'); CORS(app,supports_credentials=True)

def con():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def now(): return datetime.utcnow().isoformat(timespec='seconds')
def cid():
 if 'cid' not in session: session['cid']=secrets.token_urlsafe(18)
 return session['cid']
def init():
 c=con(); c.executescript('''
 CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,title TEXT NOT NULL,description TEXT,country TEXT,price REAL DEFAULT 0,currency TEXT DEFAULT 'TZS',image_url TEXT,seller_name TEXT,seller_contact TEXT,seller_url TEXT,source_url TEXT,is_factory INTEGER DEFAULT 0,active INTEGER DEFAULT 1,created_at TEXT);
 CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY,customer_id TEXT,product_id INTEGER,amount REAL,currency TEXT,provider TEXT,status TEXT DEFAULT 'pending',provider_ref TEXT,created_at TEXT,verified_at TEXT,UNIQUE(customer_id,product_id));
 CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password_hash TEXT,display_name TEXT,role TEXT,active INTEGER DEFAULT 1,created_at TEXT);
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,admin_id INTEGER,action TEXT,target TEXT,created_at TEXT);
 CREATE TABLE IF NOT EXISTS markets(id INTEGER PRIMARY KEY,company TEXT,country TEXT,website TEXT,contact_url TEXT,message TEXT,active INTEGER DEFAULT 1,created_at TEXT);
 CREATE TABLE IF NOT EXISTS reels(id INTEGER PRIMARY KEY,title TEXT,video_url TEXT,created_at TEXT);
 CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY,customer_id TEXT,sender TEXT,message TEXT,location TEXT,handled INTEGER DEFAULT 0,created_at TEXT);
 ''')
 for u,p,n,r in [('director','NjiaMauzoDirector2026!','Mkurugenzi Mkuu','director'),('accountant','NjiaMauzoMhasibu2026!','Mhasibu','accountant')]:
  if not c.execute('SELECT id FROM admins WHERE username=?',(u,)).fetchone(): c.execute('INSERT INTO admins(username,password_hash,display_name,role,created_at) VALUES(?,?,?,?,?)',(u,generate_password_hash(p),n,r,now()))
 if c.execute('SELECT COUNT(*) n FROM products').fetchone()['n']==0:
  ps=[('boAt 65W GaN Nano Charger','Chaja ya haraka.','India',0,0),('Anker Power Bank','Power bank ya safari.','China',0,0),('Smart Factory Computer','Kompyuta ya kiwandani.','China',0,1),('Siemens Industrial Controller','Bidhaa ya kiwandani.','China',0,1)]
  for t,d,co,pr,f in ps:c.execute('INSERT INTO products(title,description,country,price,is_factory,created_at) VALUES(?,?,?,?,?,?)',(t,d,co,pr,f,now()))
 c.commit(); c.close()

def admin(roles=None):
 def deco(fn):
  @wraps(fn)
  def w(*a,**kw):
   c=con(); x=c.execute('SELECT * FROM admins WHERE id=? AND active=1',(session.get('admin_id'),)).fetchone(); c.close()
   if not x:return jsonify(ok=False,error='Admin login required'),401
   if roles and x['role'] not in roles:return jsonify(ok=False,error='Huna ruhusa ya sehemu hii'),403
   return fn(x,*a,**kw)
  return w
 return deco

@app.route('/')
def home():return render_template('index.html')
@app.route('/admin')
def admin_page():return render_template('admin.html')
@app.post('/api/admin/login')
def login():
 d=request.get_json() or {}; c=con(); x=c.execute('SELECT * FROM admins WHERE username=? AND active=1',(str(d.get('username','')).strip(),)).fetchone()
 if not x or not check_password_hash(x['password_hash'],str(d.get('password',''))):c.close();return jsonify(ok=False,error='Username au password si sahihi'),401
 session['admin_id']=x['id']; c.execute('INSERT INTO audit(admin_id,action,target,created_at) VALUES(?,?,?,?)',(x['id'],'LOGIN',x['username'],now()));c.commit();c.close();return jsonify(ok=True,admin=dict(x))
@app.post('/api/admin/logout')
def logout():session.pop('admin_id',None);return jsonify(ok=True)
@app.get('/api/admin/me')
@admin()
def me(x):return jsonify(ok=True,admin=dict(x))
@app.get('/api/admin/dashboard')
@admin()
def dashboard(x):
 c=con(); d={
 'products':c.execute('SELECT COUNT(*) n FROM products WHERE active=1').fetchone()['n'],
 'factory_products':c.execute('SELECT COUNT(*) n FROM products WHERE active=1 AND is_factory=1').fetchone()['n'],
 'pending_payments':c.execute("SELECT COUNT(*) n FROM purchases WHERE status='pending'").fetchone()['n'],
 'verified_payments':c.execute("SELECT COUNT(*) n FROM purchases WHERE status='verified'").fetchone()['n'],
 'admins':c.execute('SELECT COUNT(*) n FROM admins WHERE active=1').fetchone()['n'],
 'unread_chat':c.execute("SELECT COUNT(*) n FROM chats WHERE handled=0 AND sender='customer'").fetchone()['n']};c.close();return jsonify(ok=True,dashboard=d)
@app.get('/api/products')
def products():
 c=con();r=c.execute('SELECT * FROM products WHERE active=1 ORDER BY id DESC').fetchall();c.close();return jsonify(ok=True,products=[dict(x) for x in r])
@app.get('/api/products/<int:pid>')
def product(pid):
 c=con();p=c.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone();paid=bool(c.execute("SELECT 1 FROM purchases WHERE customer_id=? AND product_id=? AND status='verified'",(cid(),pid)).fetchone());c.close()
 if not p:return jsonify(ok=False,error='Bidhaa haipo'),404
 d=dict(p)
 if not paid:d.update(price=None,seller_contact='',seller_url='',source_url='',locked=True)
 else:d['locked']=False
 return jsonify(ok=True,product=d,paid=paid)
@app.post('/api/payments/create')
def payment():
 d=request.get_json() or {};pid=int(d.get('product_id',0));c=con();p=c.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone()
 if not p:c.close();return jsonify(ok=False,error='Bidhaa haipo'),404
 old=c.execute('SELECT * FROM purchases WHERE customer_id=? AND product_id=?',(cid(),pid)).fetchone()
 if old:c.close();return jsonify(ok=True,purchase=dict(old))
 cur=c.execute('INSERT INTO purchases(customer_id,product_id,amount,currency,provider,status,created_at) VALUES(?,?,?,?,?,?,?)',(cid(),pid,float(p['price'] or 0),p['currency'],str(d.get('provider','MANUAL')), 'pending',now()));c.commit();r=c.execute('SELECT * FROM purchases WHERE id=?',(cur.lastrowid,)).fetchone();c.close();return jsonify(ok=True,purchase=dict(r),message='Malipo yameanzishwa; access itafunguliwa baada ya uthibitisho wa server.')
@app.get('/api/admin/payments')
@admin(['director','accountant'])
def payments(x):
 c=con();r=c.execute('SELECT p.*,pr.title FROM purchases p JOIN products pr ON pr.id=p.product_id ORDER BY p.id DESC').fetchall();c.close();return jsonify(ok=True,payments=[dict(z) for z in r])
@app.post('/api/payments/<int:pid>/verify')
@admin(['director','accountant'])
def verify(x,pid):
 d=request.get_json() or {};c=con();p=c.execute('SELECT id FROM purchases WHERE id=?',(pid,)).fetchone()
 if not p:c.close();return jsonify(ok=False,error='Payment haipo'),404
 c.execute("UPDATE purchases SET status='verified',provider_ref=?,verified_at=? WHERE id=?",(str(d.get('provider_ref','')),now(),pid));c.execute('INSERT INTO audit(admin_id,action,target,created_at) VALUES(?,?,?,?)',(x['id'],'VERIFY_PAYMENT',str(pid),now()));c.commit();c.close();return jsonify(ok=True,message='Malipo yamethibitishwa; bidhaa hii pekee imefunguliwa.')
@app.get('/api/markets')
def markets():
 c=con();r=c.execute('SELECT * FROM markets WHERE active=1 ORDER BY id DESC').fetchall();c.close();return jsonify(ok=True,markets=[dict(z) for z in r])
@app.post('/api/admin/markets')
@admin(['director','accountant','admin','marketing'])
def add_market(x):
 d=request.get_json() or {};c=con();cur=c.execute('INSERT INTO markets(company,country,website,contact_url,message,created_at) VALUES(?,?,?,?,?,?)',(d.get('company',''),d.get('country','East Africa'),d.get('website',''),d.get('contact_url',''),d.get('message',''),now()));c.commit();c.close();return jsonify(ok=True,id=cur.lastrowid)
@app.post('/api/admin/products')
@admin()
def add_product(x):
 d=request.get_json() or {};c=con();cur=c.execute('''INSERT INTO products(title,description,country,price,currency,image_url,seller_name,seller_contact,seller_url,source_url,is_factory,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(d.get('title',''),d.get('description',''),d.get('country','Tanzania'),float(d.get('price') or 0),d.get('currency','TZS'),d.get('image_url',''),d.get('seller_name',''),d.get('seller_contact',''),d.get('seller_url',''),d.get('source_url',''),1 if d.get('is_factory') else 0,now()));c.commit();c.close();return jsonify(ok=True,id=cur.lastrowid)
@app.get('/api/activity-feed')
def feed():
 c=con();r=c.execute("SELECT title,country,created_at FROM products WHERE active=1 AND is_factory=1 ORDER BY id DESC LIMIT 12").fetchall();c.close();return jsonify(ok=True,items=[dict(z) for z in r])
@app.get('/api/reels')
def reels():
 c=con();r=c.execute('SELECT * FROM reels ORDER BY id DESC').fetchall();c.close();return jsonify(ok=True,reels=[dict(z) for z in r])
@app.post('/api/admin/reels')
@admin()
def add_reel(x):
 d=request.get_json() or {};c=con();cur=c.execute('INSERT INTO reels(title,video_url,created_at) VALUES(?,?,?)',(d.get('title',''),d.get('video_url',''),now()));c.commit();c.close();return jsonify(ok=True,id=cur.lastrowid)
@app.post('/api/chat')
def chat():
 d=request.get_json() or {};m=str(d.get('message','')).strip();loc=str(d.get('location','')).strip();
 if not m:return jsonify(ok=False,error='Andika changamoto yako'),400
 c=con();c.execute('INSERT INTO chats(customer_id,sender,message,location,created_at) VALUES(?,?,?,?,?)',(cid(),'customer',m,loc,now()));reply='SASA TUNAEZA KUKUSAIDIA WAHUDUMU WETU WAKO TAYARI, KARIBU.' if c.execute('SELECT 1 FROM admins WHERE active=1').fetchone() else 'SAMAHANI SANA NDUGU MTEJA, WAHUDUMU WANAHUDUMIA WENGINE TAFADHALI ENDELEA KUSUBILI AU JARIBU TENA BAADAYE.';c.execute('INSERT INTO chats(customer_id,sender,message,location,created_at) VALUES(?,?,?,?,?)',(cid(),'bot',reply,loc,now()));c.commit();c.close();return jsonify(ok=True,reply=reply)
@app.get('/api/admin/chats')
@admin()
def chat_list(x):
 c=con();r=c.execute("SELECT customer_id,MAX(created_at) last_message,SUM(CASE WHEN sender='customer' AND handled=0 THEN 1 ELSE 0 END) unread FROM chats GROUP BY customer_id ORDER BY last_message DESC").fetchall();c.close();return jsonify(ok=True,chats=[dict(z) for z in r])
@app.get('/api/chat/<customer>')
@admin()
def chat_room(x,customer):
 c=con();r=c.execute('SELECT * FROM chats WHERE customer_id=? ORDER BY id',(customer,)).fetchall();c.close();return jsonify(ok=True,messages=[dict(z) for z in r])
@app.post('/api/admin/chats/<customer>/reply')
@admin()
def chat_reply(x,customer):
 d=request.get_json() or {};m=str(d.get('message','')).strip();c=con();c.execute('INSERT INTO chats(customer_id,sender,message,created_at,handled) VALUES(?,?,?,?,1)',(customer,'admin:'+x['display_name'],m,now()));c.execute("UPDATE chats SET handled=1 WHERE customer_id=?",(customer,));c.commit();c.close();return jsonify(ok=True)
@app.get('/api/admin/accounts')
@admin(['director'])
def accounts(x):
 c=con();r=c.execute('SELECT id,username,display_name,role,active,created_at FROM admins ORDER BY id').fetchall();c.close();return jsonify(ok=True,admins=[dict(z) for z in r])
@app.post('/api/admin/accounts')
@admin(['director'])
def create_account(x):
 d=request.get_json() or {};c=con();n=c.execute('SELECT COUNT(*) n FROM admins').fetchone()['n']
 if n>=15:c.close();return jsonify(ok=False,error='Kikomo cha accounts 15 kimefikiwa'),400
 try:
  cur=c.execute('INSERT INTO admins(username,password_hash,display_name,role,created_at) VALUES(?,?,?,?,?)',(d.get('username',''),generate_password_hash(d.get('password','')),d.get('display_name',''),d.get('role','admin'),now()));c.commit()
 except sqlite3.IntegrityError:c.close();return jsonify(ok=False,error='Username tayari ipo'),409
 c.close();return jsonify(ok=True,id=cur.lastrowid)
@app.get('/api/admin/audit')
@admin(['director','accountant'])
def audit(x):
 c=con();r=c.execute('SELECT a.*,ad.username,ad.display_name FROM audit a LEFT JOIN admins ad ON ad.id=a.admin_id ORDER BY a.id DESC LIMIT 300').fetchall();c.close();return jsonify(ok=True,logs=[dict(z) for z in r])
@app.get('/health')
def health():return jsonify(ok=True,service='NjiaMauzo Afrika')

init()
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False)
