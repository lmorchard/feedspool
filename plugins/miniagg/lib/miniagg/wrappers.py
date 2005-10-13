""" 
"""
import sys, time, os, os.path, feedparser, md5
from feedparser.subscriptions import now_ISO
from templates import UNICODE_ENC, TMPL_NEWS_PAGE, TMPL_NEWS_FEED, TMPL_NEWS_ENTRY

class FeedWrapper:

    TMPL_NEWS_FEED  = TMPL_NEWS_FEED

    def __init__(self, feed, entry_fns, seen_db):
        """ """
        self.feed    = feed
        self.entries = []
        self.seen_db = seen_db

        # Parse in all the current entries.
        for fn in entry_fns:
            data    = feedparser.parse(fn)
            entries = data.get('entries', [])
            if len(entries) > 0:
                entry = entries[0]
                id    = entry.get('id', fn)
                hash  = md5.md5(id).hexdigest()
                if not self.seen_db.has_key(hash):
                    self.seen_db[hash] = now_ISO()
                    self.entries.append(EntryWrapper(self.feed, entry))
                else:
                    # Should note "updated" entries?
                    pass

        # Sort entries by date.
        self.entries.sort()

    def __getitem__(self, name):
        """ """
        # Handle a few more special-case keys.
        if name == "feed.entries":
            return "\n".join([ str(x) for x in self.entries ])

        # Handle access to feed data on keys starting with "feed."
        if name.startswith("feed."):
            return self.feed.get(name[5:], "").encode(UNICODE_ENC)
        
        # If all else fails, return an empty string.
        return ""

    def __str__(self):
        return self.TMPL_NEWS_FEED % self 

class EntryWrapper:

    TMPL_NEWS_ENTRY = TMPL_NEWS_ENTRY

    def __str__(self):
        return self.TMPL_NEWS_ENTRY % self 

    def __init__(self, feed, entry): 
        """Initialize the wrapper with feed and entry data."""
        self.feed  = feed
        self.entry = entry
        
        # Try to work out some sensible primary date for the entry, fall
        # back to the feed's date, and use the current time as a last resort.
        if entry.has_key("modified_parsed"):
            self.date = time.mktime(entry.modified_parsed)
        elif entry.has_key("issued_parsed"):
            self.date = time.mktime(entry.issued_parsed)
        elif self.feed.has_key("modified_parsed"):
            self.date = time.mktime(self.feed.modified_parsed)
        elif self.feed.has_key("issued_parsed"):
            self.date = time.mktime(self.feed.issued_parsed)
        else:
            self.date = time.time()

    def __cmp__(self, other):
        """Use the entry's date as the comparator for sorting & etc."""
        return other.date - self.date
    
    def __getitem__(self, name):
        """ """
        # Handle a few more special-case keys.
        if name == "entry.date":
            return time.strftime("%Y-%m-%d", time.localtime(self.date))
        if name == "entry.time": 
            return time.strftime("%H:%M:%S", time.localtime(self.date))
        if name == "entry.content":
            if "content" in self.entry:
                return self.entry.content[0].value.encode(UNICODE_ENC)
            return ""

        # Handle access to feed data on keys starting with "feed."
        if name.startswith("feed."):
            return self.feed.get(name[5:], "").encode(UNICODE_ENC)
        
        # Handle access to entry data on keys starting with "entry."
        if name.startswith("entry."):
            return self.entry.get(name[6:], "").encode(UNICODE_ENC)

        # If all else fails, return an empty string.
        return ""

