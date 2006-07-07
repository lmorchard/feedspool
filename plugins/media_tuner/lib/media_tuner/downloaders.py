""" """
import sys, os, os.path, logging, urllib2, time
from urlparse import urlparse
    
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
 
# HACK: This plugin should work without BitTorrent installed.  But, just 
# in case it is, the following will define a downloader which uses it.
try:
    # This code is liberally lifted from bittorrent-console.py
    # TODO: Work on much simplifying this stuff
    # TODO: Control seeding time / total xfer

    import threading, thread
    from time import time, strftime
    from cStringIO import StringIO
    from BitTorrent.download import Feedback, Multitorrent
    from BitTorrent.defaultargs import get_defaults
    from BitTorrent.parseargs import printHelp
    from BitTorrent.zurllib import urlopen
    from BitTorrent.bencode import bdecode
    from BitTorrent.ConvertedMetainfo import ConvertedMetainfo
    from BitTorrent.prefs import Preferences
    from BitTorrent import configfile
    from BitTorrent import BTFailure
    from BitTorrent import version
    from BitTorrent import GetTorrent

    class BitTorrentDownloader:
        """This provides a BitTorrent-based content downloader."""
    
        def __init__(self):
            self.log  = logging.getLogger("%s"%self.__class__.__name__)

        def downloadURL(self, dest_path, url):
            uiname   = 'bittorrent-console'
            defaults = get_defaults(uiname)
            
            # TODO: Bring these in from the plugin's config?
            config_in  = {
                'save_in':                  dest_path,
                'display_interval':         10,
                'max_upload_rate':          8,
                'start_trackerless_client': True,
                'spew':                     False,
                'max_startup_wait':         2 * 60
            }

            try:
                config, args = configfile.parse_configuration_and_args\
                        (defaults, uiname, [], 0, 0)

                config.update(config_in)
                
                metainfo, errors = GetTorrent.get(url)
                if errors:
                    raise BTFailure(_("Error reading .torrent file: ") +\
                        '\n'.join(errors))

            except BTFailure, e:
                self.log.exception("Problem initializing torrent")
                return []

            dl = DL(metainfo, config)
            dl.run()

    class HeadlessDisplayer(object):

        def __init__(self, doneflag):
            self.log  = logging.getLogger("%s"%self.__class__.__name__)
            self.doneflag = doneflag

            self.done = False
            self.percentDone = ''
            self.timeEst = ''
            self.downRate = '---'
            self.upRate = '---'
            self.shareRating = ''
            self.seedStatus = ''
            self.peerStatus = ''
            self.errors = []
            self.file = ''
            self.downloadTo = ''
            self.fileSize = ''
            self.numpieces = 0

        def set_torrent_values(self, name, path, size, numpieces):
            self.file = name
            self.downloadTo = path
            self.fileSize = fmtsize(size)
            self.numpieces = numpieces

        def finished(self):
            self.done = True
            self.downRate = '---'
            self.display({'activity':_("download succeeded"), 'fractionDone':1})

        def error(self, errormsg):
            newerrmsg = strftime('[%H:%M:%S] ') + errormsg
            self.errors.append(newerrmsg)
            self.display({})

        def display(self, statistics):
            fractionDone = statistics.get('fractionDone')
            activity = statistics.get('activity')
            timeEst = statistics.get('timeEst')
            downRate = statistics.get('downRate')
            upRate = statistics.get('upRate')
            spew = statistics.get('spew')

            if timeEst is not None:
                self.timeEst = fmttime(timeEst)
            elif activity is not None:
                self.timeEst = activity

            if fractionDone is not None:
                self.percentDone = str(int(fractionDone * 1000) / 10)
            if downRate is not None:
                self.downRate = '%.1f KB/s' % (downRate / (1 << 10))
            if upRate is not None:
                self.upRate = '%.1f KB/s' % (upRate / (1 << 10))
            
            downTotal = statistics.get('downTotal')
            if downTotal is not None:
                upTotal = statistics['upTotal']
                if downTotal <= upTotal / 100:
                    self.shareRating = _("oo  (%.1f MB up / %.1f MB down)") % (
                        upTotal / (1<<20), downTotal / (1<<20))
                else:
                    self.shareRating = _("%.3f  (%.1f MB up / %.1f MB down)") % (
                       upTotal / downTotal, upTotal / (1<<20), downTotal / (1<<20))
                numCopies = statistics['numCopies']
                nextCopies = ', '.join(["%d:%.1f%%" % (a,int(b*1000)/10) for a,b in
                        zip(xrange(numCopies+1, 1000), statistics['numCopyList'])])
                if not self.done:
                    self.seedStatus = _("%d seen now, plus %d distributed copies "
                                        "(%s)") % (statistics['numSeeds' ],
                                                   statistics['numCopies'],
                                                   nextCopies)
                else:
                    self.seedStatus = _("%d distributed copies (next: %s)") % (
                        statistics['numCopies'], nextCopies)
                self.peerStatus = _("%d seen now") % statistics['numPeers']

            for err in self.errors[-4:]:
                self.log.error("Torrent error: %s" % err)

            out = {
                'file'        :self.file,
                'fileSize'    :self.fileSize,
                'percentDone' :self.percentDone,
                'timeEst'     :self.timeEst,
                'downloadTo'  :self.downloadTo,
                'downRate'    :self.downRate,
                'upRate'      :self.upRate,
                'shareRating' :self.shareRating,
                'seedStatus'  :self.seedStatus,
                'peerStatus'  :self.peerStatus,
            }

            msg = \
                "%(percentDone)s%% of %(file)s downloaded " +\
                "(%(timeEst)s) (d:%(downRate)s) (u:%(upRate)s) " +\
                "(seeds:%(seedStatus)s) (peers:%(peerStatus)s)"

            self.log.info(msg % out)

    class DL(Feedback):

        def __init__(self, metainfo, config):
            self.log      = logging.getLogger("%s"%self.__class__.__name__)
            self.doneflag = threading.Event()
            self.metainfo = metainfo
            self.config   = Preferences().initWithDict(config)
            self.started_downloading = False

        def run(self):
            self.d = HeadlessDisplayer(self.doneflag)
            try:
                self.multitorrent = Multitorrent(self.config, self.doneflag,
                                                 self.global_error)
                # raises BTFailure if bad
                metainfo = ConvertedMetainfo(bdecode(self.metainfo))
                torrent_name = metainfo.name_fs
                saveas = os.path.join(self.config['save_in'], torrent_name)

                self.d.set_torrent_values(metainfo.name, os.path.abspath(saveas),
                                    metainfo.total_bytes, len(metainfo.hashes))
                self.torrent = self.multitorrent.start_torrent(metainfo,
                                    Preferences(self.config), self, saveas)
            except BTFailure, e:
                self.log.exception("Problem running torrent")
                return

            self.get_status()
            #self.multitorrent.rawserver.install_sigint_handler()
            #self.multitorrent.rawserver.listen_forever()
            start_time = time()
            ret = 0
            rsvr = self.multitorrent.rawserver
            while not rsvr.doneflag.isSet() and not ret:
                ret = rsvr.listen_once()
                if not self.started_downloading and \
                        (time()-start_time) > self.config['max_startup_wait']:
                    self.log.info("Torrent took too long to start downloading")
                    break

            self.d.display({'activity':_("shutting down"), 'fractionDone':0})
            self.torrent.shutdown()

        def get_status(self):
            self.multitorrent.rawserver.add_task\
                (self.get_status, self.config['display_interval'])
            status = self.torrent.get_status(self.config['spew'])
            if not self.started_downloading and status.get('downRate',0) > 0:
                self.started_downloading = True
            self.d.display(status)

        def global_error(self, level, text):    self.d.error(text)
        def error(self, torrent, level, text):  self.d.error(text)
        def failed(self, torrent, is_external): self.doneflag.set()
        def finished(self, torrent):            self.d.finished()

    def fmttime(n):
        if n == 0:
            return _("download complete!")
        try:
            n = int(n)
            assert n >= 0 and n < 5184000  # 60 days
        except:
            return _("<unknown>")
        m, s = divmod(n, 60)
        h, m = divmod(m, 60)
        return _("finishing in %d:%02d:%02d") % (h, m, s)

    def fmtsize(n):
        s = str(n)
        size = s[-3:]
        while len(s) > 3:
            s = s[:-3]
            size = '%s,%s' % (s[-3:], size)
        if n > 999:
            unit = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']
            i = 1
            while i + 1 < len(unit) and (n >> 10) >= 999:
                i += 1
                n >>= 10
            n /= (1 << 10)
            size = '%s (%.0f %s)' % (size, n, unit[i])
        return size

except ImportError:
    # Be sure *only* to ignore import errors, everything else should squawk.
    pass

def main():
    """Try out a downloader."""
    logging.basicConfig(level=logging.DEBUG, 
        format='[%(thread)12d %(levelname)7s:%(name)-12s] %(message)s')
    global log
    log = logging.getLogger("main")
    
    dest_path, url, dl_name = sys.argv[1], sys.argv[2], sys.argv[3]
    
    if   dl_name == 'http': dl = HTTPDownloader()
    elif dl_name == 'bt':   dl = BitTorrentDownloader()
    else:                   dl = NullDownloader()
    
    dl.downloadURL(dest_path, url)

# Fire off the main testing function if run as a script.
if __name__=="__main__": main()
