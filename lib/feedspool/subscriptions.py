"""
"""
import sys, os, os.path, time, logging, traceback, base64, urllib
import feedfinder
from datetime import datetime, timedelta
from md5 import md5
from cStringIO import StringIO
from timezones import utc
import isodate
from httpcache import HTTPCache
from feedspool import config
from feedspool.spooler import Spooler
from feedspool.config import plugin_manager
from TimeRotatingFileHandler import TimeRotatingFileHandler
from OverlayConfigParser import OverlayConfigParser

# TODO: Per-feed configurable logging levels?  Other config.
# TODO: Don't hardcode the TimeRotatingFileHandler in per-feed logs.

global log
log  = logging.getLogger("%s"%__name__)

# Misc date/time utilities (should these go elsewhere?)
ISO_NEVER = '1970-01-01T00:00:00+00:00'
def datetime2ISO(dt):  return dt.replace(microsecond=0).isoformat()
def ISO2datetime(iso): return isodate.parse_datetime(iso)
def now_datetime():    return datetime.now(utc)
def now_ISO():         return datetime2ISO(now_datetime())

class Subscription:
    """Encapsulate details of a subscription managed in the spool."""

    def __init__(self, uri, spool_path=None):
        """Initialize the subscription object."""
        self.log  = logging.getLogger("%s"%self.__class__.__name__)
        
        self.spool_path = \
            config.alt('data', 'spool', 'data/spool', spool_path)
        if not os.path.isdir(self.spool_path):
            log.debug("Creating new spool path: %s" % self.spool_path)
            os.mkdir(self.spool_path, 0777)

        self.uri          = uri
        self.uid          = md5(uri).hexdigest()
        self.path         = os.path.join(self.spool_path, self.uid)
        self.feed_fn      = os.path.join(self.path, config.FEED_FULL_FN)
        self.head_fn      = os.path.join(self.path, config.FEED_HEAD_FN)
        self.entries_path = os.path.join(self.path, config.ENTRIES_DIR)

        self.log_debug_hnd = None
        self.log_hnd       = None

        self.loadMeta()

    def loadMeta(self):
        """Load up the subscription's metadata."""
        self.meta = OverlayConfigParser(parent=config.config)
        self.meta_fn = os.path.join(self.path, config.META_FN)

        if os.path.isfile(self.meta_fn):
            # Load up the metadata for the subscription.
            self.meta.read(self.meta_fn)
        else:
            # Initialize new metadata when not found.
            self.initMeta()

    def initMeta(self):
        """ """
        # Initialize new metadata if none found.
        self.log.debug("Initializing metadata for %s" % self.uri)
        self.meta.add_section('scan')
        
        # TODO: Should fix the actual cause.  Something in meta init.
        #try:
        #    self.meta.add_section('scan')
        #except DuplicateSectionError:
        #    pass

        # Set some basic metadata values
        self.meta.set('scan', 'uri', self.uri)
        self.meta.set('scan', 'uid', self.uid)

        # Set the beginning datestamps.
        self.meta.set('scan', 'last_scanned', ISO_NEVER)
        self.meta.set('scan', 'last_polled',  ISO_NEVER)
        self.meta.set('scan', 'last_updated', ISO_NEVER)
        self.meta.set('scan', 'next_poll',    ISO_NEVER)

        # Set the default scanning parameters.
        self.meta.set('scan', 'current_update_period', '3600')

    def save(self):
        """Save changes to the subscription."""
        # Create the subscription spool dir if not found.
        if not os.path.isdir(self.path):
            log.debug("Creating new subscription spool path: %s" % self.path)
            os.mkdir(self.path, 0777)
            os.mkdir(os.path.join(self.path, config.ENTRIES_DIR), 0777)

        # Save the subscription metadata
        self.meta.write(open(self.meta_fn, 'w'))

    def scan(self):
        """Scan the subscribed feed for any updates, spool new entries."""
        self.startLogging()
        self.save() # HACK: Pre-save to ensure directories created
        plugin_manager.dispatch("feed_scan_start", subscription=self)

        try:
            # Bump the last scan timestamp.
            now = now_ISO()
            self.meta.set('scan', 'last_scanned', now)

            # Does any plugin want to force or veto a scan?
            force_scan, veto_scan = \
                plugin_manager.decide("feed_should_scan", subscription=self)

            # Is it time to poll?  Is this subscription not disabled?
            time_for_poll = now > self.meta.get('scan', 'next_poll')
            scan_enabled  = not self.meta.get('scan', 'disabled')

            # We should poll if it's not vetoed and if it's forced, or 
            # it's enabled and due for a poll
            # TODO: Should veto take precedence over force?
            should_poll = not veto_scan and \
                          (force_scan or (scan_enabled and time_for_poll))
            if should_poll:
                self.meta.set('scan', 'last_polled', now)
                self.log.debug("Polling %s" % self.uri)
                plugin_manager.dispatch("feed_poll_start", subscription=self)

                found_new_entries = False
                try:
                    # If a scan is being forced, or the feed has changed, go ahead...
                    changed = self.fetch()
                    if force_scan or changed: self.spool()

                except KeyboardInterrupt: raise
                except Exception, e:
                    self.log.exception("Problem while polling %s" % self.uri)
                    plugin_manager.dispatch("feed_poll_error", 
                        subscription=self, exception=e)

                # Tweak the update period and schedule the next poll.
                self.scheduleNextPoll()
                plugin_manager.dispatch("feed_poll_end", subscription=self)

        finally:
            # Save any changes to the subscription, stop logging.
            plugin_manager.dispatch("feed_scan_end", subscription=self)
            self.save()
            self.stopLogging()

    def spool(self):
        """Process feed data, spool off any new entries."""
        plugin_manager.dispatch("feed_spool_start", subscription=self)

        # Spool the entries found in the feed.
        spooler = Spooler(self)
        spooler.spool()
        all_entries, new_entries = spooler.getEntryPaths()

        # If found new entries, flip the flag.
        if len(new_entries) > 0:
            found_new_entries = True
            self.meta.set('scan', 'last_updated', now_ISO())
            self.log.debug("Found %s new entries." % \
                len(new_entries))
            plugin_manager.dispatch("feed_new_entries", 
                subscription=self, new_entries=new_entries, all_entries=all_entries)
        else:
            plugin_manager.dispatch("feed_no_new_entries", 
                subscription=self, all_entries=all_entries)

        plugin_manager.dispatch("feed_spool_end", subscription=self)

    def fetch(self):
        """Fetch the data for the feed, return whether feed has changed."""
        plugin_manager.dispatch("feed_fetch_start", subscription=self)

        # Prepare the URI and initial headers for the fetch.
        feed_uri = self.uri
        headers  = {
            'User-Agent': config.USER_AGENT,
            'Accept':     config.ACCEPT_HEADER 
        }

        # Stolen from feedparser: Handle inline user:password for basic auth
        auth = None
        urltype, rest  = urllib.splittype(feed_uri)
        realhost, rest = urllib.splithost(rest)
        if realhost:
            user_passwd, realhost = urllib.splituser(realhost)
            if user_passwd:
                feed_uri = "%s://%s%s" % (urltype, realhost, rest)
                auth = base64.encodestring(user_passwd).strip()
                headers['Authorization'] = "Basic %s" % auth

        # Grab the feed data via HTTPCache
        cache     = HTTPCache(feed_uri, headers)
        info      = cache.info()
        content   = cache.content()
        feed_hash = md5(content).hexdigest()

        # Copy over some HTTP headers as feed metadata
        if 'ETag' in info: 
            self.meta.set('scan', 'http_etag', info['ETag'])
        if 'Last-Modified' in info:
            self.meta.set('scan', 'http_last_modified', info['Last-Modified'])

        #changed = cache.fresh()
        changed = ( not self.meta.has_option('scan', 'last_feed_md5') or \
                    not feed_hash == self.meta.get('scan', 'last_feed_md5') )
        if changed:
            # Update the feed hash, write the fetched feed.
            self.meta.set('scan', 'last_feed_md5', feed_hash)
            fout = open(self.feed_fn, 'w')
            fout.write(content)
            fout.close()

        plugin_manager.dispatch("feed_fetch_end", subscription=self, changed=changed)
        return changed

    def scheduleNextPoll(self):
        """Schedule the next future poll based on update period."""
        update_period = self.meta.getint('scan', 'current_update_period')
        next_poll = now_datetime() + timedelta(seconds=update_period)
        self.meta.set('scan', 'next_poll', datetime2ISO(next_poll))

    def startLogging(self):
        """Start writing to the per-feed log."""
        # Ensure the per-feed log path exists
        self.log_path = os.path.join(self.path, 'logs')
        if not os.path.isdir(self.log_path):
            os.mkdir(self.log_path, 0777)

        log = logging.getLogger("")
        fmt = logging.Formatter\
            ('[%(asctime)s %(levelname)s %(name)s] %(message)s', 
             '%Y-%m-%dT%H:%M:%S')  
        
        log_debug_fn  = os.path.join(self.log_path, '%Y%m%d-debug.log')
        log_debug_hnd = TimeRotatingFileHandler(log_debug_fn)
        log_debug_hnd.setLevel(logging.DEBUG)
        log_debug_hnd.setFormatter(fmt)
        self.log_debug_hnd = log_debug_hnd
        log.addHandler(self.log_debug_hnd)

        log_fn  = os.path.join(self.log_path, '%Y%m%d.log')
        log_hnd = TimeRotatingFileHandler(log_fn)
        log_hnd.setLevel(logging.INFO)
        log_hnd.setFormatter(fmt)
        self.log_hnd = log_hnd
        log.addHandler(self.log_hnd)

    def stopLogging(self):
        """Stop writing to the per-feed log."""
        log = logging.getLogger("")
        
        if self.log_debug_hnd is not None:
            log.removeHandler(self.log_debug_hnd)
            self.log_debug_hnd.close()
            self.log_debug_hnd = None

        if self.log_hnd is not None:
            log.removeHandler(self.log_hnd)
            self.log_hnd.close()
            self.log_hnd = None

