"""This provides a plugin which varies the polling period for feeds using an
AIMD-inspired algorithm:  

Each time new entries are found, the polling period jumps to a shorter value
via multiplication by a given factor (ie. 0.5).  When new entries are not found
on a poll, the polling period is incremented to a bit longer by a given value
(ie. 30 minutes).

The intended effect is that, when a feed is quiet, the aggregator gradually
waits longer and longer between checking it.  However, as soon as the feed
shows any activity, it quickly ramps up in anticipation of more activity in the
near future.  

Over time, this algorithm should naturally settle on a decent guess at a good
polling period for any given feed.
"""
from feedspool import config
from feedspool.plugins import Plugin

class PollScheduleVaryPlugin(Plugin):

    def startup(self):
        """Start off with a blank set of new entry flags."""
        self.new_flags = {}

    def feed_poll_start(self, subscription):
        """At the start of a feed scan, flag no new feeds by default."""
        self.new_flags[subscription.uid] = False

    def feed_new_entries(self, subscription, entries):
        """When new entries found, flip the feed's flag."""
        self.new_flags[subscription.uid] = True

    def feed_poll_end(self, subscription):
        """At the end of a feed scan, tweak the polling period."""
        self.update_period(subscription, self.new_flags[subscription.uid])

    def update_period(self, subscription, found_new_entries):
        """Update the polling period, based on finding new entries."""
        update_period = \
            subscription.meta.getint('scan', 'current_update_period')

        if found_new_entries:
            # If there were new entries, try ramping up the update freq.
            ramp_up_factor    = \
                subscription.meta.getfloat('scan', 'update_ramp_up_factor')
            new_update_period = int(update_period * ramp_up_factor)

        else:
            # If there weren't new entries, try backing off the update freq.
            back_off_period   = \
                subscription.meta.getfloat('scan', 'update_back_off_period')
            new_update_period = int(update_period + back_off_period)

        # Constrain the new update period to the min/max range.
        min_period = subscription.meta.getint('scan', 'min_update_period')
        max_period = subscription.meta.getint('scan', 'max_update_period')

        # Update the update period.
        old_update_period = update_period
        update_period = \
            max(min_period, min(max_period, new_update_period))
        self.log.debug("Updating period from %s to %s" % \
                (old_update_period, update_period))

        # Save the new period and return the value.
        subscription.meta.set('scan', 'current_update_period', str(update_period))
