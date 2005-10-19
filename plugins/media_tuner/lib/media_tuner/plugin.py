"""This plugin provides feed enclosure download support, with HTTP and 
BitTorrent downloaders available.
"""
import sys, os, os.path, logging, time, re
from feedspool import config
from feedspool.plugins import Plugin

from ThreadedJobQueue import JobQueue, Job

from parsers import FeedMetaParser, EnclosureParser
from downloaders import NullDownloader, HTTPDownloader

try:
    from downloaders import BitTorrentDownloader
except ImportError:
    from downloaders import HTTPDownloader as BitTorrentDownloader

class MediaTunerPlugin(Plugin):

    DOWNLOADER_POOL_SIZE = 7
    SHUTDOWN_WAIT        = 10.0
    MAX_DOWNLOADS        = 3
    DOWNLOADS_PATH       = "downloads"

    def startup(self):
        self.job_queue = None

    def scan_start(self):
        """Start up the downloader job queue at the start of a scan."""
        pool_size = self.get_config("job_queue_size", self.DOWNLOADER_POOL_SIZE)
        self.job_queue = JobQueue(pool_size)

    def feed_new_entries(self, subscription, new_entries, all_entries):
        """On new entries, scan for enclosures and schedule downloads."""
        # Come up with a sub-path for this feed's media downloads
        # TODO: Make feed title based download paths an option?  Per-feed config?
        feed_meta = FeedMetaParser().parse(subscription.head_fn)
        feed_meta['uid'] = subscription.uid
        for k in ('title', 'link', 'uid'):
            try: 
                title = feed_meta[k]
                break
            except KeyError: 
                pass
        title_path = re.sub('[^0-9A-Za-z.]+', '-', title)

        # Work out the destination path for downloads.
        dest_path = self.get_config("download_path", self.DOWNLOADS_PATH)
        dest_path = os.path.join(dest_path, title_path)
        if not dest_path.startswith('/'):
            dest_path = os.path.join(self.plugin_root, dest_path)

        # Create download path, if necessary.
        if not os.path.isdir(dest_path): os.makedirs(dest_path)

        # How many downloads per scan should be picked up.
        max_downloads = self.get_config_int("max_scan_downloads", self.MAX_DOWNLOADS)
        
        # Parse for enclosures in the new feed entries.
        enclosures, parser = [], EnclosureParser()
        for entry_fn in new_entries:
            enclosures.extend(parser.parse(entry_fn))
        
        # Build and queue up downloader jobs based on the enclosures found.
        # TODO: Should limit enclosures in date order?
        if enclosures:
            self.log.info("Found %s enclosures, downloading %s at max." % \
                (len(enclosures), max_downloads))
            for e in enclosures[:max_downloads]:
                url = e['url']
                if e.get('type','') == "application/x-bittorrent" or \
                   url.endswith('.torrent'):
                    dl = BitTorrentDownloader()
                else:
                    dl = HTTPDownloader()
                #dl  = NullDownloader()
                job = Job(url, dl.downloadURL, dest_path, url)
                self.job_queue.append(job)

    def scan_end(self):
        """Signal the job queue to stop when empty at the end of a scan."""
        self.job_queue.setStopWhenEmpty(True)
    
    def shutdown(self):
        """At shutdown, hang out until the job queue has finished."""
        if self.job_queue:
            self.log.info("Waiting for download queue to finish.")
            while self.job_queue.isAlive(): 
                self.log.debug("Still waiting for download queue to finish.")
                time.sleep(self.SHUTDOWN_WAIT)    

