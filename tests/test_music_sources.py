import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch
from test_amui import amui, make_ui
import features as f


class SourceTests(unittest.TestCase):
    def test_cover_modes_and_cancel_restore(self):
        ui = make_ui()
        ui.key('T'); ui.key('1'); ui.key(amui.curses.KEY_DOWN); ui.key('\n')
        self.assertEqual(ui.config['theme_source'], 'cover')
        self.assertEqual(ui.config['palette_mode'], 'complementary')
        self.assertTrue(ui.config['dynamic_palette'])
        ui.key('T'); ui.key('2'); ui.key(amui.curses.KEY_DOWN)
        ui.key('\x1b'); ui.key('\x1b')
        self.assertEqual(ui.config['theme_source'], 'cover')
        self.assertTrue(ui.config['dynamic_palette'])

    def test_custom_editor_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            ui = make_ui()
            ui.custom_path = Path(directory)/'custom-theme.json'
            ui.key('T'); ui.key('3'); ui.key('\n')
            self.assertIsNotNone(ui.custom_edit)
            for color in ['#101020', '#eeeeee', '#aaaaaa', '#777777', '#ff5555', '#55ffaa', '#aa88ff']:
                ui.key('\x15')
                for c in color:
                    ui.key(c)
                ui.key('\n')
            self.assertFalse(ui.theme_menu)
            self.assertEqual(ui.config['theme_source'], 'custom')
            self.assertEqual(f.custom_palette(ui.custom_path), ui.themes['personal'])
            self.assertEqual(json.loads(ui.custom_path.read_text())['background'],'#101020')

    def test_pywal_load_fail_and_live_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            ui = make_ui()
            path = Path(directory)/'colors.json'
            ui.config['pywal_file'] = str(path)
            ui.key('T'); ui.key('4')
            self.assertTrue(ui.theme_menu)
            self.assertIn('Pywal', ui.theme_error)
            data = {'special': {'background':'#101020','foreground':'#eeeeee'},
                    'colors': {f'color{i}':'#ffaaaa' for i in range(16)}}
            path.write_text(json.dumps(data))
            ui.key('4')
            self.assertFalse(ui.theme_menu)
            self.assertEqual(ui.config['theme_source'], 'pywal')
            old = ui.color_target
            data['colors']['color1'] = '#55ffaa'
            path.write_text(json.dumps(data))
            ui.external_colors()
            self.assertNotEqual(old, ui.color_target)
            path.write_text('bad json')
            ui.external_check_at = 0
            target = ui.color_target
            ui.external_colors()
            self.assertEqual(target, ui.color_target)

    def test_three_palette_modes_have_distinct_readable_accents(self):
        if not f.shutil.which('magick'):
            self.skipTest('ImageMagick optional')
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CACHE_HOME':directory}):
            path = Path(directory)/'art.ppm'
            path.write_bytes(b'P6\n2 2\n255\n'+bytes([40,100,160])*4)
            palettes = [f.dominant_palette(str(path),amui.THEMES['nocturne'],mode=mode)
                        for mode in ('extract','complementary','contrast')]
            self.assertEqual(len(set(palettes)),3)
            for palette in palettes:
                self.assertTrue(all(f.contrast(f.rgb(palette[0]),f.rgb(c)) >= 4.5 for c in palette[4:]))

    def test_music_input_never_dispatches_playback_shortcuts(self):
        ui = make_ui()
        ui.music = Mock(items=[], busy=False)
        ui.player.send = Mock()
        ui.key('b')
        for c in 'sneaky music': ui.key(c)
        self.assertEqual(ui.music_query,'sneaky music')
        ui.key('\n')
        ui.music.search.assert_called_once_with('sneaky music',False,'songs','')
        ui.player.send.assert_not_called()
        item = dict(id='1',type='songs',title='One',artist='Artist',album='Album')
        ui.music.items=[item]
        ui.key('\n'); ui.key('+'); ui.key('n')
        self.assertEqual([c.args[1] for c in ui.music.choose.call_args_list],['play-item','play-later','play-next'])

    def test_music_panel_sizes(self):
        for h,w in [(2,30),(12,45),(24,80),(40,140)]:
            ui=make_ui(h,w)
            ui.music=Mock(items=[dict(title='Long title '*10,artist='Artist',album='Album')]*25,label='25 resultados')
            ui.music_index=24
            ui.music_panel()
            self.assertTrue(ui.screen.cells)

    def test_cider_http_catalog_library_play_and_pagination(self):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path,body,self.headers.get('apptoken')))
                path=body.get('path','')
                if path=='/v1/me/storefront':
                    response={'data':{'data':[{'id':'mx'}]}}
                elif path.startswith('/v1/catalog/'):
                    response={'data':{'results':{'songs':{'data':[{'id':'12','type':'songs','attributes':{'name':'Song','artistName':'Artist'}}], 'next':'/v1/catalog/mx/search?offset=25'}}}}
                elif path.startswith('/v1/me/library/'):
                    response={'data':{'data':[{'id':'p.1','type':'library-playlists','attributes':{'name':'Playlist'}}]}}
                else: response={'status':'ok'}
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(response).encode())
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            conf=f.load_config()
            conf['cider']={'url':f'http://127.0.0.1:{server.server_port}','token_file':'/nonexistent'}
            stop=threading.Event(); browser=f.MusicBrowser(stop,conf)
            with patch.dict(os.environ,{'AMUI_CIDER_TOKEN':'fixture-token'}):
                items,more=browser.lookup('space & café',False,'songs','')
                self.assertEqual(items[0]['id'],'12')
                browser.lookup('',False,'songs',more)
                library,_=browser.lookup('',True,'playlists','')
                self.assertEqual(library[0]['type'],'library-playlists')
                browser.thread.start(); browser.choose(items[0])
                deadline=time.monotonic()+2
                while browser.busy and time.monotonic()<deadline: time.sleep(.01)
                self.assertFalse(browser.busy)
                stop.set(); browser.thread.join(1)
            self.assertEqual(requests[-1][0],'/api/v1/playback/play-item')
            self.assertEqual(requests[-1][1],{'id':'12','type':'songs'})
            self.assertTrue(all(token=='fixture-token' for _,_,token in requests))
            self.assertIn('space+%26+caf%C3%A9',requests[1][1]['path'])
        finally:
            server.shutdown(); server.server_close()

    def test_stale_search_is_discarded_and_worker_errors_recover(self):
        conf=f.load_config(); stop=threading.Event(); browser=f.MusicBrowser(stop,conf)
        started,release=threading.Event(),threading.Event()
        def lookup(term,*args):
            if term=='old':
                started.set(); release.wait(2)
                return [dict(title='Old')],''
            if term=='bad': raise ValueError('Bad response')
            return [dict(title='New')],''
        browser.lookup=lookup; browser.thread.start()
        try:
            browser.search('old'); self.assertTrue(started.wait(1)); browser.search('new'); release.set()
            deadline=time.monotonic()+2
            while browser.busy and time.monotonic()<deadline: time.sleep(.01)
            self.assertEqual(browser.items,[dict(title='New')])
            browser.search('bad')
            deadline=time.monotonic()+2
            while browser.busy and time.monotonic()<deadline: time.sleep(.01)
            self.assertFalse(browser.busy)
            self.assertIn('No se pudo',browser.label)
        finally:
            release.set(); stop.set(); browser.thread.join(1)

    def test_saved_appearance_survives_restart_and_manual_toml_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'config.toml'
            path.write_text('theme = "nocturne"\n')
            conf=f.load_config(path)
            conf.update(theme_source='pywal',palette_mode='contrast')
            f.save_appearance(conf,'ocean',path)
            restored=f.load_config(path); f.restore_appearance(restored,path)
            self.assertEqual((restored['theme'],restored['theme_source'],restored['palette_mode']),('ocean','pywal','contrast'))
            path.write_text('theme = "forest"\n')
            restored=f.load_config(path); f.restore_appearance(restored,path)
            self.assertEqual(restored['theme'],'forest')

    def test_personal_does_not_override_explicit_custom_theme(self):
        ui=make_ui()
        conf=ui.config.copy()
        conf.update(theme_source='custom',themes={'named':amui.THEMES['ice']})
        f.atomic_json(ui.custom_path,dict(zip(f.COLOR_NAMES,amui.THEMES['sunset'])))
        options=amui.argparse.Namespace(theme='named',no_lyrics=False,no_cava=False,config_data=conf,config=str(ui.config_path))
        restarted=amui.UI(ui.screen,ui.player,ui.lyrics,ui.spectrum,options)
        self.assertEqual(restarted.theme,'named')

    def test_more_results_append_and_preserve_selection(self):
        conf=f.load_config(); stop=threading.Event(); browser=f.MusicBrowser(stop,conf)
        def lookup(term,library,kind,path):
            return [dict(id=str(i),type='songs',title=str(i),artist='',album='') for i in ([2,3] if path else [1,2])], '' if path else '/v1/catalog/mx/search?offset=2'
        browser.lookup=lookup; browser.thread.start()
        try:
            browser.search('x')
            deadline=time.monotonic()+2
            while browser.busy and time.monotonic()<deadline: time.sleep(.01)
            self.assertEqual(len(browser.items),2)
            ui=make_ui(); ui.music=browser; ui.music_index=1
            ui.music_query='x'; ui.music_search(browser.next_path)
            deadline=time.monotonic()+2
            while browser.busy and time.monotonic()<deadline: time.sleep(.01)
            self.assertEqual([item['id'] for item in browser.items],['1','2','3'])
            self.assertEqual(ui.music_index,1)
        finally: stop.set(); browser.thread.join(1)

    def test_play_error_does_not_claim_success(self):
        browser=f.MusicBrowser(threading.Event(),f.load_config())
        browser.api.request=Mock(return_value={'status':'error'})
        browser.thread.start()
        try:
            browser.choose(dict(id='12',type='songs',title='Song'))
            deadline=time.monotonic()+2
            while browser.busy and time.monotonic()<deadline: time.sleep(.01)
            self.assertNotIn('solicitada',browser.label)
            self.assertFalse(browser.busy)
        finally: browser.stop.set(); browser.thread.join(1)
