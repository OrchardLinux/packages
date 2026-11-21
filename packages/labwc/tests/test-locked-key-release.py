#!/usr/bin/env python3
"""A key press that goes to the client leaves no binding current (0011).

Run by check(): test-locked-key-release.py SOURCE. With the session locked,
a key bound on release (Home) matches a binding that does not apply while
locked; the press goes to the lock screen. The release must follow it, so
the binding must not stay current for the release branch to swallow.
"""
from pathlib import Path
import re
import sys

keyboard = (Path(sys.argv[1]) / 'src/input/keyboard.c').read_text()
start = keyboard.index('\nhandle_compositor_keybindings(')
body = keyboard[start:keyboard.index('\n}\n', start)]
# The release branch swallows the release of a current on-release binding.
assert re.search(r'if \(cur_keybind && cur_keybind->on_release\) \{', body), 'release branch'
# The press that is not the compositor's clears the binding before going on.
tail = body[body.rindex('cur_keybind = match_keybinding('):]
handled = tail.index('return LAB_KEY_HANDLED_TRUE;')
to_client = tail.rindex('return LAB_KEY_HANDLED_FALSE;')
assert 'cur_keybind = NULL;' in tail[handled:to_client], 'a press to the client clears the binding'
print('locked key release: ok')
