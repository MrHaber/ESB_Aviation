from datetime import datetime,timezone
import uuid
from apscheduler.triggers.interval import IntervalTrigger
from datetime import timedelta
import re
from loguru import logger
from apscheduler.triggers.date import DateTrigger

# утилитные функции
def generate_request_id() -> str:
    return str(uuid.uuid4())

def get_current_timestamp():
    return datetime.utcnow()

def create_trigger(schedule_config: dict, moscow_time: bool = False):
        if "run_at" in schedule_config:
            try:
                run_datetime = datetime.fromisoformat(schedule_config["run_at"].replace("Z", "+00:00"))
                run_datetime = run_datetime.replace(tzinfo=timezone.utc)
                current_time = datetime.now(timezone.utc)
                if moscow_time:
                    naive_time = datetime.fromisoformat(schedule_config["run_at"].replace("Z", ""))
                    msk_time = naive_time.replace(tzinfo=timezone(timedelta(hours=3))) # Пытаемся преобразовать московское в UTC
                    run_datetime = msk_time.astimezone(timezone.utc) # APSScheduler работает только по UTC, костыль с timedelta
                if run_datetime < current_time:
                    logger.warning(f"Run date {run_datetime} is in the past, task will not be scheduled")
                    return None
                return DateTrigger(run_date=run_datetime)
            except ValueError as e:
                logger.error(f"Invalid run_at format: {str(e)}")
                return None
        elif "interval" in schedule_config:
            interval_str = schedule_config["interval"]
            match = re.match(r"(\d+)\s*(second|minute|hour|day|week)s?", interval_str.lower())
            if not match:
                logger.error(f"Invalid interval format: {interval_str}")
                return None
            value = int(match.group(1))
            unit = match.group(2)
            unit_map = {
                "second": "seconds",
                "minute": "minutes",
                "hour": "hours",
                "day": "days",
                "week": "weeks"
            }
            kwargs = {unit_map[unit]: value}
            return IntervalTrigger(**kwargs)
        return None