from datetime import datetime, timezone, timedelta


def get_time():
    utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    now = utc.astimezone(timezone(timedelta(hours=8)))
    return now.strftime('%y-%m-%d-%H-%M-%S')
