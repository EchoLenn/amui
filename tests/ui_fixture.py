"""Deterministic end-to-end UI fixture; never touches a real player or account."""
import json
import math
import os
from pathlib import Path
import queue
import time
from dataclasses import replace
from test_amui import amui


def playback(self):
    self.track = amui.Track(player="fixture", identity="fixture:1", title="Midnight Frequencies",
        artist="The Afterhours", album="A Room Full of Sound", length=240, position=95,
        status="Playing", sampled=time.monotonic(), art=os.environ.get("AMUI_FIXTURE_ART", ""))
    while not self.stop.is_set():
        try:
            _, action = self.actions.get(timeout=.1)
        except queue.Empty:
            continue
        destination = os.environ.get("AMUI_FIXTURE_ACTIONS")
        if destination:
            with open(destination, "a") as file:
                file.write(json.dumps(action) + "\n")
        if action == "shuffle":
            self.extras.shuffle = not self.extras.shuffle
        elif action == "repeat":
            self.extras.repeat = {"None": "Playlist", "Playlist": "Track", "Track": "None"}[self.extras.repeat]
        elif action == "toggle":
            self.track = replace(self.track, position=self.track.elapsed(), sampled=time.monotonic(),
                                 status="Paused" if self.track.status == "Playing" else "Playing")


def extras(self):
    self.items = [("City Lights", "The Afterhours"), ("Velvet Radio", "Luna Park"),
                  ("Slow Motion", "Electric Room"), ("Blue Hour", "The Afterhours"), ("One More Track", "Night Drive")]
    self.label, self.shuffle, self.repeat = "Fixture", False, "None"
    while not self.stop.is_set():
        self.identity = self.player.track.identity
        self.stop.wait(.1)


def spectrum(self):
    self.label = "CAVA · fixture"
    while not self.stop.is_set():
        self.bars = [.12 + .8 * abs(math.sin(i * .19 + time.monotonic() * .7)) for i in range(48)]
        self.stop.wait(.03)


def lyrics(self, track, retry):
    return {"duration": 240, "syncedLyrics": "[00:00.00]La ciudad baja la voz\n[00:30.00]La noche enciende el color\n"
            "[01:35.00]Todo suena un poco más cerca\n[01:55.00]Cuando dejamos el ruido atrás\n[02:10.00]Sólo queda esta canción"}


def music_lookup(self, term, library, kind, next_path):
    return [dict(id='fixture:1', type=('library-' if library else '')+kind,
                 title='Fixture Search Result', artist='Fixture Artist', album='Fixture Album')], ''


def music_choose(self, item, action='play-item'):
    destination = os.environ.get('AMUI_FIXTURE_MUSIC_ACTIONS')
    if destination:
        with open(destination, 'a') as file:
            file.write(json.dumps(dict(action=action, item=item))+'\n')
    self.label = 'Selección enviada · fixture'


amui.Player.run = playback
amui.Extras.run = extras
amui.Spectrum.run = spectrum
amui.Lyrics.fetch = lyrics
amui.MusicBrowser.lookup = music_lookup
amui.MusicBrowser.choose = music_choose

if __name__ == "__main__":
    raise SystemExit(amui.main())
