"""Configure various shared things, including logging."""
import sys, os, time, logging, logging.config, atexit

from ConfigParser import SafeConfigParser as ConfigParser
import TimeRotatingFileHandler
import socket; socket.setdefaulttimeout(300)

from feedspool.plugins import PluginManager

USER_AGENT    = "FeedSpool/0.1 +http://decafbad.com/trac/wiki/FeedSpool"

META_FN       = 'subscription.conf'
FEED_FULL_FN  = 'full.feed'
FEED_HEAD_FN  = 'head.feed'
ENTRIES_DIR   = 'entries'
ENTRY_FN_TMPL = '%s.entry'

ACCEPT_HEADER = "application/atom+xml,application/rdf+xml,application/rss+xml,application/x-netcdf,application/xml;q=0.9,text/xml;q=0.2,*/*;q=0.1"

def configure(conf_fn="conf/feedspool.conf"):
    """Read in the config file and initialize a few things."""
    global config, log, main_log, db_uri, so_conn, db_conn, plugin_manager
    
    # Read in config file
    config = ConfigParser()
    config.read(conf_fn)

    # Set up logging
    logging.config.fileConfig(conf_fn)
    log      = logging.getLogger("%s"%__name__)
    main_log = logging.getLogger("")

    # Set up some app-wide settings & instances
    data_root = alt('data', 'root', 'data')

    # HACK: Coerce HTTPCache to stuff things away in our data directory
    import httpcache
    httpcache.cacheSubDir__ = os.path.join(data_root, "httpcache")
    if not os.path.exists(httpcache.cacheSubDir__):
        os.mkdir(httpcache.cacheSubDir__)

    # Load up plugins
    plugins_root = alt('global', 'plugins', 'plugins')
    plugin_manager = PluginManager(plugins_root)

    log.debug("Configuration complete.")

def alt(section, name, default, local_val=None):
    """Provide mechanism to alternate between config, local override 
    and default."""
    if local_val is not None:
        return local_val
    if config.has_option(section, name):
        return config.get(section, name)
    return default

