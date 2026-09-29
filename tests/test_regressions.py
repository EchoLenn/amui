"""Regressions reported with live Cider and Kitty; no account mutations."""
import io
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from test_amui import amui, make_ui
import features as f


class RegressionTests(unittest.TestCase):
    def test_volume_api_steps_mute_restore_and_rejection(self):
        ui = make_ui()
        player = ui.player
        extras = f.Extras(threading.Event(), player, f.load_config())
        player.extras = extras
        extras.api_available = True
        current = [.4]
        def request(endpoint, payload=None):
            self.assertEqual(endpoint, 'volume')
            if payload is None:
                return {'volume': current[0]}
            current[0] = payload['volume']
            return {'status': 'ok'}
        extras.api.request = Mock(side_effect=request)
        with patch.object(amui, 'command', side_effect=AssertionError('No MPRIS volume')):
            for action, expected in [('up', .45), ('up', .5), ('down', .45), ('mute', 0), ('mute', .45)]:
                player.act(player.track.player, action)
                self.assertAlmostEqual(player.track.volume, expected)
                self.assertAlmostEqual(extras.volume, expected)
            extras.api.request.side_effect = OSError('offline')
            player.act(player.track.player, 'up')
            self.assertIn('no aceptó', player.notice)
            self.assertAlmostEqual(player.track.volume, .45)

    def test_shuffle_does_not_publish_mpris_between_api_samples(self):
        player = make_ui().player
        extras = f.Extras(threading.Event(), player, f.load_config())
        extras.shuffle, extras.repeat = True, 'Playlist'
        info = dict(name=player.track.title, artistName=player.track.artist,
                    shuffleMode=True, repeatMode=2)
        def request(endpoint):
            self.assertIs(extras.shuffle, True)
            self.assertEqual(extras.repeat, 'Playlist')
            return {'now-playing': {'info': info}, 'volume': {'volume': .35},
                    'queue': {'items': [], 'position': -1}}[endpoint]
        extras.api.request = Mock(side_effect=request)
        with patch.object(f, 'bus', return_value=None):
            extras.poll(player.track)
            extras.poll(player.track)
        self.assertTrue(extras.shuffle)
        self.assertEqual(extras.volume, .35)

    def test_kitty_restores_cursor_even_when_drawing_times_out(self):
        with tempfile.TemporaryDirectory() as directory:
            art = Path(directory)/'art.ppm'
            art.write_bytes(b'P6\n1 1\n255\n\x00\x00\x00')
            cover = amui.Cover('kitty')
            cover.enabled = True
            cover.command = ['kitten', 'icat']
            for result in (Mock(returncode=0), subprocess.TimeoutExpired('icat', 2)):
                cover.last, cover.drawn = None, False
                with patch('sys.stdout', new_callable=io.StringIO) as output, \
                     patch.object(amui.subprocess, 'run', side_effect=result if isinstance(result, Exception) else None,
                                  return_value=result):
                    cover.show(str(art), (4, 5, 26, 13))
                    self.assertEqual(output.getvalue(), '\x1b7\x1b8')

    def test_decomposed_accents_normalize_and_fit_lyrics_panel(self):
        self.assertEqual(amui.clean('cancio\u0301n, corazo\u0301n, pin\u0303ata'), 'canción, corazón, piñata')
        ui = make_ui()
        text = 'cancio\u0301n y corazo\u0301n ' * 20
        for limit in range(40):
            self.assertLessEqual(amui.width(amui.clip(text, limit)), limit)
            self.assertNotIn('\u0301', amui.clip(text, limit))
        ui.lyrics.result = (ui.player.track.lyrics_key(), [], [text]*30, 'letras')
        ui.lyrics_panel(1, 70, 30, 60, ui.player.track)
        self.assertTrue(all(70 <= x < 130 for y, x in ui.screen.cells))
        for row in range(2, 30):
            self.assertEqual(ui.screen.cells[row, 129][0], '│')
