"""Execute the actual dependency-free Cider plugin against a simulated host."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node is only needed to verify the optional Cider bridge")
class FavoriteBridgeTests(unittest.TestCase):
    def run_plugin(self, body):
        path = Path(__file__).resolve().parents[1] / "share/amui/cider-plugin/plugin.js"
        script = """
import fs from 'node:fs';
import assert from 'node:assert/strict';
const source = fs.readFileSync(PLUGIN_PATH, 'utf8');
const plugin = (await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))).default;
const bus = new EventTarget();
const calls = [];
const attributes = {playParams: {id:'123',kind:'song',isLibrary:false},inFavorites:false};
const item = {id:'123',type:'songs'};
globalThis.window = {__PLUGINSYS__:{ExternalMessages:bus},CiderApp:{RPC:{
  nowPlayingAttributes:attributes, nowPlayingMediaItem:item},v3: async (...args) => {calls.push(args); return {};}}};
function send(data) { const e = new Event('amui:favorite'); e.detail=data; bus.dispatchEvent(e); }
function message(request='test:1', state=true) { return {id:'123',type:'songs',state,request}; }
const flush = () => new Promise(resolve=>setImmediate(resolve));
plugin.setup();
""".replace("PLUGIN_PATH", json.dumps(str(path)))
        result = subprocess.run(["node", "--input-type=module"], input=script + body,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exact_favorites_endpoint_and_methods_without_local_cache_changes(self):
        self.run_plugin("""
send(message()); await flush();
send(message('test:2', false)); await flush();
assert.deepEqual(calls, [
 ['/v1/me/favorites', {'ids[songs]':'123'}, {paramsInURL:true,fetchOptions:{method:'POST'}}],
 ['/v1/me/favorites', {'ids[songs]':'123'}, {paramsInURL:true,fetchOptions:{method:'DELETE'}}]
]);
assert.equal(attributes.inFavorites, false);
""")

    def test_malformed_or_stale_messages_do_not_mutate_library(self):
        self.run_plugin("""
for (const change of [{id:'456'}, {id:'../123'}, {type:'albums'}, {state:'true'},
 {request:''}, {request:'x'.repeat(129)}, {id:'x'.repeat(129)}, {request:'test/1'}]) {
 send({...message('test:'+Math.random()),...change});
}
send(null); send({}); await flush();
assert.equal(calls.length, 0);
""")

    def test_catalog_and_library_music_ids_match_the_current_item(self):
        self.run_plugin("""
attributes.playParams = {id:'i.library123',catalogId:'123',kind:'song',isLibrary:true};
send(message()); await flush();
assert.equal(calls.length, 1);
attributes.playParams = {id:'i.library123',kind:'song',isLibrary:true};
send({...message('test:2'),id:'i.library123',type:'library-songs'}); await flush();
attributes.playParams = {id:'987',kind:'musicVideo'};
send({...message('test:3'),id:'987',type:'music-videos'}); await flush();
assert.deepEqual(calls.map(c=>c[1]), [{'ids[songs]':'123'}, {'ids[library-songs]':'i.library123'}, {'ids[music-videos]':'987'}]);
""")

    def test_serializes_deduplicates_and_revalidates_pending_track(self):
        self.run_plugin("""
let release;
window.CiderApp.v3 = (...args) => {calls.push(args); return new Promise(resolve => {release=resolve;});};
send(message()); send(message()); send(message('test:2',false)); await flush();
assert.equal(calls.length,1);
attributes.playParams.id='456'; item.id='456';
release({}); await flush();
assert.equal(calls.length,1);
""")

    def test_captures_validated_fields_before_asynchronous_execution(self):
        self.run_plugin("""
const request=message(); send(request); request.state=false; request.id='456';
await flush();
assert.equal(calls.length,1);
assert.equal(calls[0][2].fetchOptions.method,'POST');
assert.equal(calls[0][1]['ids[songs]'],'123');
""")

    def test_failure_does_not_block_next_operation_or_show_optimistic_state(self):
        self.run_plugin("""
window.CiderApp.v3 = async (...args) => {calls.push(args); if(calls.length===1) throw new Error('HTTP error'); return {};};
send(message()); send(message('test:2',false)); await flush();
assert.equal(calls.length,2);
assert.equal(attributes.inFavorites,false);
""")

    def test_setup_and_teardown_keep_one_listener_and_cancel_pending_calls(self):
        self.run_plugin("""
plugin.setup(); send(message()); await flush();
assert.equal(calls.length,1);
send(message('test:2',false)); plugin.teardown(); await flush();
assert.equal(calls.length,1);
send(message('test:3',false)); await flush();
assert.equal(calls.length,1);
plugin.setup(); send(message('test:4',false)); await flush();
assert.equal(calls.length,2);
""")


if __name__ == "__main__":
    unittest.main()
