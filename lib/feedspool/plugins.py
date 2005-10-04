"""Plugin-related classes."""

import sys, os, os.path, imp, logging
import feedspool.config

class Plugin:
    """Base class for all plugins."""
    def __init__(self, manager, plugin_root):
        self.log  = logging.getLogger("%s"%self.__class__.__name__)
        self.plugin_root = plugin_root

class PluginManager:
    """Manager of plugins, dispatcher of hook calls."""
    def __init__(self, plugins_root):
        """Initialize, load up and create plugin instances."""
        self.log  = logging.getLogger("%s"%self.__class__.__name__)
        self.plugins = []
        self.plugins_root = plugins_root
        self.load_plugins(plugins_root)

    def load_plugins(self, plugins_root):
        """Scan through plugins dir, load and instantiate plugins found."""
        # Recursive scan of plugins dir, looking for plugin modules.
        for root, dirs, files in os.walk(plugins_root):
            if 'plugin.py' in files:

                # Work out the lib parent dir and module name for plugin
                lib_dir, module_name = os.path.split(root)

                # Add the plugin lib path, import the main module.
                module = self.import_by_name(module_name, lib_dir)

                # Look for the plugin sub-module...
                if module and hasattr(module, 'plugin'):

                    # Search for Plugin subclasses in the module.
                    for cls_name in dir(module.plugin):
                        cls = getattr(module.plugin, cls_name)
                        if type(cls) is type(Plugin) and cls != Plugin and \
                                issubclass(cls, Plugin):

                            # Work out the plugin root dir, instantiate it
                            plugin_root, ignore = os.path.split(lib_dir)
                            self.plugins.append(cls(self, plugin_root))
                            self.log.debug("Loaded plugin %s (%s)" % \
                                    (plugin_root, cls.__name__))

    def import_by_name(self, module_name, lib_dir):
        """Given a module name, attempt to load it, return module."""
        fp, pathname, desc = imp.find_module(module_name, [lib_dir])
        module = None
        try:
            module = imp.load_module(module_name, fp, pathname, desc)
        finally:
            if fp: fp.close()

        return module

    def dispatch(self, meth_name, **kw):
        """Fire off a message and set of keyword args to all plugins 
        listening for it."""
        #self.log.debug("Calling plugin hook %s with %s" % (meth_name, kw))
        for plugin in self.plugins:
            if hasattr(plugin, meth_name):
                getattr(plugin, meth_name)(**kw)

