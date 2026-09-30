import threading
import unittest
from unittest.mock import Mock, patch
from test_amui import amui
import features as f


class MetadataRecoveryTests(unittest.TestCase):
    def player(self):
        player=amui.Player(threading.Event())
        player.extras=f.Extras(player.stop,player,f.load_config())
        player.extras.api.request=Mock(return_value={'info':dict(name='Song',artistName='Artist',albumName='Album',durationInMillis=120000,playParams={'id':'1'})})
        return player

    def test_empty_mpris_recovered_after_restart_and_track_change(self):
        raw=amui.Track(player='chromium.instance123',length=120)
        for _ in range(2):
            player=self.player()
            with patch.object(amui,'is_cider_player',return_value=True), patch.object(amui,'cider_artwork',return_value='/fixture/art'):
                track=player.recover_metadata(raw)
                self.assertEqual((track.title,track.artist,track.album,track.length,track.art),('Song','Artist','Album',120,'/fixture/art'))
                player.recover_metadata(raw)
                self.assertEqual(player.extras.api.request.call_count,1)
                player.recovery_at=0
                player.extras.api.request.return_value['info']['name']='New Song'
                new=player.recover_metadata(raw)
                self.assertNotEqual(new.identity,track.identity)

    def test_other_chromium_and_valid_mpris_are_not_overridden(self):
        player=self.player()
        with patch.object(amui,'is_cider_player',return_value=False):
            raw=amui.Track(player='chromium.instance123')
            self.assertEqual(player.recover_metadata(raw),raw)
        with patch.object(amui,'is_cider_player',return_value=True):
            raw=amui.Track(player='chromium.instance123',title='MPRIS Song')
            self.assertEqual(player.recover_metadata(raw),raw)
        player.extras.api.request.assert_not_called()

    def test_api_failure_does_not_keep_previous_song(self):
        player=self.player();raw=amui.Track(player='chromium.instance123')
        with patch.object(amui,'is_cider_player',return_value=True), patch.object(amui,'cider_artwork',return_value=''):
            self.assertEqual(player.recover_metadata(raw).title,'Song')
            player.recovery_at=0
            player.extras.api.request.side_effect=OSError('offline')
            self.assertEqual(player.recover_metadata(raw).title,'')

    def test_recovered_metadata_enables_queue_again(self):
        player=self.player();extra=player.extras
        with patch.object(amui,'is_cider_player',return_value=True), patch.object(amui,'cider_artwork',return_value=''):
            player.track=player.recover_metadata(amui.Track(player='chromium.instance123'))
        info=dict(name='Song',artistName='Artist',playParams={'id':'1'},shuffleMode=0,repeatMode=0)
        responses={'now-playing':{'info':info},'volume':{'volume':.4},'queue':[{'id':'1','attributes':info},{'id':'2','attributes':{'name':'Next'}}]}
        extra.api.request=Mock(side_effect=lambda endpoint:responses[endpoint])
        with patch.object(f,'bus',return_value=None):extra.poll(player.track)
        self.assertTrue(extra.api_available)
        self.assertEqual(extra.items,[('Next','')])

    def test_artwork_rejects_non_apple_urls_without_network(self):
        with patch.object(f.urllib.request,'build_opener') as opener:
            for url in ('http://example.com/art','https://localhost/art','https://mzstatic.com.evil/art'):
                self.assertEqual(f.cider_artwork({'artwork':{'url':url}}),'')
            opener.assert_not_called()
