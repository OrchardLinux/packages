#!/usr/bin/env python3
"""Compile the patched option clause and cursor initialization with fixtures.

Run by check(): test-hide-cursor.py SOURCE. Covers the default, boolean parsing,
initial visibility and pointer-capable device detection. This is a unit check;
it does not exercise DRM scanout refusal or virtual-pointer event delivery.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

source = Path(sys.argv[1])
config = (source / 'src/config/rcxml.c').read_text()
seat = (source / 'src/seat.c').read_text()
assert 'bool hide_cursor_until_pointer_input;' in (source / 'include/config/rcxml.h').read_text()


def extract_function(text, name):
    match = re.search(r'static bool\n' + name + r'\([^;{}]*\)\s*\{', text)
    assert match, name
    end = text.index('{', match.start()) + 1
    depth = 1
    while depth:
        if text[end] == '{': depth += 1
        if text[end] == '}': depth -= 1
        end += 1
    return text[match.start():end]


clause = re.search(
    r'else if \(!strcasecmp\(nodename, "hideCursorUntilPointerInput.core"\)\) \{\n([^{}]*)\}',
    config,
)
assert clause
initial = re.search(r'\tseat->cursor_visible = [^;]+;', seat[seat.index('seat_init(void)'):])
default = re.search(r'\trc.hide_cursor_until_pointer_input = [^;]+;', config[config.index('rcxml_init(void)'):])
assert initial and default
prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <strings.h>
#include <wayland-server-core.h>
#include <wlr/types/wlr_input_device.h>
#include "common/parse-bool.h"
#include "input/input.h"
static struct { bool hide_cursor_until_pointer_input; } rc;
struct seat { bool cursor_visible; struct wl_list inputs; };
static void defaults(void) {
'''
fixture = prefix + default.group() + r'''
}
static void parse_option(const char *nodename, const char *content) {
    if (false) {}
''' + clause.group() + r'''
}
static void initialize_cursor(struct seat *seat) {
''' + initial.group() + '\n}\n' + extract_function(seat, 'seat_has_pointer_device')
fixture += r'''
int main(void) {
    struct seat seat = {0};
    wl_list_init(&seat.inputs);
    defaults();
    initialize_cursor(&seat);
    assert(!rc.hide_cursor_until_pointer_input && seat.cursor_visible);
    /* Only this core option changes the setting. */
    parse_option("hideCursorUntilPointerInput.other", "yes");
    assert(!rc.hide_cursor_until_pointer_input);
    const char *enabled[] = {"yes", "true", "on", "1", "YES"};
    for (unsigned i = 0; i < sizeof(enabled)/sizeof(enabled[0]); ++i) {
        parse_option("hideCursorUntilPointerInput.core", enabled[i]);
        initialize_cursor(&seat);
        assert(rc.hide_cursor_until_pointer_input && !seat.cursor_visible);
    }
    parse_option("hidecursoruntilpointerinput.CORE", "invalid");
    assert(rc.hide_cursor_until_pointer_input);
    const char *disabled[] = {"no", "false", "off", "0", "NO"};
    for (unsigned i = 0; i < sizeof(disabled)/sizeof(disabled[0]); ++i) {
        parse_option("hidecursoruntilpointerinput.CORE", disabled[i]);
        initialize_cursor(&seat);
        assert(!rc.hide_cursor_until_pointer_input && seat.cursor_visible);
    }
    parse_option("hideCursorUntilPointerInput.core", "yes");
    defaults(); /* Removing the option on reconfigure restores its default. */
    initialize_cursor(&seat);
    assert(!rc.hide_cursor_until_pointer_input && seat.cursor_visible);
    assert(!seat_has_pointer_device(&seat));
    struct wlr_input_device devices[] = {
        {.type = WLR_INPUT_DEVICE_TOUCH}, {.type = WLR_INPUT_DEVICE_KEYBOARD},
        {.type = WLR_INPUT_DEVICE_POINTER}, {.type = WLR_INPUT_DEVICE_TABLET},
    };
    struct input inputs[4];
    for (unsigned i = 0; i < 4; ++i) {
        inputs[i].wlr_input_device = &devices[i];
        wl_list_insert(&seat.inputs, &inputs[i].link);
        assert(seat_has_pointer_device(&seat) == (i >= 2));
    }
    wl_list_remove(&inputs[2].link);
    assert(seat_has_pointer_device(&seat)); /* Tablet still supplies a pointer. */
    wl_list_remove(&inputs[3].link);
    assert(!seat_has_pointer_device(&seat));
    puts("hide cursor: parsed booleans, default/reset, initial visibility and pointer device detection OK");
}
'''
with tempfile.TemporaryDirectory(prefix='hide-cursor-') as tmp:
    root = Path(tmp)
    (root / 'test.c').write_text(fixture)
    flags = subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', 'wlroots-0.20', 'wayland-server'], text=True,
    ).split()
    subprocess.run([
        'cc', '-DWLR_USE_UNSTABLE', '-Wall', '-Wextra', '-Werror',
        '-I' + str(source / 'include'), str(root / 'test.c'),
        str(source / 'src/common/parse-bool.c'), '-o', str(root / 'test'), *flags,
    ], check=True)
    subprocess.run([str(root / 'test')], check=True)
