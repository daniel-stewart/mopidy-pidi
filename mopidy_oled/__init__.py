import logging
import pathlib

import pkg_resources

from mopidy import config, ext

from .plugin import Display, DisplayOLED

__version__ = pkg_resources.get_distribution("mopidy_oled").version

logger = logging.getLogger(__name__)


class Extension(ext.Extension):

    dist_name = "Mopidy-OLED"
    ext_name = "oled"
    version = __version__

    @classmethod
    def get_display_types(self):
        display_types = {'oled': DisplayOLED,}
        #for entry_point in pkg_resources.iter_entry_points("oled.plugin.display"):
        #    try:
        #        plugin = entry_point.load()
        #        display_types[plugin.option_name] = plugin
        #    except (ImportError) as err:
        #        logger.log(
        #            logging.WARN, f"Error loading display plugin {entry_point}: {err}"
        #        )

        return display_types

    def get_default_config(self):
        return config.read(pathlib.Path(__file__).parent / "ext.conf")

    def get_config_schema(self):
        schema = super().get_config_schema()
        schema["display"] = config.String(choices=self.get_display_types().keys())
        schema["rotation"] = config.Integer(choices=[0, 90, 180, 270])
        return schema

    def setup(self, registry):
        from .frontend import OLEDFrontend

        registry.add("frontend", OLEDFrontend)
