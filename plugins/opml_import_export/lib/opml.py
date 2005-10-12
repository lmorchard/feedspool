"""
This handles import and export of feeds in OPML format.
This was liberally borrowed from the Gnome Straw aggregator.
"""

# $Header: /cvsroot/feedspool/lib/feedspool/opml.py,v 1.3 2004/08/31 00:50:12 deusx Exp $

import sys, time, logging, pickle, traceback
from datetime import datetime

from xml.sax import saxutils, make_parser, SAXParseException
from xml.sax.handler import feature_namespaces, feature_namespace_prefixes
from xml.sax.saxutils import XMLGenerator
from xml.sax.xmlreader import AttributesImpl
from StringIO import StringIO
import xml.sax._exceptions
import xml.sax.handler

global log
log = logging.getLogger("%s"%__name__)
    
class OPML(dict):
    def __init__(self):
        self.outlines = []
    
    def output(self, stream = sys.stdout):
        xg = XMLGenerator(stream, encoding='utf-8')
        def elemWithContent(name, content):
            xg.startElement(name, AttributesImpl({}))
            if content is not None:
                xg.characters(content)
            xg.endElement(name)
        xg.startElement("opml", AttributesImpl({'version': '1.1'}))
        xg.characters("\n")
        xg.startElement("head", AttributesImpl({}))
        for key in ('title', 'dateCreated', 'dateModified', 'ownerName',
                    'ownerEmail', 'expansionState', 'vertScrollState',
                    'windowTop', 'windowBotton', 'windowRight', 'windowLeft'):
            if self.has_key(key) and self[key] != "":
                elemWithContent(key, self[key])
        xg.endElement("head")
        xg.characters("\n")
        xg.startElement("body", AttributesImpl({}))
        for o in self.outlines:
            o.output(xg)

        xg.characters("\n")
        xg.endElement("body")
        xg.characters("\n")
        xg.endElement("opml")
        xg.characters("\n")

class Outline(dict):
    __slots__ = ('_children')
    
    encoding='utf-8'

    def __init__(self):
        self._children = []

    def add_child(self, outline):
        self._children.append(outline)

    def get_children_iter(self):
        return self.OIterator(self)

    children = property(get_children_iter, None, None, "")

    def output(self, xg):
        xg.characters("\n")

        attr = dict( [ (k, self[k].encode(self.encoding, 'xmlcharrefreplace'))
                       for k in self.keys() ] )
        
        xg.startElement("outline", AttributesImpl(attr))
        for c in self.children:
            c.output(xg)
        xg.endElement("outline")

    class OIterator:
        def __init__(self, o):
            self._o = o
            self._index = -1

        def __iter__(self):
            return self

        def next(self):
            self._index += 1
            if self._index < len(self._o._children):
                return self._o._children[self._index]
            else:
                raise StopIteration

class OutlineList:
    def __init__(self):
        self._roots = []
        self._stack = []
    
    def add_outline(self, outline):
        if len(self._stack):
            self._stack[-1].add_child(outline)
        else:
            self._roots.append(outline)
        self._stack.append(outline)

    def close_outline(self):
        if len(self._stack):
            del self._stack[-1]

    def roots(self):
        return self._roots

class OPMLHandler(xml.sax.handler.ContentHandler):
    def __init__(self):
        self._outlines = OutlineList()
        self._opml = None
        self._content = ""

    def startElement(self, name, attrs):
        if self._opml is None:
            if name != 'opml':
                raise ValueError, "This doesn't look like OPML"
            self._opml = OPML()
        if name == 'outline':
            o = Outline()
            o.update(attrs)
            self._outlines.add_outline(o)
        self._content = ""

    def endElement(self, name):
        if name == 'outline':
            self._outlines.close_outline()
            return
        if name == 'opml':
            self._opml.outlines = self._outlines.roots()
            return
        for key in ('title', 'dateCreated', 'dateModified', 'ownerName',
                    'ownerEmail', 'expansionState', 'vertScrollState',
                    'windowTop', 'windowBotton', 'windowRight', 'windowLeft'):
            if name == key:
                self._opml[key] = self._content
                return
        
    def characters(self, ch):
        self._content += ch

    def get_opml(self):
        return self._opml

def parse(stream):
    parser = make_parser()
    parser.setFeature(feature_namespaces, 0)
    handler = OPMLHandler()
    parser.setContentHandler(handler)

    parser.parse(stream)
    return handler.get_opml()

class BlogListEntry(object):
    __slots__ = ('text', 'type', 'url', 'xmlurl', 'htmlurl', 'description', 'language',
                 'title', 'version')

    def __init__(self):
        self.xmlurl = None
        self.description = None
        self.language = None
        self.title = None
        self.version = None

def _find_entries(outline):
    entries = []
    for c in outline.children:
        entries += _find_entries(c)
    type = outline.get('type', '')
    text = outline.get('text', '')
    e = None
    if type == 'link':
        url = outline.get('url', '')
        if url != '':
            e = BlogListEntry()
            e.type = type
            e.text = text
            e.url = url
    else:
        url = outline.get('htmlUrl', '')
        xmlurl = outline.get('xmlUrl', '')
        if url != '' and xmlurl != '':
            e = BlogListEntry()
            e.type = type
            e.text = text
            e.url = url
            e.xmlurl = xmlurl
            e.description = outline.get('description', '')
            e.language = outline.get('language', '')
            e.title = outline.get('title', '')
            e.version = outline.get('version', '')
    if e is not None:
        entries[0:0] = [e]
    return entries

def find_entries(outlines):
    entries = []
    for o in outlines:
        entries += _find_entries(o)
    return entries

def read(stream):
    try:
        o = parse(stream)
    except ValueError:
        return None
    entries = find_entries(o.outlines)
    ret = []
    edict = {}
    for e in entries:
        ek = (e.text, e.type, e.url)
        edict[ek] = edict.get(ek, 0) + 1
        if edict[ek] < 2:
            ret.append(e)
    return ret
