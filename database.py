"""
Database models and initialization for Telegram Account Manager
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class TelegramAccount(db.Model):
    __tablename__ = 'telegram_accounts'
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    account_name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, unique=True, nullable=True)
    is_logged_in = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='offline')
    session_file = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    api_id = db.Column(db.Integer, nullable=False)
    api_hash = db.Column(db.String(255), nullable=False)
    
    groups = db.relationship('Group', backref='account', lazy=True, cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='account', lazy=True, cascade='all, delete-orphan')
    logs = db.relationship('Log', backref='account', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'phone_number': self.phone_number,
            'account_name': self.account_name,
            'user_id': self.user_id,
            'is_logged_in': self.is_logged_in,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'last_active': self.last_active.isoformat()
        }


class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(50), nullable=False)
    group_name = db.Column(db.String(255), nullable=False)
    members_count = db.Column(db.Integer, default=0)
    account_id = db.Column(db.Integer, db.ForeignKey('telegram_accounts.id'), nullable=False)
    is_selected = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('group_id', 'account_id', name='unique_group_per_account'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'group_id': self.group_id,
            'group_name': self.group_name,
            'members_count': self.members_count,
            'account_id': self.account_id,
            'is_selected': self.is_selected
        }


class GroupList(db.Model):
    __tablename__ = 'group_lists'
    id = db.Column(db.Integer, primary_key=True)
    list_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    groups_data = db.Column(db.JSON, default=[])


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('telegram_accounts.id'), nullable=False)
    group_id = db.Column(db.String(50), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='sent')
    error_message = db.Column(db.Text, nullable=True)


class ScheduledMessage(db.Model):
    __tablename__ = 'scheduled_messages'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('telegram_accounts.id'), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    groups_data = db.Column(db.JSON, default=[])
    scheduled_time = db.Column(db.DateTime, nullable=False)
    is_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RepeatTask(db.Model):
    __tablename__ = 'repeat_tasks'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('telegram_accounts.id'), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    groups_data = db.Column(db.JSON, default=[])
    interval_type = db.Column(db.String(20), nullable=False)
    interval_value = db.Column(db.Integer, nullable=False)
    repeat_count = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=False)
    repeat_completed = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_executed = db.Column(db.DateTime, nullable=True)


class Log(db.Model):
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('telegram_accounts.id'), nullable=True)
    group_id = db.Column(db.String(50), nullable=True)
    log_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'group_id': self.group_id,
            'log_type': self.log_type,
            'message': self.message,
            'timestamp': self.timestamp.isoformat()
        }


class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskLog(db.Model):
    __tablename__ = 'task_logs'
    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(255), nullable=False)
    task_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending')
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)


def init_db(app):
    with app.app_context():
        db.create_all()
        default_settings = {
            'default_delay': '1',
            'max_retries': '3',
            'auto_reconnect': 'true',
            'backup_interval': '24'
        }
        for key, value in default_settings.items():
            existing = Setting.query.filter_by(key=key).first()
            if not existing:
                db.session.add(Setting(key=key, value=value))
        db.session.commit()
