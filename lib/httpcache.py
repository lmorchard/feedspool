"""httpcache

A caching http interface that supports ETags and gzip
to conserve bandwidth. All of the headers and the content
at that URL are cached for quick retrieval later.
ETags are supported for doing a conditional GET, which
only retrieves the content when it has really changed.

Direction for use:

            cache = HTTPCache('http://127.0.0.1/testContent.xml')
            content = cache.content()

The 'content' is the content retrieved from the URL.
            
            info = cache.info()

The 'info' returned is an rfc822 Message object for
reading rfc822 headers. Note that this object
is only useful for reading only. If you want to add
new headers and have them updated in the cache you
will need to call 'add_headers()'

            cache.add_headers({"md5" : "03030eeeef33, 2034023feef, 23493208903"})

Requires Python 2.2 or later
"""

__author__ = "Joe Gregorio (joe@bitworking.org)"
__copyright__ = "Copyright 2004, Joe Gregorio"
__contributors__ = ["Kendall Clark", "Beat Bolli"]
__version__ = "1.0.2 $Rev: 33 $"
__license__ = "MIT"
__history__ = """
"""

import os, md5, urllib2, rfc822, StringIO, gzip

cacheSubDir__ = ".cache"

if not os.path.exists(cacheSubDir__):
    os.mkdir(cacheSubDir__)

class HTTPCache:
    """Represents a single cached URL"""
   
    def __init__(self, url, headers={}):
        self.info_ = None
        self.content_ = None
        self.fresh_ = False
        self.url_ = url
        #Create a non-clashing name for each url in the cache.
        digest = md5.new(url).digest()
        cacheFileName = "".join(["%02x" % (ord(c),) for c in digest])
        self.cacheFullPath_ = os.path.join(cacheSubDir__, cacheFileName)
	self.headers_ = {"Accept-Encoding": "gzip"}
	self.headers_.update(headers)
	
    
        if (os.path.exists(self.cacheFullPath_)):
            # Load up the cached version and use it's 'ETag' header value, if it exists.
            f = file(self.cacheFullPath_, "r")
            self.info_ = rfc822.Message(f)
            f.seek(0)
            self.content_ = f.read().split('\n\n', 1)[1]
            f.close()
            request = urllib2.Request(url, None, self.headers_)
            if self.info_.has_key('ETag'):
                request.add_header("If-None-Match", self.info_['ETag'])
            
            try:
                response = urllib2.urlopen(request)
            except urllib2.HTTPError, e:
                if (304 == e.code):
                    self.fresh_ = True
                else:
                    raise urllib2.HTTPError, e
            else:
                info = response.info()
                for key in info.keys():
                    self.info_[key] = info[key]
                self.content_ = self._writeContent(self.info_, response)
                
        else:
            # There isn't a cached version of this URL yet.
            request = urllib2.Request(url, None, self.headers_)
            response = urllib2.urlopen(request)
            response.info()['Url'] = url
            self.content_ = self._writeContent(response.info(), response)
            self.info_ = response.info()

    def content(self):
        """Get the content as a single string."""
        return self.content_

    def filename(self):
         """Get the full path file name of the cached file."""
         return self.cacheFullPath_
 
    def fresh(self):
         """Get the state of the cache; if true, the cached copy is
         fresh; if false, it's stale."""
         return self.fresh_

    def info(self):
        """Returns and rfc822.Message for manipulating headers.
        
        Note that you can use this to read headers but not
        to add or change headers. Use the 'add_headers()' for
        adding/changing header values permanently in the cache."""
        return self.info_

    def add_headers(self, headers):
        """Add/change header values in the cache.

        Note that if the key/value pair you change is used
        by HTTP then you risk the possibility that the value
        will be over-written the next time content is retrieved
        from that URL.
        """
        for key in headers.keys():
            self.info_[key] = headers[key]
        f = file(self.cacheFullPath_, "w")
        f.write(str(self.info_))
        f.write("\n")
        f.write(self.content_)
        f.close()

    def _writeContent(self, info, response):
        f = file(self.cacheFullPath_, "w")
        f.write(str(info))
        f.write("\n")
        content = ""

        if response.info().get('content-encoding', None) == 'gzip':
            import StringIO
            zip_content = response.read()
            try:
                content = gzip.GzipFile(fileobj=StringIO.StringIO(zip_content)).read()
            except IOError, e:
                if str(e) == "Not a gzipped file":
                    content = zip_content
                else:
                    raise
            f.write(content)
        else:
            content = response.read()
            f.write(content)
        f.close()
        return content
    
