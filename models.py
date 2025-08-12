from datetime import datetime, timezone
from flask_login import UserMixin
from sqlalchemy.types import TypeDecorator, DateTime

from extensions import db, bcrypt


class UTCDateTime(TypeDecorator):
    """A DateTime type that stores timezone-aware UTC datetimes."""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(UTCDateTime, default=lambda: datetime.now(timezone.utc))
    trackings = db.relationship('Tracking', backref='user', lazy=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.phone_number} (Admin: {self.is_admin})>"


class Tracking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tracking_number = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(UTCDateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Tracking {self.tracking_number}>"