class SubscriptionsList:
    """Managed list of subscriptions."""
    # TODO: Optimization - exists(uri) method?

    def __init__(self, subs_list_fn=None):
        self.log = logging.getLogger("%s"%self.__class__.__name__)
        self.subs_list_fn = \
            config.alt('data', 'subscriptions', 
                       'data/subscriptions', subs_list_fn)

        # Create the subscriptions list file if it doesn't yet exist.
        if not os.path.isfile(self.subs_list_fn):
            fout = open(self.subs_list_fn, 'w')
            fout.close()

        # Load up the subscriptions (if any)
        fin = open(self.subs_list_fn, 'r')
        self.subs = [ 
            Subscription(x.strip()) 
            for x in fin.readlines()
            if not x.startswith('#') 
        ]
        fin.close()

    def list(self):
        """Return a list of subscriptions."""
        return [x for x in self.subs]

    def listURIs(self):
        """Return the list of subscribed feed URIs"""
        return [x.uri for x in self.list()]

    def get(self, uri):
        """Return the subscription for a given URI"""
        for x in self.subs:
            if x.uri == uri: return x
        raise SubscriptionNotFoundException(uri)

    def add(self, uri, find_feed=False):
        """Add a subscription to a feed."""
        if uri in self.listURIs():
            raise SubscriptionDuplicateException(uri)
     
        if not find_feed:
            # No need to locate a feed uri, so use the given uri
            feed_uri = uri
        
        else:
            feeds_found = feedfinder.getFeeds(uri)

            # There's a problem if there's less than or more than
            # one feed uri found
            if len(feeds_found) < 1: 
                raise SubscriptionFeedNotFoundException(uri)
            elif len(feeds_found) > 1: 
                raise SubscriptionMultipleFeedsFoundException(uri, feeds_found)

            # Get an existing feed, or create new a new feed
            feed_uri = feeds_found[0]

        # scan.feedScan(new_feed, xd)
        sub = Subscription(uri)
        plugin_manager.dispatch("adding_feed", subscription=sub)
        sub.save()
        self.subs.append(sub)

    def remove(self, uri):
        """Remove a subscription to a feed."""
        if not uri in self.listURIs():
            raise SubscriptionNotFoundException(uri)
        doomed_subs = [ x for x in self.subs if x.uri == uri ]
        for x in doomed_subs: 
            plugin_manager.dispatch("removing_feed", subscription=x)
            self.subs.remove(x)

    def save(self):
        """Save changes to the subscriptions list."""
        fout = open(self.subs_list_fn, 'w')
        fout.write('\n'.join(self.listURIs()))
        fout.close()

    def _importuri(self, uri, find_feed=False):
        """Utility function for subscription imports"""
        try:
            self.add(uri, find_feed=find_feed)
            self.log.info("Imported %s" % uri)
        except SubscriptionDuplicateException, e:
            log.error("Duplicate %s" % (uri))
        except SubscriptionFeedNotFoundException, e:
            log.error("No feed uris found at %s" % (uri))
        except SubscriptionMultipleFeedsFoundException, e:
            log.error("Multiple feed uris found at %s" % (uri))
        except KeyboardInterrupt:
            raise
        except:
            log.exception("Unexpected error while processing subscription")

    def fileexport(self, file=sys.stdout):
        """Export the subscriptions to a list of one uri per line"""
        for sub in self.listURIs():
            file.write("%s\n" % sub)

    def fileimport(self, file=sys.stdin, find_feeds=False):
        """Import subscriptions from a list of uris in a file"""
        for uri in file.readlines():
            if not uri.startswith("#"):
                log.debug("Trying to subscribe to %s" % (uri))
                _importuri(uri.rstrip(), find_feeds)


class SubscriptionDuplicateException(Exception):
    def __init__(self, uri): 
        self.uri  = uri
    def __str__(self): 
        return "Attempted to add a duplicate subscription: %s" % \
            (self.uri)

class SubscriptionMultipleFeedsFoundException(Exception):
    def __init__(self, uri, feeds): 
        self.uri = uri
        self.feeds = feeds
    def __str__(self):
        return "Multiple feeds found at %s: %s" % (self.uri, self.feeds)

class SubscriptionFeedNotFoundException(Exception):
    def __init__(self, uri): 
        self.uri = uri
    def __str__(self):
        return "No feeds found at %s" % (self.uri)

class SubscriptionNotFoundException(Exception):
    def __init__(self, id_or_uri): 
        self.id_or_uri = id_or_uri
    def __str__(self): return "No subscription found by id or uri %s" % \
        (self.id_or_uri)

