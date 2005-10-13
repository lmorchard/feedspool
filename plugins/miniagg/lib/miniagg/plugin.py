""" """
import sys, time, os, os.path, anydbm, feedparser
from feedspool import config
from feedspool.plugins import Plugin
from feedspool.utils import ISO_NEVER, datetime2ISO, ISO2datetime, now_datetime, now_ISO

from templates import UNICODE_ENC, TMPL_NEWS_PAGE, TMPL_NEWS_FEED, TMPL_NEWS_ENTRY
from templates import TMPL_LIST_END, TMPL_LIST_START, TMPL_INDEX_PAGE, TMPL_INDEX_PAGE_ITEM
from templates import TMPL_MAIN_PAGE

from wrappers  import FeedWrapper, EntryWrapper

NEWS_PAGE_FN = "%Y/%m/%d/%H%M%S.html"

SEEN_DB_FN   = "data/seen.db"

class MiniAggPlugin(Plugin):

    NEWS_PAGE_FN         = NEWS_PAGE_FN
    TMPL_MAIN_PAGE       = TMPL_MAIN_PAGE
    TMPL_NEWS_PAGE       = TMPL_NEWS_PAGE
    TMPL_LIST_END        = TMPL_LIST_END
    TMPL_LIST_START      = TMPL_LIST_START
    TMPL_INDEX_PAGE      = TMPL_INDEX_PAGE
    TMPL_INDEX_PAGE_ITEM = TMPL_INDEX_PAGE_ITEM

    def startup(self):
        """At start of scan, initialize for aggregation."""
        self.feeds   = []
        self.seen_db = anydbm.open(os.path.join(self.plugin_root, SEEN_DB_FN), 'c')

    def feed_new_entries(self, subscription, new_entries, all_entries):
        """Upon finding new entries for a feed, wrap for rendering."""
        data = feedparser.parse(subscription.head_fn)
        if 'feed' in data:
            feed = FeedWrapper(data['feed'], new_entries, self.seen_db)
            self.log.debug("%s fresh entries for feed, %s already seen." % \
                ( len(feed.entries), len(feed.seen_entries) ) )
            if len(feed.entries) > 0:
                self.feeds.append(feed)

    def shutdown(self):
        """At the end of a scan, render out all the feeds with new entries."""
        # If no new entries were encountered, do nothing.
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

            # Create the leading directories, if necessary
            base_path, fn_out = os.path.split(path_out)
            if not os.path.isdir(base_path): os.makedirs(base_path)

            # Open the output file and write the output HTML.
            fout = open(path_out, 'w')
            fout.write(out)
            fout.close()
            
            self.log.debug("Wrote %s" % fn_out)

            # Index the news pages and produce nav HTML.
            self.index_news()

        self.seen_db.close()

    def index_news(self):
        pages = []

        for root, dirs, files in os.walk(os.path.join(self.plugin_root, 'www')):

            # A news archive dir is yyyy/mm/dd/HHMMSS.html
            parts = root.split('/')[-3:]

            # The second part should be a year
            if len(parts[0]) != 4: continue
            yy = parts[0]

            # The third part should be a month
            if len(parts[1]) != 2: continue
            mm = parts[1]
           
            # The fourth part should be a day
            if len(parts[2]) != 2: continue
            dd = parts[2]
           
            for file in files:
                (h, m, s) = file[0:2], file[2:4], file[4:6]
                page = { 
                    'path': '%s/%s' % ("/".join(parts), file), 
                    'yy':yy, 'mm':mm, 'dd':dd,
                    'h':h, 'm':m, 's':s
                }
                pages.append(page)

        pages.sort(lambda a,b: cmp(b['path'], a['path']))

        out, curr_date = [], None
        for p in pages:
            now = "%(yy)s-%(mm)s-%(dd)s" % p
            if now != curr_date:
                if curr_date: out.append(TMPL_LIST_END)
                out.append(TMPL_LIST_START % p)
                curr_date = now

            out.append(TMPL_INDEX_PAGE_ITEM % p)

        out.append(TMPL_LIST_END)

        # Write out the nav side panel.
        nav_path = os.path.join(self.plugin_root, 'www', 'nav.html')
        fout = open(nav_path, 'w')
        fout.write(TMPL_INDEX_PAGE % { 'page_list':"\n".join(out) })
        fout.close()

        # Write out the index page.
        if len(pages) > 0:
            index_path = os.path.join(self.plugin_root, 'www', 'index.html')
            fout = open(index_path, 'w')
            fout.write(TMPL_MAIN_PAGE % pages[0])
            fout.close()

