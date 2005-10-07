"""This is a simpleminded plugin which always votes to force a feed scan."""

from feedspool import config
from feedspool.plugins import Plugin

class ForcePollPlugin(Plugin):

    def feed_should_scan(self, subscription):
        return True

