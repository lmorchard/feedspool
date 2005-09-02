from datetime import tzinfo, timedelta, datetime
import time as _time

ZERO = timedelta(0)
HOUR = timedelta(hours=1)

# A UTC class.

class UTC(tzinfo):
    """UTC"""
    def utcoffset(self, dt): return ZERO
    def tzname(self, dt): return "UTC"
    def dst(self, dt):  return ZERO

utc = UTC()

STDOFFSET = timedelta(seconds = -_time.timezone)
if _time.daylight:
    DSTOFFSET = timedelta(seconds = -_time.altzone)
else:
    DSTOFFSET = STDOFFSET

DSTDIFF = DSTOFFSET - STDOFFSET

class LocalTimezone(tzinfo):

    def utcoffset(self, dt):
        if self._isdst(dt):
            return DSTOFFSET
        else:
            return STDOFFSET

    def dst(self, dt):
        if self._isdst(dt):
            return DSTDIFF
        else:
            return ZERO

    def tzname(self, dt):
        return _time.tzname[self._isdst(dt)]

    def _isdst(self, dt):
        try:
            tt = (dt.year, dt.month, dt.day,
                  dt.hour, dt.minute, dt.second,
                  dt.weekday(), 0, -1)
            stamp = _time.mktime(tt)
            tt = _time.localtime(stamp)
        except: 
            return False
        return tt.tm_isdst > 0

Local = LocalTimezone()
