"""
Main Flask application for Multi-Account Telegram Group Message Manager
"""
import os
from flask import Flask, render_template, request, jsonify
from database import db, init_db, TelegramAccount, Group, Message, ScheduledMessage, RepeatTask, Log, Setting, TaskLog
from telethon_manager import TelethonManager, run_async
from scheduler import MessageScheduler
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///telegram_manager.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key'

db.init_app(app)
init_db(app)

API_ID = int(os.getenv('TELEGRAM_API_ID', '29948857'))
API_HASH = os.getenv('TELEGRAM_API_HASH', 'e7f4f2b6c3c3c3c3c3c3c3c3c3c3c3c3')

telethon_manager = TelethonManager(API_ID, API_HASH)
message_scheduler = MessageScheduler(API_ID, API_HASH)
message_scheduler.start()


# ==================== DASHBOARD ====================
@app.route('/')
def dashboard():
    return render_template('dashboard.html')


@app.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    try:
        total_accounts = TelegramAccount.query.count()
        total_groups = Group.query.count()
        active_accounts = TelegramAccount.query.filter_by(status='online').count()
        today = datetime.utcnow().date()
        messages_today = Message.query.filter(
            db.func.DATE(Message.sent_at) == today
        ).count()
        running_tasks = TaskLog.query.filter_by(status='running').count()
        pending_tasks = TaskLog.query.filter_by(status='pending').count()
        
        return jsonify({
            'success': True,
            'data': {
                'total_accounts': total_accounts,
                'total_groups': total_groups,
                'active_sessions': active_accounts,
                'messages_today': messages_today,
                'running_tasks': running_tasks,
                'pending_tasks': pending_tasks
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== ACCOUNTS ====================
@app.route('/accounts')
def accounts_page():
    return render_template('accounts.html')


@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    try:
        accounts = TelegramAccount.query.all()
        return jsonify({'success': True, 'data': [acc.to_dict() for acc in accounts]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts/add', methods=['POST'])
def add_account():
    try:
        data = request.json
        phone_number = data.get('phone_number')
        account_name = data.get('account_name')
        
        if not phone_number or not account_name:
            return jsonify({'success': False, 'error': 'Phone and name required'})
        
        existing = TelegramAccount.query.filter_by(phone_number=phone_number).first()
        if existing:
            return jsonify({'success': False, 'error': 'Account exists'})
        
        account = TelegramAccount(phone_number=phone_number, account_name=account_name, api_id=API_ID, api_hash=API_HASH)
        db.session.add(account)
        db.session.commit()
        
        success, user_id, error, client = run_async(telethon_manager.login_account(phone_number))
        
        if success:
            return jsonify({'success': True, 'account_id': account.id, 'requires_otp': True})
        else:
            db.session.delete(account)
            db.session.commit()
            return jsonify({'success': False, 'error': error})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts/<int:account_id>/verify-otp', methods=['POST'])
def verify_otp(account_id):
    try:
        data = request.json
        otp_code = data.get('otp_code')
        account = TelegramAccount.query.get(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'})
        
        success, user_id, error = run_async(telethon_manager.verify_otp(account.phone_number, otp_code))
        
        if success:
            account.user_id = user_id
            account.is_logged_in = True
            account.status = 'online'
            db.session.commit()
            return jsonify({'success': True, 'requires_2fa': False})
        elif 'password' in error.lower():
            return jsonify({'success': True, 'requires_2fa': True})
        else:
            return jsonify({'success': False, 'error': error})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts/<int:account_id>/verify-2fa', methods=['POST'])
def verify_2fa(account_id):
    try:
        data = request.json
        password = data.get('password')
        account = TelegramAccount.query.get(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'})
        
        success, user_id, error = run_async(telethon_manager.verify_2fa(account.phone_number, password))
        
        if success:
            account.user_id = user_id
            account.is_logged_in = True
            account.status = 'online'
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': error})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts/<int:account_id>/delete', methods=['POST'])
def delete_account(account_id):
    try:
        account = TelegramAccount.query.get(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'})
        
        run_async(telethon_manager.disconnect(account.phone_number))
        db.session.delete(account)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== GROUPS ====================
@app.route('/groups')
def groups_page():
    return render_template('groups.html')


@app.route('/api/groups/load/<int:account_id>', methods=['POST'])
def load_groups(account_id):
    try:
        account = TelegramAccount.query.get(account_id)
        if not account or not account.is_logged_in:
            return jsonify({'success': False, 'error': 'Account not logged in'})
        
        success, group_count, error = run_async(telethon_manager.load_groups(account.phone_number, account.id))
        
        if success:
            return jsonify({'success': True, 'group_count': group_count})
        else:
            return jsonify({'success': False, 'error': error})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/groups/<int:account_id>', methods=['GET'])
def get_groups(account_id):
    try:
        groups = Group.query.filter_by(account_id=account_id).all()
        return jsonify({'success': True, 'data': [g.to_dict() for g in groups]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/groups/select', methods=['POST'])
def select_groups():
    try:
        data = request.json
        group_ids = data.get('group_ids', [])
        is_selected = data.get('is_selected', False)
        
        for group_id in group_ids:
            group = Group.query.get(group_id)
            if group:
                group.is_selected = is_selected
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== MESSAGES ====================
@app.route('/sender')
def sender_page():
    return render_template('sender.html')


@app.route('/api/messages/send', methods=['POST'])
def send_messages():
    try:
        data = request.json
        account_ids = data.get('account_ids', [])
        group_ids = data.get('group_ids', [])
        message_text = data.get('message_text')
        
        if not message_text or not account_ids or not group_ids:
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        task = TaskLog(task_name=f'Send to {len(group_ids)} groups', task_type='message_send', status='running')
        db.session.add(task)
        db.session.commit()
        
        success_count = 0
        for account_id in account_ids:
            account = TelegramAccount.query.get(account_id)
            if not account or not account.is_logged_in:
                continue
            for group_id in group_ids:
                success, error, msg_id = run_async(telethon_manager.send_message(account.phone_number, group_id, message_text))
                if success:
                    msg = Message(account_id=account.id, group_id=group_id, message_text=message_text, status='sent')
                    db.session.add(msg)
                    success_count += 1
        
        task.status = 'completed'
        db.session.commit()
        return jsonify({'success': True, 'sent': success_count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== REPEATER ====================
@app.route('/repeater')
def repeater_page():
    return render_template('repeater.html')


@app.route('/api/repeater/start', methods=['POST'])
def start_repeater():
    try:
        data = request.json
        account_id = data.get('account_id')
        group_ids = data.get('group_ids', [])
        message_text = data.get('message_text')
        interval_type = data.get('interval_type')
        interval_value = data.get('interval_value')
        
        account = TelegramAccount.query.get(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'})
        
        repeat_task = RepeatTask(
            account_id=account_id, message_text=message_text, groups_data=group_ids,
            interval_type=interval_type, interval_value=int(interval_value), is_active=True
        )
        db.session.add(repeat_task)
        db.session.commit()
        
        message_scheduler.add_repeat_task(repeat_task.id, account.phone_number, group_ids, message_text, interval_type, int(interval_value))
        return jsonify({'success': True, 'task_id': repeat_task.id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/repeater/<int:task_id>/pause', methods=['POST'])
def pause_repeater(task_id):
    return jsonify({'success': message_scheduler.pause_repeat_task(task_id)})


@app.route('/api/repeater/<int:task_id>/resume', methods=['POST'])
def resume_repeater(task_id):
    return jsonify({'success': message_scheduler.resume_repeat_task(task_id)})


@app.route('/api/repeater/<int:task_id>/stop', methods=['POST'])
def stop_repeater(task_id):
    return jsonify({'success': message_scheduler.remove_repeat_task(task_id)})


# ==================== LOGS ====================
@app.route('/logs')
def logs_page():
    return render_template('logs.html')


@app.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        page = request.args.get('page', 1, type=int)
        logs = Log.query.order_by(Log.timestamp.desc()).paginate(page=page, per_page=50)
        return jsonify({'success': True, 'data': [log.to_dict() for log in logs.items]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== SETTINGS ====================
@app.route('/settings')
def settings_page():
    return render_template('settings.html')


@app.route('/api/settings', methods=['GET'])
def get_settings():
    try:
        settings = Setting.query.all()
        return jsonify({'success': True, 'data': {s.key: s.value for s in settings}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/settings/update', methods=['POST'])
def update_settings():
    try:
        data = request.json
        for key, value in data.items():
            setting = Setting.query.filter_by(key=key).first()
            if setting:
                setting.value = str(value)
            else:
                db.session.add(Setting(key=key, value=str(value)))
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    print("Starting Telegram Multi-Account Manager on http://localhost:5000")
    app.run(debug=True, host='127.0.0.1', port=5000, use_reloader=False)
