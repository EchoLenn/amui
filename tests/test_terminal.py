"""PTY acceptance tests: curses, real input, resize, prompts and clean exit."""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TerminalTests(unittest.TestCase):
    def open_ui(self, directory, mini=False):
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 2 if mini else 40, 140, 0, 0))
        env = dict(os.environ, TERM="xterm-256color", XDG_CONFIG_HOME=directory, XDG_CACHE_HOME=directory,
                   AMUI_FIXTURE_ACTIONS=directory + "/actions.jsonl", AMUI_FIXTURE_MUSIC_ACTIONS=directory + '/music.jsonl')
        env.pop("KITTY_WINDOW_ID", None)
        env.pop("TERM_PROGRAM", None)
        process = subprocess.Popen([sys.executable, str(ROOT / "tests/ui_fixture.py"), *(["--mini"] if mini else [])],
                                   stdin=slave, stdout=slave, stderr=slave, env=env, start_new_session=True)
        return master, slave, process

    def read(self, master, seconds=.15):
        data = b""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if select.select([master], [], [], max(0, end - time.monotonic()))[0]:
                try:
                    data += os.read(master, 65536)
                except OSError:
                    break
        return data

    def test_full_ui_controls_prompt_export_resize_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            master, slave, process = self.open_ui(directory)
            output = b""
            try:
                output += self.read(master, .7)
                self.assertIn(b"UP NEXT", output)
                self.assertIn(b"LYRICS", output)
                os.write(master, b"T")
                output += self.read(master, .2)
                self.assertIn(b"VISTA PREVIA", output)
                self.assertIn(b"Pywal", output)
                os.write(master, b"2")
                output += self.read(master, .2)
                self.assertIn(b"sakura", output)
                os.write(master, b"\x1bOB\n")
                output += self.read(master, .2)
                os.write(master, b"se")
                output += self.read(master, .2)
                os.write(master, b"/\x15Manual Title\n\x15Manual Artist\n")
                output += self.read(master, .3)
                os.write(master, b"S\x15" + directory.encode() + b"/export\n")
                output += self.read(master, .3)
                self.assertTrue(list((Path(directory) / "export").glob("*.lrc")))
                os.write(master, b"Q?\x1bft")
                output += self.read(master, .2)
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 22, 48, 0, 0))
                process.send_signal(signal.SIGWINCH)
                output += self.read(master, .2)
                os.write(master, b"q")
                output += self.read(master, .3)
                process.wait(timeout=3)
                self.assertEqual(process.returncode, 0, output[-2000:].decode(errors="replace"))
                self.assertNotIn(b"Traceback", output)
                self.assertIn(b"\x1b[?1049l", output)
                self.assertTrue(termios.tcgetattr(slave)[3] & termios.ECHO)
                self.assertEqual([json.loads(line) for line in (Path(directory) / "actions.jsonl").read_text().splitlines()],
                                 ["shuffle", "repeat"])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)
                os.close(slave)

    def test_mini_two_line_terminal_and_sigterm(self):
        with tempfile.TemporaryDirectory() as directory:
            master, slave, process = self.open_ui(directory, mini=True)
            try:
                output = self.read(master, .5)
                self.assertIn(b"Midnight Frequencies", output)
                process.terminate()
                output += self.read(master, .3)
                process.wait(timeout=3)
                self.assertEqual(process.returncode, 0)
                self.assertNotIn(b"Traceback", output)
                self.assertTrue(termios.tcgetattr(slave)[3] & termios.ICANON)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)
                os.close(slave)

    def test_library_queue_confirmation_and_timer_in_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            master, slave, process = self.open_ui(directory)
            try:
                output=self.read(master,.5)
                os.write(master,b'HAQd')
                output+=self.read(master,.2)
                self.assertIn('¿Borrar canción?'.encode(),output)
                os.write(master,b'\x1b')
                output+=self.read(master,.1)
                os.write(master,b'c\n')
                output+=self.read(master,.2)
                os.write(master,b'\x1bZ')
                output+=self.read(master,.2)
                self.assertIn(b'TEMPORIZADOR',output)
                os.write(master,b'\n')
                output+=self.read(master,.2)
                os.write(master,b'Z\x1bOA\n')
                output+=self.read(master,.2)
                os.write(master,b'q');process.wait(timeout=3)
                events=[json.loads(line) for line in (Path(directory)/'actions.jsonl').read_text().splitlines()]
                self.assertEqual([e[0] for e in events],['library','library','queue'])
                self.assertEqual([e[1] for e in events[:2]],['favorite','add'])
                self.assertEqual(events[2][3],'clear_pending')
                self.assertEqual(process.returncode,0,output[-1500:])
            finally:
                if process.poll() is None: process.kill();process.wait()
                os.close(master);os.close(slave)

    def test_queue_selection_in_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            master, slave, process = self.open_ui(directory)
            try:
                output=self.read(master,.5)
                os.write(master,b'Q'); output+=self.read(master,.2)
                os.write(master,b'\x1bOB\x1bOB\n'); output+=self.read(master,.3)
                os.write(master,b'\x1b'); output+=self.read(master,.1)
                os.write(master,b'q'); process.wait(timeout=3)
                events=[json.loads(line) for line in (Path(directory)/'actions.jsonl').read_text().splitlines()]
                jumps=[event for event in events if isinstance(event,list) and event[0]=='queue']
                self.assertEqual(len(jumps),1)
                self.assertEqual(jumps[0][1],2)
                self.assertNotIn('down',events)
                self.assertEqual(process.returncode,0,output[-1000:])
            finally:
                if process.poll() is None: process.kill(); process.wait()
                os.close(master); os.close(slave)

    def test_collection_open_play_and_back_in_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            master, slave, process = self.open_ui(directory)
            try:
                output=self.read(master,.5)
                os.write(master,b'bfixture\x1bOC\n')
                output+=self.read(master,.4)
                os.write(master,b'\n')
                output+=self.read(master,.4)
                self.assertIn(b'Collection Track',output)
                os.write(master,b'\n+P')
                output+=self.read(master,.2)
                os.write(master,b'\x1b')
                output+=self.read(master,.2)
                os.write(master,b'P')
                output+=self.read(master,.2)
                os.write(master,b'\x1b')
                output+=self.read(master,.1)
                os.write(master,b'q'); process.wait(timeout=3)
                events=[json.loads(line) for line in (Path(directory)/'music.jsonl').read_text().splitlines()]
                self.assertEqual([e['item']['type'] for e in events],['songs','songs','albums','albums'])
                self.assertEqual(events[1]['action'],'play-later')
                self.assertEqual(process.returncode,0,output[-1000:])
            finally:
                if process.poll() is None: process.kill(); process.wait()
                os.close(master); os.close(slave)

    def test_music_browser_input_selection_and_library_in_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            master, slave, process = self.open_ui(directory)
            try:
                output = self.read(master,.5)
                os.write(master,b'bfixture\n')
                output += self.read(master,.4)
                self.assertIn(b'ELIGE TU', output)
                self.assertIn(b'Fixture Search Result',output)
                os.write(master,b'\n+n')
                output += self.read(master,.2)
                os.write(master,b'\t')
                output += self.read(master,.3)
                os.write(master,b'\n')
                output += self.read(master,.2)
                os.write(master,b'\x1b')
                output += self.read(master,.1)
                os.write(master,b'q'); process.wait(timeout=3)
                events=[json.loads(line) for line in (Path(directory)/'music.jsonl').read_text().splitlines()]
                self.assertEqual([e['action'] for e in events],['play-item','play-later','play-next','play-item'])
                self.assertEqual(events[-1]['item']['type'],'library-songs')
                self.assertEqual(process.returncode,0,output[-1000:])
                self.assertNotIn(b'Traceback',output)
            finally:
                if process.poll() is None: process.kill(); process.wait()
                os.close(master); os.close(slave)
