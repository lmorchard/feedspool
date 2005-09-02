"""Configure various shared things, including logging."""
import sys, os, time, logging, logging.config, ConfigParser

import TimeRotatingFileHandler
import socket; socket.setdefaulttimeout(300)

def configure(conf_fn="conf/feedspool.conf"):
    """Read in the config file and initialize a few things."""
    global config, log, main_log, db_uri, so_conn, db_conn
    
    # Read in config file
    config = ConfigParser.ConfigParser()
    config.read(conf_fn)
    data_root = alt('data', 'root', 'data')

    # HACK: Coerce HTTPCache to stuff things away in our data directory
    import httpcache
    httpcache.cacheSubDir__ = os.path.join(data_root, "httpcache")
    if not os.path.exists(httpcache.cacheSubDir__):
        os.mkdir(httpcache.cacheSubDir__)

    # Set up logging
    logging.config.fileConfig(conf_fn)
    log      = logging.getLogger("%s"%__name__)
    main_log = logging.getLogger("")

    log.debug("Configuration complete.")

def alt(section, name, default, local_val=None):
    """Provide mechanism to alternate between config, local override 
    and default."""
    if local_val is not None:
        return local_val
    if config.has_option(section, name):
        return config.get(section, name)
    return default

