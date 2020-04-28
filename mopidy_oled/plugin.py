import time
import subprocess
 
from board import SCL, SDA
import busio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
import textwrap

class Display:
    """Base class to represent an OLED Display display output."""

    def __init__(self, args=None):
        """Initialise a new display."""
        self._size = args.size
        self._title = ""
        self._shuffle = False
        self._repeat = False
        self._state = ""
        self._volume = 0
        self._progress = 0
        self._elapsed = 0

        self._title = ""
        self._album = ""
        self._artist = ""

    def stop(self):
        pass

    def update_album_art(self, input_file):
        """Update the display album art."""
        raise NotImplementedError

    def update_overlay(
        self, shuffle, repeat, state, volume, progress, elapsed, title, album, artist
    ):
        """Update the display transport information."""
        self._shuffle = shuffle
        self._repeat = repeat
        self._state = state
        self._volume = float(volume)
        self._progress = progress
        self._elapsed = elapsed
        self._title = title
        self._album = album
        self._artist = artist

    def redraw(self):
        """Redraw the display."""
        raise NotImplementedError

    def add_args(argparse):
        """Expand argparse instance with display-specific args."""


class DisplayDummy(Display):
    """Dummy display for use in texting."""

    option_name = "dummy"

    def update_album_art(self, input_file):
        pass

    def redraw(self):
        pass

class DisplayOLED(Display):
    """OLED display for use with 128x64 OLED display"""

    option_name = "oled"

    def __init__(self, args=None):
        self._i2c = busio.I2C(SCL, SDA)
        self._disp = adafruit_ssd1306.SSD1306_I2C(128, 64, self._i2c)
        self._disp.fill(0)
        self._disp.show()
        self._width = self._disp.width
        self._height = self._disp.height
        self._image = Image.new("1", (self._width, self._height))
        self._draw = ImageDraw.Draw(self._image)
        self._font = ImageFont.load_default()
        self._draw.rectangle((0, 0, self._width, self._height), outline=0, fill=0)
        self._disp.image(self._image)
        self._disp.show()

    def update_album_art(self, input_file):
        pass

    def redraw(self):
        self._disp.image(self._image)
        self._disp.show()

    def update_overlay(
        self, shuffle, repeat, state, volume, progress, elapsed, title, album, artist
    ):
        x = 1
        num_lines = 6
        padding = -2
        top = padding
        bottom = self._height - padding
        self._draw.rectangle((0, 0, self._width, self._height), outline=0, fill=0)
        wrapper = textwrap.TextWrapper(width=21)
        shortened_line = textwrap.shorten(text=title, width=num_lines*21)
        lines = wrapper.wrap(text=shortened_line)
        offset = 0
        for line in lines:
            self._draw.text((x, top + offset*10), line, font=self._font, fill=255)
            offset = offset + 1
            if offset >= num_lines:
                break
        if offset < num_lines:
            shortened_line = textwrap.shorten(text=album, width=((num_lines-offset)*21))
            lines = wrapper.wrap(text=shortened_line)
            for line in lines:
                self._draw.text((x, top + offset*10), line, font=self._font, fill=255)
                offset = offset + 1
                if offset >= num_lines:
                    break
        self._disp.image(self._image)
        self._disp.show()
