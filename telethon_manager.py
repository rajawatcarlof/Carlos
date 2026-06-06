"""
Telethon client manager for handling multiple Telegram accounts
"""
import os
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from database import db, Group
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

active_clients = {}


class TelethonManager:
    def __init__(self, api_id, api_hash):
        self.api_id = api_id
        self.api_hash = api_hash
        self.sessions_dir = os.path.join(os.getcwd(), 'sessions')
        if not os.path.exists(self.sessions_dir):
            os.makedirs(self.sessions_dir)
    
    def get_session_path(self, phone_number):
        sanitized_phone = phone_number.replace('+', '').replace(' ', '')
        return os.path.join(self.sessions_dir, f'{sanitized_phone}')
    
    async def login_account(self, phone_number, password=None):
        try:
            session_path = self.get_session_path(phone_number)
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            if await client.is_user_authorized():
                user = await client.get_me()
                active_clients[phone_number] = client
                return True, user.id, None, client
            await client.send_code_request(phone_number)
            return True, None, None, client
        except Exception as e:
            return False, None, f"Login error: {str(e)}", None
    
    async def verify_otp(self, phone_number, otp_code, client=None):
        try:
            if not client:
                session_path = self.get_session_path(phone_number)
                client = TelegramClient(session_path, self.api_id, self.api_hash)
                await client.connect()
            user = await client.sign_in(phone_number, otp_code)
            active_clients[phone_number] = client
            return True, user.id, None
        except SessionPasswordNeededError:
            return False, None, "2FA password required"
        except Exception as e:
            return False, None, f"OTP verification error: {str(e)}"
    
    async def verify_2fa(self, phone_number, password, client=None):
        try:
            if not client:
                session_path = self.get_session_path(phone_number)
                client = TelegramClient(session_path, self.api_id, self.api_hash)
                await client.connect()
            user = await client.sign_in(password=password)
            active_clients[phone_number] = client
            return True, user.id, None
        except Exception as e:
            return False, None, f"2FA verification error: {str(e)}"
    
    async def load_groups(self, phone_number, account_id):
        try:
            session_path = self.get_session_path(phone_number)
            if phone_number in active_clients:
                client = active_clients[phone_number]
            else:
                client = TelegramClient(session_path, self.api_id, self.api_hash)
                await client.connect()
            
            if not await client.is_user_authorized():
                return False, 0, "Account not authorized"
            
            Group.query.filter_by(account_id=account_id).delete()
            db.session.commit()
            
            dialogs = await client.get_dialogs()
            group_count = 0
            for dialog in dialogs:
                if dialog.is_group or dialog.is_channel:
                    try:
                        group = Group(group_id=str(dialog.id), group_name=dialog.name or 'Unknown', members_count=0, account_id=account_id)
                        db.session.add(group)
                        group_count += 1
                    except:
                        continue
            db.session.commit()
            active_clients[phone_number] = client
            return True, group_count, None
        except Exception as e:
            return False, 0, f"Error loading groups: {str(e)}"
    
    async def send_message(self, phone_number, group_id, message_text):
        try:
            session_path = self.get_session_path(phone_number)
            if phone_number in active_clients:
                client = active_clients[phone_number]
            else:
                client = TelegramClient(session_path, self.api_id, self.api_hash)
                await client.connect()
            
            if not await client.is_user_authorized():
                return False, "Account not authorized", None
            message = await client.send_message(int(group_id), message_text)
            active_clients[phone_number] = client
            return True, None, message.id
        except Exception as e:
            return False, f"Error sending message: {str(e)}", None
    
    async def disconnect(self, phone_number):
        try:
            if phone_number in active_clients:
                await active_clients[phone_number].disconnect()
                del active_clients[phone_number]
                return True
            return False
        except:
            return False
    
    async def get_account_status(self, phone_number):
        try:
            session_path = self.get_session_path(phone_number)
            if not os.path.exists(f"{session_path}.session"):
                return "logged_out"
            if phone_number in active_clients and await active_clients[phone_number].is_user_authorized():
                return "online"
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            if await client.is_user_authorized():
                active_clients[phone_number] = client
                return "online"
            return "offline"
        except:
            return "offline"
    
    async def reconnect_account(self, phone_number):
        try:
            session_path = self.get_session_path(phone_number)
            if phone_number in active_clients:
                try:
                    await active_clients[phone_number].disconnect()
                except:
                    pass
                del active_clients[phone_number]
            
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            if await client.is_user_authorized():
                active_clients[phone_number] = client
                return True, None
            else:
                return False, "Not authorized"
        except Exception as e:
            return False, f"Reconnection error: {str(e)}"


def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                return executor.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except:
        return asyncio.run(coro)
