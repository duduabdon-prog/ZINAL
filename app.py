import os
import random
import time
import calendar
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import pytz  # <-- ADICIONADO

from models import db, User, ClickLog

# carregar .env
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "dev-fallback-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///zinal.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
with app.app_context():
    db.create_all()

# timezone America/Sao_Paulo para conversão
tz_sp = pytz.timezone("America/Sao_Paulo")

# ---------- Helpers ----------
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return User.query.get(uid)

def ms_now():
    return int(time.time() * 1000)

def to_ms(dt):
    """Converte datetime para epoch ms de forma correta assumindo UTC se for 'naive'."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return int(calendar.timegm(dt.timetuple()) * 1000 + dt.microsecond // 1000)
    else:
        return int(dt.timestamp() * 1000)


# ---------------- Public pages ----------------
@app.route("/", methods=["GET"])
def landing():
    return render_template("landing.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        if not identifier or not password:
            error = "Preencha usuário/email e senha."
            return render_template("login.html", error=error)

        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
        if user and check_password_hash(user.password, password):
            if not user.is_access_valid():
                error = "Acesso expirado."
                return render_template("login.html", error=error)
            session["user_id"] = user.id
            # >>> CORREÇÃO: força is_admin como True/False
            is_admin_flag = True if user.is_admin in (1, True) else False
            session["is_admin"] = is_admin_flag
            return redirect(url_for("admin") if is_admin_flag else url_for("dashboard"))
        error = "Credenciais inválidas!"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


# ---------------- Dashboard (user) ----------------
@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("dashboard.html", username=user.username)


# API: start analysis (server-authoritative block using session)
@app.route("/api/start-analysis", methods=["POST"])
def api_start_analysis():
    user = current_user()
    if not user:
        return jsonify({"error": "not_authenticated"}), 401

    if user.access_expires_at and user.access_expires_at < datetime.utcnow():
        return jsonify({"error": "expired"}), 403

    now_ms = ms_now()
    block_ms = 7 * 60 * 1000
    last_ms = session.get("analysis_started_at_ms")

    if last_ms and (last_ms + block_ms) > now_ms:
        return jsonify({"error": "blocked", "blocked_until": last_ms + block_ms}), 429

    session["analysis_started_at_ms"] = now_ms

    ativos = [
        "Google (OTC)", "Apple (OTC)", "Tesla (OTC)", "Bitcoin (OTC)",
        "AUD-JPY (OTC)", "USD-JPY (OTC)", "USD-BRL (OTC)", "GBP-JPY (OTC)",
        "EUR-USD (OTC)", "AUD-CAD (OTC)", "GBP-USD (OTC)", "EUR-GBP (OTC)",
        "EUR-JPY (OTC)"
    ]
    direcoes = ["🟢 COMPRA", "🔴 VENDA"]

    ativo = random.choice(ativos)
    direcao = random.choice(direcoes)

    now_dt_sp = datetime.now(tz_sp).replace(second=0, microsecond=0)

    entrada_dt = (now_dt_sp + timedelta(minutes=3)).strftime("%H:%M")
    protec1 = (now_dt_sp + timedelta(minutes=4)).strftime("%H:%M")
    protec2 = (now_dt_sp + timedelta(minutes=5)).strftime("%H:%M")

    return jsonify({
        "titulo": "ANÁLISE CONCLUÍDA POR I.A.",
        "moeda": ativo,
        "expiracao": "1 Minuto",
        "entrada": entrada_dt,
        "direcao": direcao,
        "protecao1": protec1,
        "protecao2": protec2,
        "blocked_until": now_ms + block_ms
    })


# API: current user info
@app.route("/api/user/me")
def api_user_me():
    user = current_user()
    if not user:
        return jsonify({"authenticated": False}), 401
    blocked_until = None
    if session.get("analysis_started_at_ms"):
        blocked_until = session.get("analysis_started_at_ms") + 7 * 60 * 1000
    return jsonify({
        "authenticated": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": bool(user.is_admin),
            "access_expires_at": to_ms(user.access_expires_at),
            "blocked_until": blocked_until
        }
    })


# ---------------- Click logging ----------------
@app.route("/api/registrar-clique", methods=["POST"])
def api_registrar_clique():
    user = current_user()
    if not user:
        return jsonify({"error": "not_authenticated"}), 401
    data = request.get_json() or {}
    button_name = data.get("button_name")
    if button_name not in ("telegram", "compra"):
        return jsonify({"error": "invalid_button"}), 400
    log = ClickLog(user_id=user.id, button_name=button_name)
    db.session.add(log)
    db.session.commit()
    return jsonify({"success": True})


# ---------------- Admin pages & APIs ----------------
@app.route("/admin")
def admin():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if not user.is_admin:
        return redirect(url_for("dashboard"))
    return render_template("admin.html", username=user.username)


# Admin API: users list/create/update/delete
@app.route("/api/admin/users", methods=["GET", "POST"])
def api_admin_users():
    user = current_user()
    if not user or not user.is_admin:
        return jsonify({"error": "unauthorized"}), 403

    if request.method == "GET":
        users = User.query.order_by(User.id.desc()).all()
        out = []
        for u in users:
            out.append({
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "is_admin": bool(u.is_admin),
                "access_expires_at": to_ms(u.access_expires_at),
                "created_at": to_ms(u.created_at),
                "last_analysis_started_at": session.get("analysis_started_at_ms") if u.id == user.id else None,
                "is_expired": (not u.is_access_valid())
            })
        return jsonify({"users": out})

    data = request.get_json() or {}
    email = data.get("email")
    username = data.get("username")
    password = data.get("password")
    is_admin_flag = bool(data.get("is_admin"))
    access_expires_ms = data.get("access_expires_at")

    if not (email and username and password):
        return jsonify({"error": "missing_fields"}), 400
    if User.query.filter((User.email == email) | (User.username == username)).first():
        return jsonify({"error": "exists"}), 400

    access_expires_at = None
    if access_expires_ms:
        access_expires_at = datetime.utcfromtimestamp(access_expires_ms / 1000.0)

    hashed = generate_password_hash(password)
    u = User(email=email, username=username, password=hashed, is_admin=is_admin_flag, access_expires_at=access_expires_at)
    db.session.add(u)
    db.session.commit()
    return jsonify({"ok": True, "id": u.id})


@app.route("/api/admin/users/<int:user_id>", methods=["PUT", "DELETE"])
def api_admin_user_modify(user_id):
    user = current_user()
    if not user or not user.is_admin:
        return jsonify({"error": "unauthorized"}), 403
    target = User.query.get(user_id)
    if not target:
        return jsonify({"error": "not_found"}), 404
    if request.method == "DELETE":
        db.session.delete(target)
        db.session.commit()
        return jsonify({"ok": True})
    data = request.get_json() or {}
    if data.get("email"):
        target.email = data.get("email")
    if data.get("username"):
        target.username = data.get("username")
    if "is_admin" in data:
        target.is_admin = bool(data.get("is_admin"))
    if "access_expires_at" in data:
        if data.get("access_expires_at") is None:
            target.access_expires_at = None
        else:
            target.access_expires_at = datetime.utcfromtimestamp(int(data.get("access_expires_at")) / 1000.0)
    if data.get("password"):
        target.password = generate_password_hash(data.get("password"))
    db.session.add(target)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/users/<int:user_id>/renew", methods=["POST"])
def api_admin_user_renew(user_id):
    admin = current_user()
    if not admin or not admin.is_admin:
        return jsonify({"error": "unauthorized"}), 403

    target = User.query.get(user_id)
    if not target:
        return jsonify({"error": "not_found"}), 404

    data = request.get_json() or {}
    if "access_expires_at" not in data:
        return jsonify({"error": "missing_access_expires_at"}), 400

    if data["access_expires_at"] is None:
        target.access_expires_at = None
    else:
        try:
            ms = int(data["access_expires_at"])
            target.access_expires_at = datetime.utcfromtimestamp(ms / 1000.0)
        except Exception:
            return jsonify({"error": "invalid_timestamp"}), 400

    db.session.add(target)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/clicks/list")
def api_admin_clicks_list():
    user = current_user()
    if not user or not user.is_admin:
        return jsonify({"error": "unauthorized"}), 403
    logs = ClickLog.query.order_by(ClickLog.clicked_at.desc()).limit(1000).all()
    out = []
    for l in logs:
        out.append({
            "id": l.id,
            "user_id": l.user_id,
            "username": l.user.username if l.user else None,
            "button_name": l.button_name,
            "clicked_at": to_ms(l.clicked_at)
        })
    return jsonify({"logs": out})


@app.route("/api/admin/clicks/stats")
def api_admin_clicks_stats():
    user = current_user()
    if not user or not user.is_admin:
        return jsonify({"error": "unauthorized"}), 403
    period = request.args.get("period", "daily")
    now = datetime.utcnow()

    labels = []
    telegram_counts = {}
    compra_counts = {}

    if period == "daily":
        days = 30
        start = (now - timedelta(days=days)).date()
        for i in range(days + 1):
            d = start + timedelta(days=i)
            label = d.strftime("%Y-%m-%d")
            labels.append(label)
            telegram_counts[label] = 0
            compra_counts[label] = 0
        logs = ClickLog.query.filter(ClickLog.clicked_at >= datetime.combine(start, datetime.min.time())).all()
        for l in logs:
            key = l.clicked_at.date().strftime("%Y-%m-%d")
            if l.button_name == "telegram":
                telegram_counts[key] += 1
            else:
                compra_counts[key] += 1

    elif period == "weekly":
        weeks = 12
        start_date = (now - timedelta(weeks=weeks)).date()
        def week_label(dt):
            y, w, _ = dt.isocalendar()
            return f"{y}-W{w:02d}"
        for i in range(weeks + 1):
            dt = start_date + timedelta(weeks=i)
            label = week_label(dt)
            labels.append(label)
            telegram_counts[label] = 0
            compra_counts[label] = 0
        logs = ClickLog.query.filter(ClickLog.clicked_at >= datetime.combine(start_date, datetime.min.time())).all()
        for l in logs:
            key = week_label(l.clicked_at.date())
            if l.button_name == "telegram":
                telegram_counts[key] += 1
            else:
                compra_counts[key] += 1

    else:
        months = 12
        start_month = (now.replace(day=1) - timedelta(days=30 * months)).date()
        def month_label(dt):
            return dt.strftime("%Y-%m")
        cur = start_month
        for i in range(months + 1):
            label = month_label(cur)
            labels.append(label)
            telegram_counts[label] = 0
            compra_counts[label] = 0
            year = cur.year + (cur.month // 12)
            month = (cur.month % 12) + 1
            try:
                cur = cur.replace(year=year, month=month, day=1)
            except Exception:
                cur = (cur + timedelta(days=31)).replace(day=1)
        logs = ClickLog.query.filter(ClickLog.clicked_at >= datetime.combine(start_month, datetime.min.time())).all()
        for l in logs:
            key = month_label(l.clicked_at)
            if l.button_name == "telegram":
                telegram_counts[key] += 1
            else:
                compra_counts[key] += 1

    telegram_arr = [telegram_counts.get(lbl, 0) for lbl in labels]
    compra_arr = [compra_counts.get(lbl, 0) for lbl in labels]
    total_arr = [telegram_arr[i] + compra_arr[i] for i in range(len(labels))]

    return jsonify({
        "labels": labels,
        "telegram": telegram_arr,
        "compra": compra_arr,
        "total": total_arr
    })


if __name__ == "__main__":
    app.run(debug=True)
