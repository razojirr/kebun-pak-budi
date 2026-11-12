from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "ganti-dengan-secret-key-anda"
DB = "kebun.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        nama_petani TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        keterangan TEXT NOT NULL,
        jumlah REAL NOT NULL,
        via_utang INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS harvests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        tanaman TEXT NOT NULL,
        total_kg REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        volume_kg REAL NOT NULL,
        harga_per_kg REAL NOT NULL,
        tunai INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users(username,password,nama_petani) VALUES(?,?,?)",
            ("budi", generate_password_hash("budi123"), "Pak Budi")
        )
    conn.commit()
    conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["nama_petani"] = user["nama_petani"]
            return redirect(url_for("dashboard"))
        flash("Username atau password salah.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def index():
    return redirect(url_for("dashboard" if "user_id" in session else "login"))

@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    conn = get_db()
    expenses = conn.execute("SELECT * FROM expenses WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
    harvest = conn.execute("SELECT * FROM harvests WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
    sales = conn.execute("SELECT * FROM sales WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
    conn.close()

    total_modal = sum(x["jumlah"] for x in expenses)
    total_utang = sum(x["jumlah"] for x in expenses if x["via_utang"])
    panen = harvest["total_kg"] if harvest else 0
    pendapatan = sales["volume_kg"] * sales["harga_per_kg"] if sales else 0
    hpp = total_modal / panen if panen > 0 else 0
    rekomendasi = hpp + 3000 if panen > 0 else 0
    laba = pendapatan - total_modal

    return render_template("dashboard.html",
        nama=session["nama_petani"], expenses=expenses, harvest=harvest, sales=sales,
        total_modal=total_modal, total_utang=total_utang, panen=panen,
        pendapatan=pendapatan, hpp=hpp, rekomendasi=rekomendasi, laba=laba)

@app.post("/expense")
@login_required
def expense():
    keterangan = request.form["keterangan"].strip()
    jumlah = float(request.form["jumlah"])
    via_utang = 1 if "via_utang" in request.form else 0
    conn = get_db()
    conn.execute("INSERT INTO expenses(user_id,keterangan,jumlah,via_utang) VALUES(?,?,?,?)",
                 (session["user_id"], keterangan, jumlah, via_utang))
    conn.commit(); conn.close()
    flash("Pengeluaran berhasil disimpan.", "success")
    return redirect(url_for("dashboard"))

@app.post("/harvest")
@login_required
def harvest():
    tanaman = request.form["tanaman"].strip()
    kg = float(request.form["total_kg"])
    conn = get_db()
    conn.execute("INSERT INTO harvests(user_id,tanaman,total_kg) VALUES(?,?,?)",
                 (session["user_id"], tanaman, kg))
    conn.commit(); conn.close()
    flash("Data panen berhasil disimpan.", "success")
    return redirect(url_for("dashboard"))

@app.post("/sale")
@login_required
def sale():
    volume = float(request.form["volume_kg"])
    harga = float(request.form["harga_per_kg"])
    tunai = 1 if "tunai" in request.form else 0
    conn = get_db()
    conn.execute("INSERT INTO sales(user_id,volume_kg,harga_per_kg,tunai) VALUES(?,?,?,?)",
                 (session["user_id"], volume, harga, tunai))
    conn.commit(); conn.close()
    flash("Data penjualan berhasil disimpan.", "success")
    return redirect(url_for("dashboard"))

@app.post("/clear")
@login_required
def clear():
    uid = session["user_id"]
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM harvests WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM sales WHERE user_id=?", (uid,))
    conn.commit(); conn.close()
    flash("Data transaksi berhasil dihapus.", "success")
    return redirect(url_for("dashboard"))

init_db()

if __name__ == "__main__":
    app.run(debug=True)
