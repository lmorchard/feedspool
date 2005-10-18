"""This plugin provides feed enclosure download support, with HTTP and 
BitTorrent downloaders available.
"""
import sys, os, os.path, logging, urllib2, time
from urlparse  import urlparse
from sgmllib   import SGMLParser
from feedspool import config
from feedspool.plugins import Plugin

from ThreadedJobQueue import JobQueue, Job

THREAD_POOL_SIZE = 5
MAX_DOWNLOADS    = 3
DOWNLOADS_PATH   = "downloads"

class MediaTunerPlugin(Plugin):

    def scan_start(self):
        """Start up the downloader job queue at the start of a scan."""
        pool_size = self.get_config("job_queue_size", THREAD_POOL_SIZE)
        self.job_queue = JobQueue(pool_size)

    def feed_new_entries(self, subscription, new_entries, all_entries):
        """On new entries, scan for enclosures and schedule downloads."""
        # Work out the destination path for downloads.
        dest_path = self.get_config("download_path", DOWNLOADS_PATH)
        if not dest_path.startswith('/'):
            dest_path = os.path.join(self.plugin_root, dest_path)

        # How many downloads per scan should be picked up.
        max_downloads = self.get_config("max_scan_downloads", MAX_DOWNLOADS)
        
        # Parse for enclosures in the new feed entries.
        enclosures, parser = [], EnclosureParser()
        for entry_fn in new_entries:
            enclosures.extend(parser.parse(entry_fn))
        
        # Build a list of downloader jobs based on the enclosures found.
        # TODO: Should limit enclosures in date order?
        jobs = []
        for e in enclosures[:max_downloads]:
            url    = e['url']
            #dl_cls = NullDownloader
            dl_cls = HTTPDownloader
            jobs.append(Job(url, dl_cls().downloadURL, dest_path, url))

        # If there were any jobs, queue them and note the downloads.
        if jobs: 
            self.job_queue.queueJobs(jobs)
            self.log.info("Found %s enclosures, downloading %s at max." % \
                (len(enclosures), max_downloads))

    def scan_end(self):
        """Signal the job queue to stop when empty at the end of a scan."""
        self.job_queue.setStopWhenEmpty(True)

class EnclosureParser(SGMLParser):
    """Simple-minded enclosure parser, looks for <enclosure/> elements."""

    def parse(self, fn):
        """Parse an entry/feed, return a list of dicts of enclosures."""
        self.reset()
        self.feed(open(fn).read())
        return self._enclosures
        
    def reset(self):
        self._enclosures = []
        SGMLParser.reset(self)

    def start_enclosure(self, attrs_tuples):
        attrs = dict(attrs_tuples)
        self._enclosures.append(attrs)
    
import random
class NullDownloader:
    """This is a testing downloader which does nothing but waste time."""

    def __init__(self):
        random.seed()
        self.log  = logging.getLogger("%s"%self.__class__.__name__)

    def downloadURL(self, dest_path, url):
        self.log.debug("Pretending to download %s to %s" % (url, dest_path))
        for x in range(20):
            self.log.info("%s%% of %s downloaded (but not really)" % (x*5, url))
            time.sleep(5 * random.random())

class HTTPDownloader:
    """This provides an HTTP content downloader."""
    PERC_STEP  = 5
    CHUNK_SIZE = 10*1024
    
    def __init__(self):
        self.log  = logging.getLogger("%s"%self.__class__.__name__)

    def downloadURL(self, dest_path, url):
        """Given a destination path and URL, download with a progress indicator."""
        files = []
        
        # Dissect the given URL to extract a filename, build output path.
        url_path  = urlparse(url)[2]
        url_fn    = os.path.basename(url_path)
        fout_path = os.path.join(dest_path, url_fn)
        files.append(fout_path)
        
        # Open the file for writing, initialize size to 0.
        fout      = open(fout_path, "w")
        fout_size = 0
        
        # Open the URL for reading, try getting the content length.
        fin          = urllib2.urlopen(url)
        fin_size_str = fin.headers.getheader("Content-Length", "-1")
        fin_size     = int(fin_size_str.split(";",1)[0])
        self.log.info("Downloading %s to %s (%s bytes)" % \
            (url, fout_path, fin_size))
        
        # Initialize variables tracking download progress
        perc_step, perc, next_perc = self.PERC_STEP, 0, 0
        perc_chunk = fin_size / (100/self.PERC_STEP) 
        
        while True:
            # Read in a chunk of data, breaking from loop if 
            # no data returned
            data = fin.read(self.CHUNK_SIZE)
            if len(data) == 0: break
            
            # Write a chunk of data, incrementing output file size
            fout.write(data)
            fout_size += len(data)
             
            # If the current output size has exceeded the next
            while fin_size > 0 and fout_size >= next_perc:
                self.log.info("%s%% of %s downloaded (%s of %s bytes)" % \
                    (perc, url, fout_size, fin_size))
                perc      += perc_step
                next_perc += perc_chunk
            
        # Close input & output, line break at the end of progress.
        fout.close()
        fin.close()

        return files
 
