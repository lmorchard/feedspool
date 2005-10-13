from timezones import utc
import isodate
from datetime import datetime, timedelta

ISO_NEVER = '1970-01-01T00:00:00+00:00'
def datetime2ISO(dt):  return dt.replace(microsecond=0).isoformat()
def ISO2datetime(iso): return isodate.parse_datetime(iso)
def now_datetime():    return datetime.now(utc)
def now_ISO():         return datetime2ISO(now_datetime())

