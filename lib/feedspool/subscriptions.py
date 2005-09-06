"""
"""
import sys, os, os.path, time, logging, traceback, feedfinder
from datetime import datetime, timedelta
from timezones import utc
import isodate
from email.Message import Message
from email.Parser import Parser
from email.Utils import formatdate, parsedate
from httpcache import HTTPCache
from md5 import md5
from cStringIO import StringIO
import feedspool, opml
from feedspool import config
from feedspool.spooler import Spooler
from TimeRotatingFileHandler import TimeRotatingFileHandler

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

        self.uri     = uri
        self.uid     = md5(uri).hexdigest()
        self.path    = os.path.join(self.spool_path, self.uid)
        self.feed_fn = os.path.join(self.path, 'feed.xml')

        self.log_debug_hnd = None
        self.log_hnd       = None

        self.loadMeta()

    def loadMeta(self):
        """Load up the subscription's metadata."""
        self.meta_fn = os.path.join(self.path, 'meta')
        if os.path.isfile(self.meta_fn):
            # Load up the metadata for the subscription.
            self.meta = Parser().parse(open(self.meta_fn, 'r'))
        else:
            # Initialize new metadata if none found.
            self.log.debug("Initializing metadata for %s" % self.uri)
            self.meta = Message()

            # Set some basic metadata values
            self.meta['URI'] = self.uri
            self.meta['UID'] = self.uid

            # Set the beginning datestamps.
            self.meta['Last-Scanned']  = ISO_NEVER
            self.meta['Last-Polled']   = ISO_NEVER
            self.meta['Next-Poll']     = ISO_NEVER
            self.meta['Last-Updated']  = ISO_NEVER

            # Set the default scanning parameters.
            self.meta['Current-Update-Period'] = "600"
            self.meta['Update-Ramp-Up-Factor'] = \
                config.alt('scan', 'update_ramp_up_factor', '0.5')
            self.meta['Update-Back-Off-Period'] = \
                config.alt('scan', 'update_back_off_period', '1800')
            self.meta['Min-Update-Period'] = \
                config.alt('scan', 'min_update_period', '3600')
            self.meta['Max-Update-Period'] = \
                config.alt('scan', 'max_update_period', '86400')

    def save(self):
        """Save changes to the subscription."""
        # Create the subscription spool dir if not found.
        if not os.path.isdir(self.path):
            log.debug("Creating new subscription spool path: %s" % self.path)
            os.mkdir(self.path, 0777)
            os.mkdir(os.path.join(self.path, 'entries'), 0777)

        # Save the subscription metadata
        open(self.meta_fn, 'w').write(self.meta.as_string())

    def scan(self):
        """Scan the subscribed feed for any updates, spool new entries."""
        self.startLogging()
        self.save() # HACK: Pre-save to ensure directories created

        try:
            # Bump the last scan timestamp.
            now = now_ISO()
            self['Last-Scanned'] = now

            # Is it time for the next poll?
            if now > self['Next-Poll']:
                self['Last-Polled'] = now
                self.log.debug("Polling %s" % self.uri)

                found_new_entries = False
                try:
                    # Has the feed content changed?
                    if self.fetch():

                        # Spool the entries found in the feed.
                        self.log.debug("\tSpooling entries.")
                        spooler = Spooler(self)
                        spooler.spool()

                        # If found new entries, flip the flag.
                        new_entries = spooler.getNewEntryPaths()
                        if len(new_entries) > 0:
                            found_new_entries = True
                            self.log.debug("\tFound %s new entries." % \
                                len(new_entries))

                except KeyboardInterrupt: raise
                except Exception, e:
                    self.log.exception("Problem while polling %s" % self.uri)

                # Tweak the update period and schedule the next poll.
                update_period = self.updatePollingPeriod(found_new_entries)
                self.scheduleNextPoll()

        finally:
            # Save any changes to the subscription, stop logging.
            self.save()
            self.stopLogging()

    def fetch(self):
        """Fetch the data for the feed, return whether feed has changed."""
        # Grab the feed data via HTTPCache
        cache     = HTTPCache(self.uri)
        info      = cache.info()
        content   = cache.content()
        feed_hash = md5(content).hexdigest()

        # Copy over some HTTP headers as feed metadata
        if 'ETag' in info: 
            self['HTTP-ETag'] = info['ETag']
        if 'Last-Modified' in info:
            self['HTTP-Last-Modified'] = info['Last-Modified']

        #changed = cache.fresh()
        changed = (not feed_hash == self['Last-Feed-MD5'])
        if changed:
            # Update the feed hash, write the fetched feed.
            self['Last-Feed-MD5'] = feed_hash
            fout = open(self.feed_fn, 'w')
            fout.write(content)
            fout.close()

        return changed

    def updatePollingPeriod(self, found_new_entries):
        """Update the polling period, based on finding new entries."""
        update_period = int(self['Current-Update-Period'])

        if found_new_entries:
            # If there were new entries, try ramping up the update freq.
            ramp_up_factor    = float(self['Update-Ramp-Up-Factor'])
            new_update_period = int(update_period * ramp_up_factor)

        else:
            # If there weren't new entries, try backing off the update freq.
            back_off_period   = float(self['Update-Back-Off-Period'])
            new_update_period = int(update_period + back_off_period)

        # Constrain the new update period to the min/max range.
        min_period = int(self['Min-Update-Period'])
        max_period = int(self['Max-Update-Period'])
        update_period = \
            max(min_period, min(max_period, new_update_period))

        # Save the new period and return the value.
        self['Current-Update-Period'] = str(update_period)
        return update_period

    def scheduleNextPoll(self):
        """Schedule the next future poll based on update period."""
        update_period = int(self['Current-Update-Period'])
        next_poll = now_datetime() + timedelta(seconds=update_period)
        self['Next-Poll'] = datetime2ISO(next_poll)

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

    # HACK: Somewhat dirty way to pass through mapping interface for meta
    def __setitem__(self, name, val): 
        del self.meta[name]
        self.meta[name] = val
    def __getitem__(self, name): return self.meta.__getitem__(name)
    def __delitem__(self, name): return self.meta.__delitem__(name)

    def __len__(self, name): return self.meta.__len__()
    def __contains__(self, name): return self.meta.__contains__(name)
    def has_key(self, name): return self.meta.has_key(name)
    def keys(self): return self.meta.keys()
    def values(self): return self.meta.values()
    def items(self): return self.meta.items()
    def get(self, name, default): return self.meta.get(name, default)

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

    def add(self, uri, find_feed=True):
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
        sub.save()
        self.subs.append(sub)

    def remove(self, uri):
        """Remove a subscription to a feed."""
        if not uri in self.listURIs():
            raise SubscriptionNotFoundException(uri)
        doomed_subs = [ x for x in self.subs if x.uri == uri ]
        for x in doomed_subs: self.subs.remove(x)

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

    def OPMLimport(self, file=sys.stdin, find_feeds=False):
        """Import subscriptions from an OPML file."""
        new_items = []
        for item in opml.read(file):
            self._importuri(item.xmlurl, find_feeds)

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

    def OPMLexport(self, file=sys.stdout):
        """Import subscriptions to an OPML file."""
        subs = self.subs

        op = opml.OPML()
        op['title'] = "Subscriptions"

        for sub in subs:
            feed = sub.feed

            o = opml.Outline()
            o['text']        = feed.title
            o['description'] = feed.description
            o['language']    = feed.language
            o['title']       = feed.title
            o['type']        = feed.format
            o['xmlurl']      = feed.uri

            #xd = XPathDict(xml=feed.xml)
            #link_nodes = xd.nodes("/a:feed/a:link[@type='text/html']")
            #if len(link_nodes) > 0:
            #    o['htmluri'] = link_nodes[0].prop('href')

            op.outlines.append(o)

        file.write('<?xml version="1.0"?>\n')
        op.output(file)

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

