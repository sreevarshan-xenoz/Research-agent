"""P19: Plugin System — Entry-point and filesystem-based plugin discovery."""

from __future__ import annotations

import importlib
import importlib.metadata
import inspect
import logging
import pkgutil

from research_agent.plugins.base import BasePlugin

logger = logging.getLogger(__name__)


def discover_entry_point_plugins() -> dict[str, BasePlugin]:
    """Discover plugins registered via Python entry points.

    Looks for entry points in the group ``research_agent.plugins``
    defined in ``pyproject.toml`` or ``setup.cfg``::

        [project.entry-points."research_agent.plugins"]
        my_plugin = "research_agent.plugins.installed.my_plugin:MyPlugin"

    Returns:
        Dict mapping plugin_id -> plugin instance.
    """
    plugins: dict[str, BasePlugin] = {}
    try:
        eps = importlib.metadata.entry_points(group="research_agent.plugins")
        for ep in eps:
            try:
                plugin_class = ep.load()
                if inspect.isclass(plugin_class) and issubclass(plugin_class, BasePlugin) and plugin_class is not BasePlugin:
                    instance = plugin_class()
                    plugins[instance.metadata.id] = instance
                    logger.info("Discovered entry-point plugin: %s (v%s)", instance.metadata.name, instance.metadata.version)
            except Exception as exc:
                logger.warning("Failed to load entry-point plugin '%s': %s", ep.name, exc)
    except Exception as exc:
        logger.debug("No 'research_agent.plugins' entry points found: %s", exc)

    return plugins


def discover_filesystem_plugins(plugin_dirs: list[str] | None = None) -> dict[str, BasePlugin]:
    """Discover plugins by scanning the filesystem for plugin modules.

    Scans:
    1. ``research_agent.plugins.installed`` (built-in location)
    2. Additional directories in ``plugin_dirs``

    Each module must expose a ``plugin`` attribute that is a ``BasePlugin`` subclass instance,
    or a ``register_plugin()`` function that returns a ``BasePlugin`` instance.

    Returns:
        Dict mapping plugin_id -> plugin instance.
    """
    plugins: dict[str, BasePlugin] = {}
    scanned_packages = ["research_agent.plugins.installed"]

    if plugin_dirs:
        scanned_packages.extend(plugin_dirs)

    for package_name in scanned_packages:
        try:
            package = importlib.import_module(package_name)
            package_path = getattr(package, "__path__", None)
            if not package_path:
                continue

            for importer, modname, is_pkg in pkgutil.iter_modules(package_path):
                if is_pkg or modname.startswith("_"):
                    continue
                try:
                    full_name = f"{package_name}.{modname}"
                    module = importlib.import_module(full_name)

                    # Look for 'plugin' attribute
                    plugin_obj = getattr(module, "plugin", None)
                    if plugin_obj is not None and isinstance(plugin_obj, BasePlugin):
                        plugins[plugin_obj.metadata.id] = plugin_obj
                        logger.info("Discovered filesystem plugin: %s", plugin_obj.metadata.name)
                        continue

                    # Look for 'register_plugin()' function
                    register_fn = getattr(module, "register_plugin", None)
                    if register_fn is not None and callable(register_fn):
                        instance = register_fn()
                        if isinstance(instance, BasePlugin):
                            plugins[instance.metadata.id] = instance
                            logger.info("Discovered filesystem plugin via register: %s", instance.metadata.name)
                            continue

                    # Look for any BasePlugin subclass (all of them, not just the first)
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and issubclass(obj, BasePlugin) and obj is not BasePlugin):
                            instance = obj()
                            plugins.setdefault(instance.metadata.id, instance)
                            logger.info("Discovered filesystem plugin class: %s", instance.metadata.name)

                except Exception as exc:
                    logger.warning("Failed to load plugin module '%s': %s", modname, exc)

            # Check for a list/iterable of plugins (catches plugins defined as _plugins_list)
            plugin_list = getattr(module, "__all_plugins__", None) or getattr(module, "_plugins_list", None)
            if plugin_list is not None and isinstance(plugin_list, (list, tuple)):
                for p_obj in plugin_list:
                    if isinstance(p_obj, BasePlugin):
                        plugins.setdefault(p_obj.metadata.id, p_obj)
                        logger.info("Discovered plugin from list: %s", p_obj.metadata.name)

        except ImportError:
            logger.debug("Package '%s' not found, skipping", package_name)
        except Exception as exc:
            logger.warning("Error scanning package '%s': %s", package_name, exc)

    return plugins


def discover_all_plugins(plugin_dirs: list[str] | None = None) -> dict[str, BasePlugin]:
    """Discover all available plugins from both entry-point and filesystem sources.

    Args:
        plugin_dirs: Additional directories to scan for plugin modules.

    Returns:
        Dict mapping plugin_id -> plugin instance (entry-point plugins take priority).
    """
    plugins: dict[str, BasePlugin] = {}

    # Entry-point plugins take priority
    ep_plugins = discover_entry_point_plugins()
    plugins.update(ep_plugins)

    # Filesystem plugins (don't override entry-point)
    fs_plugins = discover_filesystem_plugins(plugin_dirs)
    for pid, instance in fs_plugins.items():
        if pid not in plugins:
            plugins[pid] = instance

    return plugins
