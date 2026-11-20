#!/usr/bin/env python3
"""Compile the patched focus update against stubs (0008).

Run by check(): test-touch-pointer-focus.py SOURCE. While the cursor is hidden
(touch input hid it, or no pointer input yet) a focus update clears pointer
focus and looks up nothing under the cursor; a visible cursor updates as before.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

source = Path(sys.argv[1])
cursor = (source / 'src/input/cursor.c').read_text()
match = re.search(r'static void\n_cursor_update_focus\(void\)\n\{', cursor)
assert match, '_cursor_update_focus'
end = cursor.index('{', match.start()) + 1
depth = 1
while depth:
    if cursor[end] == '{': depth += 1
    if cursor[end] == '}': depth -= 1
    end += 1
function = cursor[match.start():end]

fixture = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
struct wlr_seat { int unused; };
struct seat { bool cursor_visible; struct wlr_seat *wlr_seat; };
static struct wlr_seat the_seat;
static struct { struct seat seat; } server = { { false, &the_seat } };
static struct { bool focus_follow_mouse, focus_follow_mouse_requires_movement, raise_on_focus; } rc;
struct cursor_context { void *view, *surface; };
static int cleared, looked_up, updated;
static void wlr_seat_pointer_notify_clear_focus(struct wlr_seat *s) { (void)s; cleared++; }
static struct cursor_context get_cursor_context(void) { looked_up++; struct cursor_context c = { 0, 0 }; return c; }
static void desktop_focus_view_or_surface(struct seat *s, void *v, void *f, bool r) { (void)s; (void)v; (void)f; (void)r; }
static void cursor_update_common(const struct cursor_context *c, struct cursor_context *n) { (void)c; (void)n; updated++; }
''' + function + r'''
int main(void) {
    _cursor_update_focus();
    assert(cleared == 1 && looked_up == 0 && updated == 0);
    server.seat.cursor_visible = true;
    _cursor_update_focus();
    assert(cleared == 1 && looked_up == 1 && updated == 1);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as work:
    c = Path(work) / 'focus.c'
    c.write_text(fixture)
    binary = Path(work) / 'focus'
    subprocess.run(['cc', '-Wall', '-Werror', '-o', str(binary), str(c)], check=True)
    subprocess.run([str(binary)], check=True)
print('pointer focus while hidden: ok')
