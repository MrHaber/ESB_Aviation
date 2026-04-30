from datetime import datetime, timezone
from datetime import timedelta

run_at = "2025-07-31T15:16:00Z"
run_datetime = (datetime.fromisoformat(run_at.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)) + timedelta(hours=3)
current_time = datetime.now(timezone.utc)
print(current_time)
if run_datetime < current_time:
    print("Время уже прошло!")
else:
    print("Время в будущем, можно использовать.")