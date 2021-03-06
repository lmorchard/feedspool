"""
"""
import os, os.path, sys, logging, time
from md5 import md5
from StringIO import StringIO
import xml.sax, xml.sax.saxutils
from xml.sax.handler  import ContentHandler, feature_namespaces
from xml.sax.saxutils import XMLFilterBase, XMLGenerator, quoteattr
import feedspool
from feedspool import config

# TODO: Parse some things out for subscription metadata? (ie. feed title)
# TODO: Need entry directory hashing?  Time-based dirs?  Entry deduping probs.
# TODO: Allow for spooling into virtual filesystem databases

global log
log  = logging.getLogger("%s"%__name__)

class Spooler:
    """ """

    def __init__(self, subscription):
        """ """
        self.subscription = subscription
        self.new_entries  = []

    def spool(self):
        """ """
        sub  = self.subscription

        head_fn   = os.path.join(sub.path, config.FEED_HEAD_FN)
        head_fout = open(head_fn, 'w')
        head_xg   = XMLGenerator(head_fout)

        parser    = xml.sax.make_parser()
        spooler   = SpoolerFilter(parser, head_xg, sub,
            os.path.join(sub.path, config.ENTRIES_DIR) )

        fin  = open(sub.feed_fn, 'r')
        spooler.parse(fin)
        fin.close()

        head_fout.close()

        self.new_entries = spooler.new_entries
        self.all_entries = spooler.all_entries

    def getEntryPaths(self):
        """ """ 
        return self.all_entries, self.new_entries

    def getNewEntryPaths(self):
        """ """
        return self.new_entries

    def getAllEntryPaths(self):
        """ """
        return self.all_entries

class SpoolerFilter(XMLFilterBase):
    """SAX filter which chops a feed up into feed head and spooled entry
    documents."""

    # Supported known feed entry namespace / entry pairs.
    ENTRY_ELEMENTS = [
        ( 'http://my.netscape.com/rdf/simple/0.9/',  'item'  ),
        ( 'http://purl.org/rss/1.0/',                'item'  ),
        ( None,                                      'item'  ),
        ( 'http://purl.org/atom/ns#',                'entry' ),
        ( 'http://www.w3.org/2005/Atom',             'entry' ),
    ]

    def __init__(self, parent, head_xg, subscription, entries_root):
        XMLFilterBase.__init__(self, parent)
        
        self.log          = logging.getLogger("%s"%self.__class__.__name__)
        self.head_xg      = head_xg
        self.entries_root = entries_root
        self.subscription = subscription
        self.all_entries  = []
        self.new_entries  = []

        self.setFeature(feature_namespaces, True)
        self.setContentHandler(self.head_xg)

    def startElementNS(self, name, qname, attrs):
        """Filter element start, redirect to spooled entry file when start
        of an entry is detected."""
        # On start of a feed entry, redirect to entry spool file.
        if name in self.ENTRY_ELEMENTS:

            # Buffer the entry XML in a StringIO using our XMLGenerator.
            self.entry_fout = StringIO()
            self.entry_xg   = XMLGenerator(self.entry_fout)
            self.setContentHandler(self.entry_xg)

            # HACK: Since entry is a separate document, treat all parent
            # namespaces as undeclared.
            sub_maps = []
            for m in self.head_xg._ns_contexts:
                for uri, prefix in m.items():
                    p = (prefix, uri)
                    if p not in sub_maps: sub_maps.append(p)
            self.entry_xg._undeclared_ns_maps = sub_maps
        
        # Copy the feed/entry element start event.
        XMLFilterBase.startElementNS(self, name, qname, attrs)

    def endElementNS(self, name, qname):
        """Filter element end, finish spooling entry when it ends."""
        # Copy the feed/entry element end event.
        XMLFilterBase.endElementNS(self, name, qname)

        # On end of a feed entry, save the entry and return to feed head.
        if name in self.ENTRY_ELEMENTS:

            # Get a hash of the entry's contents.
            entry_src  = self.entry_fout.getvalue()
            entry_hash = md5(entry_src).hexdigest()

            # Build a time-based directory structure for entries.
            #tt = time.gmtime()
            #entry_path = os.path.join(self.entries_root,
            #    '%04d' % tt[0], '%02d' % tt[1], '%02d' % tt[2])
            
            # Build a flat directory structure for entries
            entry_path = self.entries_root
            if not os.path.isdir(entry_path):
                os.makedirs(entry_path, 0777)

            # Write out the entry data to a spool file, with hash-based name.
            entry_fn = os.path.join(entry_path, config.ENTRY_FN_TMPL % entry_hash)
            self.all_entries.append(entry_fn)
            if not os.path.exists(entry_fn):
                entry_fout = open(entry_fn, 'w')
                entry_fout.write(entry_src)
                entry_fout.close()
                self.new_entries.append(entry_fn)

            # Resume writing to feed head file.
            self.setContentHandler(self.head_xg)

class XMLGenerator(xml.sax.saxutils.XMLGenerator):
    """XMLGenerator subclass to fix a few namespace-related bugs."""

    def _write(self, string):
        self._out.write(string)

    def startDocument(self):
        self._current_context[u'http://www.w3.org/XML/1998/namespace'] = "xml"
        xml.sax.saxutils.XMLGenerator.startDocument(self)

    def startElementNS(self, name, qname, attrs):
        if self._current_context.get(name[0], None) is None:
            name = name[1]
        else:
            name = self._current_context[name[0]] + ":" + name[1]
        self._write('<' + name)

        for pair in self._undeclared_ns_maps:
            if pair[0] is None:
                self._write(' xmlns="%s"' % pair[1])
            else:
                self._write(' xmlns:%s="%s"' % pair)
        self._undeclared_ns_maps = []

        for (name, value) in attrs.items():
            if self._current_context.get(name[0], None) is None:
                name = name[1]
            else:
                name = self._current_context[name[0]] + ":" + name[1]
            self._write(' %s=%s' % (name, quoteattr(value)))

        self._write('>')

    def endElementNS(self, name, qname):
        if self._current_context.get(name[0], None) is None:
            name = name[1]
        else:
            name = self._current_context[name[0]] + ":" + name[1]
        self._write('</%s>' % name)

