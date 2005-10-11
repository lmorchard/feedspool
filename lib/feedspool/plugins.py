"""Plugin-related classes."""

import sys, os, os.path, imp, logging
import feedspool.config
from OverlayConfigParser import OverlayConfigParser

class Plugin:
    """Base class for all plugins."""
    def __init__(self, manager, plugin_root, config, plugin_name):
        self.log  = logging.getLogger("%s"%self.__class__.__name__)
        self.plugin_manager = manager
        self.plugin_root = plugin_root
        self.plugin_name = plugin_name
        self.config = config

    def get_config(self, name):
        return self.config.get(self.plugin_name, name)

class PluginManager:
    """Manager of plugins, dispatcher of hook calls."""

    def __init__(self, plugins_root):
        """Initialize, load up and create plugin instances."""
        self.log  = logging.getLogger("%s"%self.__class__.__name__)
        self.plugins = []
        self.plugins_root = plugins_root
        self.load_plugins(plugins_root)

    def load_plugins(self, plugins_root):
        """Scan through plugins dir, load and instantiate plugins found.
        Note that this supports both single-module plugins, as well as
        plugin bundles."""

        plugin_modules = []

        # Search for *.py in plugin root dir for single module plugins.
        mods = [x for x in os.listdir(plugins_root) if x.endswith('.py')]
        for module_fn in mods:
            module = self.import_by_name(module_fn[:-3], plugins_root)
            self.init_plugins_from_module(module, plugins_root, module_fn[:-3])

        # Recursive scan of plugins dir, looking for bundled plugin modules.
        for root, dirs, files in os.walk(plugins_root):
            if 'plugin.py' in files:

                # Work out the lib parent dir and module name for plugin
                lib_dir, module_name = os.path.split(root)

                # Add the plugin lib path, import the main module.
                module = self.import_by_name(module_name, lib_dir)

                # Look for the plugin sub-module and init plugins.
                if module and hasattr(module, 'plugin'):
                    plugin_root, ignore = os.path.split(lib_dir)
                    ignore, plugin_name = os.path.split(plugin_root)
                    self.init_plugins_from_module(module.plugin, plugin_root, plugin_name)

    def init_plugins_from_module(self, module, root, name):
        """Given a module, search for plugins inside, instantiate them."""
        # Build an overlay config based on the global config
        plugin_config = OverlayConfigParser(parent=feedspool.config.config)
        
        # Try to find a config file for this plugin
        bundle_conf_fn = os.path.join(root, 'conf', '%s.conf' % name)
        simple_conf_fn = os.path.join(root, '%s.conf' % name)
        for fn in (bundle_conf_fn, simple_conf_fn):
            if os.path.isfile(fn): plugin_config.read(fn)

        # Search for Plugin subclasses in the module.
        for cls_name in dir(module):

            # Get the module part, make sure it's a plugin subclass.
            cls = getattr(module, cls_name)
            if type(cls) is type(Plugin) and cls != Plugin and issubclass(cls, Plugin):

                # Work out the plugin root dir, instantiate it
                self.plugins.append(cls(self, root, plugin_config, name))
                self.log.debug("Loaded plugin %s (named %s at %s)" % \
                    (cls.__name__, name, root))

    def import_by_name(self, module_name, lib_dir):
        """Given a module name, attempt to load it, return module."""
        # Add the module's lib dir to the system path
        if not lib_dir in sys.path:
            sys.path.append(lib_dir)
        
        # This is lifted straight from the docs for the imp module:
        fp, pathname, desc = imp.find_module(module_name, [lib_dir])
        module = None
        try:
            module = imp.load_module(module_name, fp, pathname, desc)
        finally:
            if fp: fp.close()

        return module

    def decide(self, meth_name, **kw):
        """Dispatch a message and return the yay or nay decision 
        offered by plugins."""
        returns = self.dispatch(meth_name, **kw)
        return (True in returns, False in returns)

    def dispatch(self, meth_name, **kw):
        """Fire off a message and args to all plugins listening for it."""
        returns = []
        for plugin in self.plugins:
            if hasattr(plugin, meth_name):
                try:
                    rv = getattr(plugin, meth_name)(**kw)
                    returns.append(rv)
                except Exception, e:
                    self.log.exception("Problem while dispatching %s to %s" % \
                        (meth_name, plugin))
                    returns.append(None)

        # Return the collection of plugin return values.
        return returns

