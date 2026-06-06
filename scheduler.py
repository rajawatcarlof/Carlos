"""
Task scheduler for managing messages and repeating tasks
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from database import db, ScheduledMessage, RepeatTask, Message, Log
from telethon_manager import TelethonManager, run_async
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessageScheduler:
    def __init__(self, api_id, api_hash):
        self.scheduler = BackgroundScheduler()
        self.telethon = TelethonManager(api_id, api_hash)
    
    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
    
    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
    
    def schedule_message(self, scheduled_message_id, phone_number, groups, message_text, scheduled_time):
        try:
            job_id = f"scheduled_msg_{scheduled_message_id}"
            self.scheduler.add_job(
                func=self._send_scheduled_message,
                trigger=DateTrigger(run_date=scheduled_time),
                id=job_id,
                args=[scheduled_message_id, phone_number, groups, message_text],
                replace_existing=True
            )
            return True
        except Exception as e:
            logger.error(f"Error scheduling message: {str(e)}")
            return False
    
    def _send_scheduled_message(self, scheduled_message_id, phone_number, groups, message_text):
        try:
            for group_id in groups:
                success, error, msg_id = run_async(
                    self.telethon.send_message(phone_number, group_id, message_text)
                )
                if success:
                    msg = Message(account_id=None, group_id=group_id, message_text=message_text, status='sent')
                    db.session.add(msg)
            scheduled_msg = ScheduledMessage.query.get(scheduled_message_id)
            if scheduled_msg:
                scheduled_msg.is_sent = True
            db.session.commit()
        except Exception as e:
            logger.error(f"Error in _send_scheduled_message: {str(e)}")
    
    def add_repeat_task(self, repeat_task_id, phone_number, groups, message_text, interval_type, interval_value):
        try:
            job_id = f"repeat_task_{repeat_task_id}"
            if interval_type == 'seconds':
                seconds = interval_value
            elif interval_type == 'minutes':
                seconds = interval_value * 60
            elif interval_type == 'hours':
                seconds = interval_value * 3600
            else:
                return False
            
            self.scheduler.add_job(
                func=self._send_repeating_message,
                trigger=IntervalTrigger(seconds=seconds),
                id=job_id,
                args=[repeat_task_id, phone_number, groups, message_text],
                replace_existing=True
            )
            return True
        except Exception as e:
            logger.error(f"Error adding repeat task: {str(e)}")
            return False
    
    def _send_repeating_message(self, repeat_task_id, phone_number, groups, message_text):
        try:
            repeat_task = RepeatTask.query.get(repeat_task_id)
            if not repeat_task or not repeat_task.is_active:
                return
            if repeat_task.repeat_count and repeat_task.repeat_completed >= repeat_task.repeat_count:
                self.pause_repeat_task(repeat_task_id)
                return
            for group_id in groups:
                success, error, msg_id = run_async(
                    self.telethon.send_message(phone_number, group_id, message_text)
                )
                if success:
                    msg = Message(account_id=repeat_task.account_id, group_id=group_id, message_text=message_text, status='sent')
                    db.session.add(msg)
            repeat_task.repeat_completed += 1
            repeat_task.last_executed = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            logger.error(f"Error in _send_repeating_message: {str(e)}")
    
    def pause_repeat_task(self, repeat_task_id):
        try:
            job_id = f"repeat_task_{repeat_task_id}"
            job = self.scheduler.get_job(job_id)
            if job:
                job.pause()
            repeat_task = RepeatTask.query.get(repeat_task_id)
            if repeat_task:
                repeat_task.is_active = False
                db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error pausing repeat task: {str(e)}")
            return False
    
    def resume_repeat_task(self, repeat_task_id):
        try:
            job_id = f"repeat_task_{repeat_task_id}"
            job = self.scheduler.get_job(job_id)
            if job:
                job.resume()
            repeat_task = RepeatTask.query.get(repeat_task_id)
            if repeat_task:
                repeat_task.is_active = True
                db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error resuming repeat task: {str(e)}")
            return False
    
    def remove_repeat_task(self, repeat_task_id):
        try:
            job_id = f"repeat_task_{repeat_task_id}"
            self.scheduler.remove_job(job_id)
            repeat_task = RepeatTask.query.get(repeat_task_id)
            if repeat_task:
                repeat_task.is_active = False
                db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error removing repeat task: {str(e)}")
            return False
