from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)  # hash da senha
    is_admin = db.Column(db.Boolean, default=False)  # booleano consistente
    access_expires_at = db.Column(db.DateTime, nullable=True)  # None = vitalício
    is_expired = db.Column(db.Boolean, default=False)  # já existia

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clicks = db.relationship("ClickLog", backref="user", lazy=True)

    def is_access_valid(self):
        """Retorna True se o acesso ainda está válido (vitalício ou data no futuro)."""
        return self.access_expires_at is None or self.access_expires_at > datetime.utcnow()

    def update_expiration_status(self):
        """Atualiza o campo is_expired de acordo com access_expires_at."""
        self.is_expired = not self.is_access_valid()
        return self.is_expired

    def renew_access(self, new_access_dt):
        """Renova o acesso do usuário."""
        self.access_expires_at = new_access_dt
        self.is_expired = False

    def __repr__(self):
        return f"<User {self.username}>"


class ClickLog(db.Model):
    __tablename__ = "click_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    button_name = db.Column(db.String(50), nullable=False)  # "telegram" ou "compra"
    clicked_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ClickLog {self.button_name} - User {self.user_id}>"
