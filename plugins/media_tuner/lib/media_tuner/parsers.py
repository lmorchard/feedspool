from sgmllib import SGMLParser

def main():
    import sys, os.path, re
    fn = sys.argv[1]
    meta = FeedMetaParser().parse(fn)
    x, ignore          = os.path.split(fn)
    ignore, meta['fn'] = os.path.split(x)

    for k in ('title', 'link', 'fn'):
        try: 
            title = meta[k]
            break
        except KeyError: 
            pass
    
    fixed_title = re.sub('[^0-9A-Za-z.]+', '-', title)

    print 'TITLE: %s' % title
    print 'FIXED: %s' % fixed_title

    #print '\n'.join(['[%s]: %s' % (k,v.strip()) for k,v in meta.items()])

class FeedMetaParser(SGMLParser):
    """Very stupid feed metadata parser."""

    def parse(self, fn):
        self.reset()
        self.feed(open(fn).read())
        return self._meta

    def reset(self):
        SGMLParser.reset(self)
        self._meta  = {}
        self._data  = ''
        self._attrs = {}
        self._in_feed = False
        self._in_entry = False

    def unknown_starttag(self, tag, attrs):
        self._data = ''
        self._attrs = attrs

    def unknown_endtag(self, tag):
        if not self._in_entry: self._meta[tag] = self._data
        self._data = ''

    def start_entry(self, attrs): self._in_entry = True
    def end_entry(self): self._in_entry = False
    start_item = start_entry
    end_item   = end_entry

    def handle_data(self, data): self._data += data

    ENTITY_MAP = { 'lt':'<', 'gt':'>', 'quot':'"', 'amp':'&', 'apos':"'" }
    def handle_entityref(self, data):
        self._data += self.ENTITY_MAP.get(data, '?')

class EnclosureParser(SGMLParser):
    """Simple-minded enclosure parser, looks for <enclosure/> elements."""

    def parse(self, fn):
        """Parse an entry/feed, return a list of dicts of enclosures."""
        self.reset()
        self.feed(open(fn).read())
        return self._enclosures
        
    def reset(self):
        SGMLParser.reset(self)
        self._enclosures = []

    def start_enclosure(self, attrs_tuples):
        attrs = {}
        for n,v in attrs_tuples:
            # TODO: Decode more entities.  &amp; seems most common.
            v = v.replace('&amp;','&')
            attrs[n] = v
        self._enclosures.append(attrs)

if __name__ == "__main__": main()
