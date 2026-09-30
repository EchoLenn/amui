import threading
import time
import unittest
from unittest.mock import Mock

from test_amui import amui, make_ui
import features as f


def item(ident='1', kind='albums'):
    return dict(id=ident, type=kind, title='Collection '+ident, artist='Artist', album='Album')


class CollectionTests(unittest.TestCase):
    def browser(self):
        browser = f.MusicBrowser(threading.Event(), f.load_config())
        self.addCleanup(browser.stop.set)
        return browser

    def settle(self, browser):
        deadline = time.monotonic()+2
        while browser.busy and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertFalse(browser.busy)

    def test_routes_catalog_library_and_pagination(self):
        browser = self.browser()
        browser.storefront = 'mx'
        for kind in ('albums', 'playlists', 'library-albums', 'library-playlists'):
            library = kind.startswith('library-')
            resource = 'library-songs' if library else 'songs'
            base = '/v1/me/library' if library else '/v1/catalog/mx'
            path = f'{base}/{kind.removeprefix("library-")}/1/tracks'
            browser.api.music = Mock(return_value={'data': [dict(id='s.1', type=resource, attributes={'name':'Canción'})], 'next':path+'?offset=25'})
            tracks, next_path = browser.lookup_tracks(item(kind=kind))
            self.assertEqual(tracks[0]['type'], resource)
            browser.api.music.assert_called_with(path+'?limit=25')
            browser.lookup_tracks(item(kind=kind), next_path)
            browser.api.music.assert_called_with(path+'?offset=25')
        for invalid in (item('../bad'), item(kind='songs')):
            with self.assertRaises(ValueError):
                browser.lookup_tracks(invalid)

    def test_ui_enter_opens_without_playing_and_back_restores_selection(self):
        ui = make_ui(); browser = self.browser(); ui.music = browser
        browser.items = [item('1'), item('2')]
        browser.next_path = '/v1/catalog/mx/search?offset=25'
        browser.label = '2 resultados'
        ui.music_open, ui.music_editing, ui.music_index = True, False, 1
        browser.choose = Mock()
        ui.music_key('\n')
        browser.choose.assert_not_called()
        self.assertEqual(ui.music_collection['id'], '2')
        self.assertTrue(browser.busy)
        ui.music_key('\x1b')
        self.assertIsNone(ui.music_collection)
        self.assertTrue(ui.music_open)
        self.assertFalse(browser.busy)
        self.assertEqual(ui.music_index, 1)
        self.assertEqual([row['id'] for row in browser.items], ['1', '2'])
        self.assertTrue(browser.next_path.endswith('offset=25'))

    def test_detail_controls_and_small_layout(self):
        for size in ((12,45),(24,80),(40,140)):
            ui=make_ui(*size); browser=self.browser(); ui.music=browser
            ui.music_editing=False; ui.music_collection=item(); ui.music_kind='albums'
            browser.items=[item('song', 'songs')]; browser.choose=Mock()
            for key in ('\n','+','n','P'): ui.music_key(key)
            self.assertEqual([call.args[0]['type'] for call in browser.choose.call_args_list], ['songs','songs','songs','albums'])
            ui.music_key(amui.curses.KEY_RIGHT)
            self.assertEqual(ui.music_kind,'albums')
            ui.music_panel()

    def test_late_collection_response_cannot_replace_parent(self):
        browser=self.browser(); started=threading.Event(); release=threading.Event()
        def lookup(*args):
            started.set(); release.wait(2)
            return [item('child','songs')], ''
        browser.lookup_tracks=lookup
        browser.thread.start()
        try:
            browser.tracks(item()); self.assertTrue(started.wait(1))
            browser.restore(([item('parent')], '', 'restored'))
            release.set(); browser.stop.set(); browser.thread.join(2)
            self.assertEqual(browser.items[0]['id'], 'parent')
            self.assertEqual(browser.label, 'restored')
        finally:
            release.set(); browser.stop.set(); browser.thread.join(2)

    def test_pagination_keeps_playlist_duplicates_and_retry_path(self):
        browser=self.browser()
        browser.lookup_tracks=Mock(return_value=([item('s','songs')], '/v1/me/library/playlists/p/tracks?offset=25'))
        browser.thread.start()
        try:
            browser.tracks(item(kind='library-playlists')); self.settle(browser)
            path=browser.next_path
            browser.lookup_tracks.side_effect=OSError('offline')
            browser.tracks(item(kind='library-playlists'),path); self.settle(browser)
            self.assertEqual(browser.next_path,path)
            self.assertEqual(len(browser.items),1)
            browser.lookup_tracks.side_effect=None
            browser.lookup_tracks.return_value=([item('s','songs')],'')
            browser.tracks(item(kind='library-playlists'),path); self.settle(browser)
            self.assertEqual([row['id'] for row in browser.items], ['s','s'])
        finally:
            browser.stop.set(); browser.thread.join(2)