if __name__ == '__main__':
    # To run these unit tests you should have a web server installed on the local machine.
    # Alter rootPath to point to the location of the root directory for said server.
    import unittest

    rootPath = 'c:/Apache/Apache2/htdocs'

    def clearCache():
        [os.unlink(os.path.join(cacheSubDir__, name)) for name in os.listdir(cacheSubDir__)]

    def writeTargetFile():
        f = file(os.path.join(rootPath, 'testContent.xml'), "w")
        f.write("""<rss><channel><item></item></channel></rss>""")
        f.close()

    def writeTargetFileAlternate():
        f = file(os.path.join(rootPath, 'testContent.xml'), "w")
        f.write("""<rss></rss>""")
        f.close()

    class BasicTest(unittest.TestCase):
        def testCreation(self):
            clearCache()
            writeTargetFile()
            cache = HTTPCache('http://127.0.0.1/testContent.xml')
            content = cache.content()
            info = cache.info()
            self.assertEqual(info['Url'], 'http://127.0.0.1/testContent.xml')
            self.assertEqual(cache.filename(), ".cache\827456fdc98606d568b6f03e09168738")
            fileNames = os.listdir(cacheSubDir__)
            self.assertEqual(len(fileNames), 1)            
            f = file(os.path.join(cacheSubDir__, fileNames[0]), "r")
            orig_content = f.read()
            self.assertNotEqual(orig_content.find('Url: http://127.0.0.1/testContent.xml'), -1)
            f.close()
            
        def testCachedGet(self):
            clearCache()
            writeTargetFile()
            cache0 = HTTPCache('http://127.0.0.1/testContent.xml')
            cache = HTTPCache('http://127.0.0.1/testContent.xml')
            self.assertEqual(cache0.fresh(), False)
            self.assertEqual(cache.fresh(), True)
            content = cache.content()
            info = cache.info()
            self.assertEqual(info['Url'], 'http://127.0.0.1/testContent.xml')
            

        def testChangedGet(self):
            clearCache()
            writeTargetFile()
            cache = HTTPCache('http://127.0.0.1/testContent.xml')
            content = cache.content()
            info = cache.info()
            self.assertEqual(info['Url'], 'http://127.0.0.1/testContent.xml')
            writeTargetFileAlternate()
            cache2 = HTTPCache('http://127.0.0.1/testContent.xml')
            content2 = cache2.content()
            info2 = cache2.info()
            self.assertNotEqual(content, content2)
            self.assertEqual("""<rss></rss>""", content2)
            
        def testPreserveChangedHeader(self):
            """Add a new header to a cached file. Then do a pull
            where the content has been updating, the new cached
            file should still contain the old added header."""
            clearCache()
            writeTargetFile()
            cache = HTTPCache('http://127.0.0.1/testContent.xml')
            content = cache.content()
            info = cache.info()
            self.assertEqual(info['Url'], 'http://127.0.0.1/testContent.xml')
            cache.add_headers({"md5" : "03030eeeef33, 2034023feef, 23493208903"})
            writeTargetFileAlternate()
            cache2 = HTTPCache('http://127.0.0.1/testContent.xml')
            content2 = cache2.content()
            info2 = cache2.info()
            self.assertNotEqual(content, content2)
            self.assertEqual("""<rss></rss>""", content2)
            self.assertEqual(info2['md5'], "03030eeeef33, 2034023feef, 23493208903")

        def testVeryLastCachedGetZip(self):
            clearCache()
            writeTargetFile()
            cache = HTTPCache('http://diveintomark.org/')
            content = cache.content()
            info = cache.info()
            self.assertEqual(info['Url'], 'http://diveintomark.org/')
            self.assertEqual(info['content-encoding'], 'gzip')

    unittest.main()		
    
    







