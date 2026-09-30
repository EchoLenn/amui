import threading
import unittest
from unittest.mock import Mock
from test_amui import amui, make_ui
import features as f


class QueueNavigationTests(unittest.TestCase):
    def setup_queue(self):
        ui = make_ui()
        extra = f.Extras(threading.Event(), ui.player, f.load_config())
        ui.extras = ui.player.extras = extra
        track = ui.player.track
        current = dict(name=track.title, artistName=track.artist, playParams={'id':'0'})
        data = [dict(id=str(i), type='song', attributes=dict(name=track.title if i == 0 else f'Track {i}', artistName=track.artist)) for i in range(20)]
        rows, _ = f.cider_queue(data,current,True)
        extra.queue_view = (track.identity,tuple(rows),f.queue_signature(data))
        extra.identity=track.identity
        extra.items=[(t,a) for _,t,a in rows]
        extra.api.request=Mock(side_effect=lambda endpoint,payload=None: {'info':current} if endpoint=='now-playing' else data if endpoint=='queue' else {'status':'ok'})
        return ui, extra, data, current

    def test_navigation_does_not_change_volume_and_scrolls_full_queue(self):
        ui, extra, _, _ = self.setup_queue()
        ui.key('Q'); ui.render()
        for _ in range(12): ui.key(amui.curses.KEY_DOWN)
        ui.render()
        self.assertEqual(ui.queue_index,12)
        self.assertTrue(ui.player.actions.empty())
        ui.key('\n')
        _, action=ui.player.actions.get_nowait()
        self.assertEqual(action[:2],('queue',12))
        ui.key('\x1b'); self.assertFalse(ui.queue_focus)

    def test_jump_uses_absolute_index_not_visible_index_or_play_item(self):
        ui, extra, data, current = self.setup_queue()
        notice=extra.jump_queue(extra.queue_view,7)
        self.assertIn('solicitado',notice)
        extra.api.request.assert_called_with('queue/change-to-index',{'index':8})
        self.assertFalse(any(call.args[0] in ('play-item','play-next','play-later') for call in extra.api.request.call_args_list))

    def test_queue_change_and_player_change_refuse_jump(self):
        ui, extra, data, current = self.setup_queue()
        data[2],data[3]=data[3],data[2]
        self.assertIn('cola cambió',extra.jump_queue(extra.queue_view,2))
        self.assertFalse(any(len(call.args)>1 for call in extra.api.request.call_args_list))
        view=('old identity',extra.queue_view[1],extra.queue_view[2])
        self.assertIn('canción cambió',extra.jump_queue(view,2))

    def test_duplicate_current_is_not_guessed_and_all_upcoming_kept(self):
        ui, extra, data, current = self.setup_queue()
        self.assertEqual(len(extra.queue_view[1]),19)
        data.append(data[0])
        self.assertEqual(f.cider_queue(data,current,True)[0],[])
        rows,_=f.cider_queue({'items':data,'position':0},current,True)
        self.assertEqual(rows[-1][0],20)

    def test_failure_is_reported_and_refresh_resets_selection(self):
        ui, extra, data, current = self.setup_queue()
        ui.key('Q'); ui.render(); ui.key(amui.curses.KEY_END)
        self.assertEqual(ui.queue_index,18)
        extra.api.request.side_effect=OSError('offline')
        ui.player.act(ui.player.track.player,('queue',1,extra.queue_view))
        self.assertIn('No se pudo',ui.player.notice)
        extra.queue_view=(extra.identity,extra.queue_view[1][:2],('changed',))
        ui.render(); self.assertEqual(ui.queue_index,0)
