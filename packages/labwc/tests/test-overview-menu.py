#!/usr/bin/env python3
"""A card's menu in the overview (0010): how presses, keys and leaving treat it.

Run by check(): test-overview-menu.py SOURCE. A reading of the patched
overview.c; the menu's drawing and the window actions need a compositor.
"""
from pathlib import Path
import re
import sys

source = Path(sys.argv[1])
overview = (source / 'src/overview.c').read_text()


def body(name):
    start = overview.index('\n' + name + '(')
    return overview[start:overview.index('\n}\n', start)]


press = body('overview_press')
menu_branch = press[press.index('if (card_menu.tree)'):press.index('if (!on_overview')]
# A press beside the menu puts only the menu away: the overview is not left.
assert 'card_menu_close();' in menu_branch and 'finish(' not in menu_branch
assert re.search(r'return true;\s*\}\s*if \(!on_overview', press), 'the press is the menu\'s'
# A press held still on a card arms the menu; moving disarms it.
assert 'card_menu_hold_arm(ov.press.card != NULL)' in press
assert 'card_menu_hold_arm(false)' in body('overview_motion')
release = body('overview_release')
assert release.index('card_menu_hold_arm(false)') < release.index('if (!ov.press.down)')
assert 'card_menu_run(card_menu.current)' in release
# Escape closes the menu before it would close the overview.
keys = body('overview_handle_key')
assert keys.index('if (card_menu.tree)') < keys.index('finish(NULL)')
# The items: Minimize only for a window not minimized, then Maximize/Restore, Close.
opened = body('card_menu_open')
assert re.search(r'if \(!view->minimized\) \{\s*card_menu\.items\[card_menu\.nr_items\+\+\] = CARD_MENU_MINIMIZE;', opened)
# Leaving the overview takes the menu along.
assert 'card_menu_close();' in body('finish')
assert 'card_menu_close();' in body('destroy')
assert re.search(r'#define CARD_MENU_ITEM_HEIGHT (\d+)', overview).group(1) == '44'
print('ok')
