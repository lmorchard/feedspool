"""This is a plugin providing new CLI commands for the import and 
export of subscribed feeds in OPML format.
"""

import sys
from feedspool import config
from feedspool.plugins import CLIPlugin
import opml

# TODO: Obviate the need for this module.
import feedparser

class OPMLImportExportPlugin(CLIPlugin):

    def cmd_opmlimport(self, options, args):
        """Import a list of subscriptions in OPML|<OPML filename>"""
        if len(args) > 0: fin = open(args[0], 'r')
        else:             fin = sys.stdin

        from feedspool import subscriptions
        sl = subscriptions.SubscriptionsList()
        for item in opml.read(fin):
            sl._importuri(item.xmlurl, False)
        sl.save()

    def cmd_opmlexport(self, options, args):
        """Export a list of subscriptions as OPML|<OPML filename>"""
        if len(args) > 0: fout = open(args[0], 'w')
        else:             fout = sys.stdout

        op = opml.OPML()
        op['title'] = "Subscriptions"

        from feedspool import subscriptions
        sl = subscriptions.SubscriptionsList()
        for sub in sl.list():
            # TODO: Stop using feedparser for this, build a simpler one?
            data = feedparser.parse(sub.head_fn)
            feed = data.feed

            o = opml.Outline()
            o['xmlUrl'] = sub.uri
            if 'title' in feed:       
                o['text'], o['title'] = feed.title, feed.title
            if 'link' in feed:
                o['htmlUrl'] = feed.link
            if 'description' in feed: 
                o['description'] = feed.description
            if 'language' in feed and feed.language: 
                o['language'] = feed.language
            if 'version' in data:     
                o['version']  = data.version

            op.outlines.append(o)

        fout.write('<?xml version="1.0"?>\n')
        op.output(fout)
