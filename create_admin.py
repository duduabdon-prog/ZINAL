from models import db, User
from werkzeug.security import generate_password_hash
from datetime import datetime
from app import app

with app.app_context():
    email = "admin@zinal.com"
    username = "admin@zinal.com"
    password_plain = "admin123"  # troque para senha segura
    hashed = generate_password_hash(password_plain)

    if not User.query.filter_by(username=username).first():
        admin_user = User(
            email=email,
            username=username,
            password=hashed,
            is_admin=True,
            access_expires_at=None
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Admin criado com sucesso.")
    else:
        print("Admin já existe.")
