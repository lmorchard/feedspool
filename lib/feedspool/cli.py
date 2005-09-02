"""Command-line interface to FeedSpool
"""

import os, os.path, sys, logging, logging.config, ConfigParser, re
from cStringIO import StringIO
from optparse import OptionParser
from datetime import datetime, timedelta
import TimeRotatingFileHandler
import feedspool

##########################################################################

def cmd_hello():
    """Hello World|"""
    print "Hello world!"
    log.debug("Greeted the user")

def cmd_scan():
    """Perform a polling scan of all subscribed feeds.|"""
    from feedspool import subscriptions
    sl = subscriptions.SubscriptionsList()
    for sub in sl.list(): 
        try:
            sub.scan()
        except KeyboardInterrupt:
            raise
        except Exception, e:
            log.exception("Problem while scanning %s" % sub.uri)

def cmd_info():
    """Display metadata about a subscribed feed|<feed URI>"""
    feed_uri = args[0]
    try:
        from feedspool import subscriptions
        sl = subscriptions.SubscriptionsList()
        sub = sl.get(feed_uri)
        for k,v in sub.items():
            log.info("%s: %s" % (k, v))
    except subscriptions.SubscriptionNotFoundException, e:
        log.error("No subscription found for %s" % args[0])        

def cmd_list():
    """List subscribed feed URIs|"""
    from feedspool import subscriptions
    sl = subscriptions.SubscriptionsList()
    for url in sl.listURIs(): log.info("%s" % url)

def cmd_add():
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

def cmd_remove():
    """Remove a subscription to a given feed URI|<feed URI>"""
    feed_uri = args[0]
    try:
        from feedspool import subscriptions
        sl = subscriptions.SubscriptionsList()
        sl.remove(feed_uri)
        sl.save()
    except subscriptions.SubscriptionNotFoundException, e:
        log.error("No subscription found for %s" % args[0])        

def cmd_opmlimport():
    """Import a list of subscriptions in OPML|<OPML filename>"""
    # Import from a given filename, or grab from STDIN
    if len(args) > 0:
        fin = open(args[0], 'r')
    else:
        fin = sys.stdin

    try:
        from feedspool import subscriptions
        sl = subscriptions.SubscriptionsList()
        sl.OPMLimport(fin)
        sl.save()
    except:
        raise

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
    for cmd_func_name in cmd_names:
        cmd       = eval(cmd_func_name)
        cmd_name  = cmd_func_name[4:]
        cmd_doc   = getattr(cmd, '__doc__', '|')

        (cmd_desc, cmd_args) = cmd_doc.split('|')
        cmd_usage = cmd_name + " " + cmd_args
        usage += "    %s %s\n        %s\n" % (cmd_name, cmd_args, cmd_desc)

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
    
    # Set up console logging.
    log = logging.getLogger("")
    log_formatter     = logging.Formatter('%(message)s', '%Y-%m-%dT%H:%M:%S') 
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
        cmd_func = eval('cmd_%s' % cmd)
    except NameError:
        log.error("No such command '%s'" % cmd)
        parser.print_help()
        sys.exit(1)

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
