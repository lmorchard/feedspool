""" """
import sys, time, os, os.path, feedparser
from feedspool import config
from feedspool.plugins import Plugin

from templates import UNICODE_ENC, TMPL_INDEX, TMPL_NEWS_PAGE, TMPL_NEWS_FEED, TMPL_NEWS_ENTRY
from wrappers  import FeedWrapper, EntryWrapper

NEWS_PAGE_FN = "news-%Y%m%d-%H%M%S.html" 

class MiniAggPlugin(Plugin):

    NEWS_PAGE_FN   = NEWS_PAGE_FN
    TMPL_NEWS_PAGE = TMPL_NEWS_PAGE

    def scan_start(self):
        """At start of scan, initialize for aggregation."""
        self.feeds = []

    def feed_new_entries(self, subscription, entries):
        """Upon finding new entries for a feed, wrap for rendering."""
        data = feedparser.parse(subscription.head_fn)
        if 'feed' in data:
            feed = FeedWrapper(data['feed'], entries)
            self.feeds.append(feed)

    def scan_end(self):
        """At the end of a scan, render out all the feeds with new entries."""
        if len(self.feeds) > 0:

            # Build the namespace for the template and render it.
            ns = {
                'now'   : time.strftime('%Y-%m-%dT%H:%M:%S'),
                'feeds' : '\n'.join([str(x) for x in self.feeds])
            }
            out = self.TMPL_NEWS_PAGE % ns

            # Work out the output file path.
            fn_out   = time.strftime(self.NEWS_PAGE_FN)
            path_out = os.path.join(self.plugin_root, 'www', fn_out)

            # Open the output file and write the output HTML.
            fout = open(path_out, 'w')
            fout.write(out)
            fout.close()
            
            self.log.debug("Wrote %s" % fn_out)

