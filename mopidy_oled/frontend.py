import logging
import os
import threading
import time

import pykka
import requests
from mopidy import core

import netifaces

from . import Extension
from .brainz import Brainz

logger = logging.getLogger(__name__)


class OLEDConfig:
    def __init__(self, config=None):
        self.size = 128

class OLEDFrontend(pykka.ThreadingActor, core.CoreListener):
    def __init__(self, config, core):
        super().__init__()
        self.core = core
        self.config = config
        self.current_track = None
        self._mode = 1
        self._playlistSize = 0
        self._playlistNum = 0
        self._playlist = None

    def on_start(self):
        self.display = OLED(self.config)
        self.display.start()
        self.display.update(volume=self.core.mixer.get_volume().get())
        if "http" in self.config:
            ifaces = netifaces.interfaces()
            ifaces.remove("lo")

            http = self.config["http"]
            if http.get("enabled", False):
                hostname = http.get("hostname", "127.0.0.1")
                port = http.get("port", 6680)
                if hostname in ["::", "0.0.0.0"]:
                    family = (
                        netifaces.AF_INET6 if hostname == "::" else netifaces.AF_INET
                    )
                    for iface in ifaces:
                        hostname = self.get_ifaddress(iface, family)
                        if hostname is not None:
                            break
                if hostname is not None:
                    self.display.update(
                        title=f"Visit http://{hostname}:{port} to select content."
                    )
                    self.display.update_album_art(art="")

    def on_stop(self):
        self.display.stop()
        self.display = None

    def get_ifaddress(self, iface, family):
        try:
            return netifaces.ifaddresses(iface)[family][0]["addr"]
        except (IndexError, KeyError):
            return None

    def mute_changed(self, mute):
        pass

    def options_changed(self):
        self.display.update(
            shuffle=self.core.tracklist.get_random(),
            repeat=self.core.tracklist.get_repeat(),
        )

    def playlist_changed(self, playlist):
        pass

    def playlist_deleted(self, playlist):
        pass

    def playlists_loaded(self):
        pass

    def seeked(self, time_position):
        self.update_elapsed(time_position)

    def stream_title_changed(self, title):
        self.display.update(title=title)

    def track_playback_ended(self, tl_track, time_position):
        self.update_elapsed(time_position)
        self.display.update(state="pause")

    def track_playback_paused(self, tl_track, time_position):
        self.update_elapsed(time_position)
        self.display.update(state="pause")

    def track_playback_resumed(self, tl_track, time_position):
        self.update_elapsed(time_position)
        self.display.update(state="play")

    def track_playback_started(self, tl_track):
        self.update_track(tl_track.track, 0)
        self.display.update(state="play")

    def update_elapsed(self, time_position):
        self.display.update(elapsed=float(time_position))

    def update_track(self, track, time_position=None):
        if track is None:
            track = self.core.playback.get_current_track().get()

        title = ""
        album = ""
        artist = ""

        if track.name is not None:
            title = track.name

        if track.album is not None and track.album.name is not None:
            album = track.album.name

        if track.artists is not None:
            artist = ", ".join([artist.name for artist in track.artists])

        self.display.update(title=title, album=album, artist=artist)

        if time_position is not None:
            length = track.length
            # Default to 60s long and loop the transport bar
            if length is None:
                length = 60
                time_position %= length

            self.display.update(elapsed=float(time_position), length=float(length))

    def tracklist_changed(self):
        pass

    def volume_changed(self, volume):
        if volume is None:
            return

        self.display.update(volume=volume)

    def playlist_list(self):
        self._playlist = self.core.playlists.as_list().get()
        self._playlistSize = len(self._playlist)
        self._playlistNum = 0
        if self._mode == 0:
            self.display.update2(self._playlist, self._playlistNum)

    def playlist_prev(self):
        self._playlistNum = self._playlistNum - 1
        if self._playlistNum < 0:
            self._playlistNum = self._playlistSize - 1
        self.display.update2(self._playlist, self._playlistNum)

    def playlist_next(self):
        self._playlistNum = (self._playlistNum + 1) % self._playlistSize
        self.display.update2(self._playlist, self._playlistNum)

    def playlist_select(self):
        playlist_items = self.core.playlists.get_items(self._playlist[self._playlistNum].uri).get()
        itemURIs = []
        for item in playlist_items:
            itemURIs.append(item.uri)
        self.core.tracklist.clear()
        self.core.tracklist.add(uris=itemURIs)

    def custom_command(self, **kwargs):
        target = kwargs.get("target")
        if target == 'oled':
            self._mode = kwargs.get("mode", self._mode)
            self.display.update(mode=self._mode)
            playlist = kwargs.get("playlist")
            if playlist == "list":
                self.playlist_list()
            elif playlist == "next":
                self.playlist_next()
            elif playlist == "prev":
                self.playlist_prev()
            elif playlist == "select":
                self.playlist_select()


class OLED:
    def __init__(self, config):
        self.config = config
        self.cache_dir = Extension.get_data_dir(config)
        self.display_config = OLEDConfig(config["oled"])
        self.display_class = Extension.get_display_types()[
            self.config["oled"]["display"]
        ]

        self._brainz = Brainz(cache_dir=self.cache_dir)
        self._display = self.display_class(self.display_config)
        self._running = threading.Event()
        self._delay = 1.0 / 30
        self._thread = None

        self._mode = 1

        self.shuffle = False
        self.repeat = False
        self.state = "stop"
        self.volume = 100
        self.progress = 0
        self.elapsed = 0
        self.length = 0
        self.title = ""
        self.album = ""
        self.artist = ""
        self._last_progress_update = time.time()
        self._last_progress_value = 0
        self._last_art = ""

    def start(self):
        if self._thread is not None:
            return

        self._running = threading.Event()
        self._running.set()
        self._thread = threading.Thread(target=self._loop)
        self._thread.start()

    def stop(self):
        self._running.clear()
        self._thread.join()
        self._thread = None
        self._display.stop()

    def _handle_album_art(self, art):
        pass

    def update_album_art(self, art=None):
        pass

    def update(self, **kwargs):
        self.shuffle = kwargs.get("shuffle", self.shuffle)
        self.repeat = kwargs.get("repeat", self.repeat)
        self.state = kwargs.get("state", self.state)
        self.volume = kwargs.get("volume", self.volume)
        # self.progress = kwargs.get('progress', self.progress)
        self.elapsed = kwargs.get("elapsed", self.elapsed)
        self.length = kwargs.get("length", self.length)
        self.title = kwargs.get("title", self.title)
        self.album = kwargs.get("album", self.album)
        self.artist = kwargs.get("artist", self.artist)
        self._mode = kwargs.get("mode", self._mode)

        if "elapsed" in kwargs:
            if "length" in kwargs:
                self.progress = float(self.elapsed) / float(self.length)
            self._last_elapsed_update = time.time()
            self._last_elapsed_value = kwargs["elapsed"]

    def _loop(self):
        while self._running.is_set():
            if self.state == "play":
                t_elapsed_ms = (time.time() - self._last_elapsed_update) * 1000
                self.elapsed = float(self._last_elapsed_value + t_elapsed_ms)
                self.progress = self.elapsed / self.length
            if self._mode == 1:
                self._display.update_overlay(
                    self.shuffle,
                    self.repeat,
                    self.state,
                    self.volume,
                    self.progress,
                    self.elapsed,
                    self.title,
                    self.album,
                    self.artist,
                )

            if self._mode == 1:
                self._display.redraw()
            time.sleep(self._delay)

    def update2(self, playlist, index):
        self._display.update_playlist(playlist, index)
