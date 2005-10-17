"""Command-line interface to FeedSpool"""

import os, os.path, sys, logging, logging.config, ConfigParser, re, atexit, time
import threading
from cStringIO import StringIO
from optparse import OptionParser
from datetime import datetime, timedelta
import TimeRotatingFileHandler
import feedspool

##########################################################################

USAGE_TMPL = "    %(name)s %(args)s\n        %(desc)s\n"

def cmd_hello(options, args):
    """Hello World|"""
    print "Hello world!"

    from feedspool.config import plugin_manager
    plugin_manager.dispatch("hello")

def cmd_scan(options, args):
    """Perform a polling scan of all subscribed feeds.|"""
    from feedspool.config import plugin_manager
    plugin_manager.dispatch("scan_start")

    from feedspool import subscriptions
    sl = subscriptions.SubscriptionsList()
    for sub in sl.list(): 
        try:
            sub.scan()
        except KeyboardInterrupt:
            raise
        except Exception, e:
            log.exception("Problem while scanning %s" % sub.uri)

    plugin_manager.dispatch("scan_end")

def cmd_info(options, args):
    """Display metadata about a subscribed feed|<feed URI>"""
    feed_uri = args[0]
    try:
        from feedspool import subscriptions
        sl = subscriptions.SubscriptionsList()
        sub = sl.get(feed_uri)
        sub.meta.write(sys.stdout)
    except subscriptions.SubscriptionNotFoundException, e:
        log.error("No subscription found for %s" % args[0])        

def cmd_list(options, args):
    """List subscribed feed URIs|"""
    from feedspool import subscriptions
    sl = subscriptions.SubscriptionsList()
    for url in sl.listURIs(): log.info("%s" % url)

def cmd_add(options, args):
    """Add a subscription to the given feed URI|<feed URI>"""
    feed_uri = args[0]
    try:
        from feedspool import subscriptions
        sl = subscriptions.SubscriptionsList()
        sl.add(feed_uri)
        sl.save()
    except subscriptions.SubscriptionDuplicateException, e:
        log.error("Already subscribed to %s" % args[0])        
    except subscriptions.SubscriptionFeedNotFoundException, e:
        log.error("No feeds found at %s" % args[0])
    except subscriptions.SubscriptionMultipleFeedsFoundException, e:
        log.info("Multiple feeds found at %s" % args[0])
        for url in e.feeds: log.info("  %s" % url)

def cmd_remove(options, args):
    """Remove a subscription to a given feed URI|<feed URI>"""
    feed_uri = args[0]
    try:
        from feedspool import subscriptions
        sl = subscriptions.SubscriptionsList()
        sl.remove(feed_uri)
        sl.save()
    except subscriptions.SubscriptionNotFoundException, e:
        log.error("No subscription found for %s" % args[0])        

##########################################################################

class CmdException(Exception):
    pass

class NotEnoughArgsException(CmdException):
    def __init__(self, msg): self.msg = msg
    def __str__(self): return "Not enough arguments. Need: %s" % \
        (self.msg)
    
cmd_names = filter(lambda x: x.startswith('cmd_'), dir())
def main():
    """Main driver, try to dynamically find desired operation 
    and execute."""
    global options, args, user, log    

    # Build command usage text
    usage = "%s [<options>] <command> [<arguments>...]\n\n" % sys.argv[0]
    usage += "where <command> is one of:\n"

    commands = {}

    for cmd_func_name in cmd_names:
        cmd       = eval(cmd_func_name)
        cmd_name  = cmd_func_name[4:]
        cmd_doc   = getattr(cmd, '__doc__', '|')
        (cmd_desc, cmd_args) = cmd_doc.split('|')

        commands[cmd_name] = {
            'name' : cmd_name,
            'call' : cmd,
            'desc' : cmd_desc,
            'args' : cmd_args
        }

    # Process command line arguments
    parser = OptionParser(usage=usage)
    parser.add_option('-P', '--profile',  dest='profile',
                      help="Run with profiler, save output to file {PROFILE}",
                      default=None)

    parser.add_option('-f', '--conf',   dest='conf',
                      help="Path to config file",
                      default='conf/feedspool.conf')
                      
    parser.add_option('-v', '--verbose', dest='verbose',
                      help="Verbose console logging",
                      default=False, action='store_true')
                      
    parser.add_option('-d', '--debug',   dest='debug',
                      help="Debug console logging",
                      default=False, action='store_true')
                      
    parser.add_option('-q', '--quiet',   dest='quiet',
                      help="Silence all but essential console logging",
                      default=False, action='store_true')
    
    (options, args) = parser.parse_args()

    # Load up config module and configure before doing anything else
    from feedspool import config
    config.configure(options.conf)
    from feedspool.config import plugin_manager
    
    # Ask for and merge in commands contributed by plugins.
    plugin_commands = plugin_manager.dispatch("cli_get_commands")
    for cmds in plugin_commands: commands.update(cmds)

    # Build usage from all commands found.
    names = commands.keys()
    names.sort()
    usage += '\n'.join([ USAGE_TMPL % commands[x] for x in names])
    parser.set_usage(usage)

    # Set up console logging.
    log = logging.getLogger("")
    log_formatter = logging.Formatter('%(message)s', '%Y-%m-%dT%H:%M:%S') 
    #log_formatter     = logging.Formatter\
    #    ('[%(asctime)s %(levelname)s %(name)s] %(message)s', 
    #     '%Y-%m-%dT%H:%M:%S')  
    log_handler       = logging.StreamHandler(sys.stdout)
    log_handler.setLevel(logging.INFO)
    log_handler.setFormatter(log_formatter)
    if options.quiet:   log_handler.setLevel(logging.FATAL)
    if options.verbose: log_handler.setLevel(logging.INFO)
    if options.debug:   log_handler.setLevel(logging.DEBUG)
    log.addHandler(log_handler)

    # Try to get the current command
    if len(args) < 1:
        parser.print_help()
        sys.exit(0)    
    cmd = args.pop(0)

    # Find a function for the command
    try:
        cmd_func = lambda: commands[cmd]['call'](options, args)
    except NameError:
        log.error("No such command '%s'" % cmd)
        parser.print_help()
        sys.exit(1)

    # Fire off the startup event, register for shutdown
    plugin_manager.dispatch("startup")

    # Execute the chosen command
    try:
        if options.profile:
            from profile import Profile
            p = Profile()
            p.runcall(cmd_func)
            p.dump_stats(options.profile)
        else:
            cmd_func()

    except CmdException, e:
        log.error("Error: %s" % e)
        parser.print_help()
        sys.exit(1)

    plugin_manager.dispatch("shutdown")

    # Hang out while threads wind down.
    while threading.activeCount() > 0: 
        time.sleep(5)
        log.debug("Waiting for threads to end...")

