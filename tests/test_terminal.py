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
                   AMUI_FIXTURE_ACTIONS=directory + "/actions.jsonl")
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
