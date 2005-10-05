""" """
from feedspool import config
from feedspool.plugins import Plugin

class ForcePollPlugin(Plugin):

    ISO_NEVER = '1970-01-01T00:00:00+00:00'

    def feed_scan_start(self, subscription):
        subscription.meta.set('scan', 'next_poll', self.ISO_NEVER)

