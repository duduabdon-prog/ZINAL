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
    # Se tzinfo for None, tratamos como UTC (datetime.utcnow() cria objetos 'naive' representando UTC)
    if dt.tzinfo is None:
        # usa calendar.timegm para evitar interpretações do timezone local
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
            session["is_admin"] = bool(user.is_admin)
            return redirect(url_for("admin") if user.is_admin else url_for("dashboard"))
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

    # check access expiry
    if user.access_expires_at and user.access_expires_at < datetime.utcnow():
        return jsonify({"error": "expired"}), 403

    now_ms = ms_now()
    block_ms = 7 * 60 * 1000
    last_ms = session.get("analysis_started_at_ms")

    if last_ms and (last_ms + block_ms) > now_ms:
        return jsonify({"error": "blocked", "blocked_until": last_ms + block_ms}), 429

    # allowed: set session start timestamp (server authoritative)
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

    # pega UTC "naive" agora e converte para SP
    now_dt_utc = datetime.utcnow().replace(second=0, microsecond=0)
    now_dt_sp = pytz.utc.localize(now_dt_utc).astimezone(tz_sp)

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
        return jsonify({
