"""This provides a plugin which is meant to clean up old spooled entries.

It will not delete entries which still appear in the feed, because these 
would just be "rediscovered" as new upon the next scan.  But, once entries
have fallen out of the feed and have aged beyond the given maximum, they
will be deleted.  This should hopefully keep the spool from growing 
out of control, and maybe reclaim some inodes taken up by all those tiny
files.
"""
import os, os.path, time

from feedspool import config
from feedspool.plugins import Plugin

class CleanOldEntriesPlugin(Plugin):

    # TODO: This should be specified in a config file overlaid on main config
    MAX_ENTRY_AGE = 15 * 24 * 60 * 60 

    def feed_poll_start(self, subscription):
        self.all_entries = []

    def feed_new_entries(self, subscription, new_entries, all_entries):
        self.all_entries = all_entries

    def feed_no_new_entries(self, subscription, all_entries):
        self.all_entries = all_entries

    def feed_poll_end(self, subscription):
        # Don't do anything if this scan skipped polling the feed.
        if not len(self.all_entries) > 0: return

        # Look up all the entries in the feed's spool.
        entries_path  = subscription.entries_path
        spool_entries = [ 
            os.path.join(entries_path, x) 
            for x in os.listdir(entries_path) 
            if x.endswith('.entry') 
        ]

        # Remove entries no longer found in the feed yet older than the
        # maximum age for cleanup.
        now = time.time()
        delete_cnt = 0
        for fn in spool_entries:
            if fn not in self.all_entries:
                if (now - os.stat(fn).st_mtime) > self.MAX_ENTRY_AGE:
                    try:    
                        os.remove(fn)
                        delete_cnt += 1
                    except: 
                        self.log.exception("Problem cleaning entry %s" % fn)

        self.log.debug("Deleted %s old entries." % delete_cnt)

