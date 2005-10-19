"""Simple-minded enclosure parser, looks for <enclosure/> elements."""
from sgmllib import SGMLParser

class EnclosureParser(SGMLParser):

    def parse(self, fn):
        """Parse an entry/feed, return a list of dicts of enclosures."""
        self.reset()
        self.feed(open(fn).read())
        return self._enclosures
        
    def reset(self):
        self._enclosures = []
        SGMLParser.reset(self)

    def start_enclosure(self, attrs_tuples):
        attrs = {}
        for n,v in attrs_tuples:
            # TODO: Decode more entities.  &amp; seems most common.
            v = v.replace('&amp;','&')
            attrs[n] = v
        self._enclosures.append(attrs)
