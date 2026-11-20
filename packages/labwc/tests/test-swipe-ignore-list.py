#!/usr/bin/env python3
"""Compile the patched namespace list match against stubs (0009).

Run by check(): test-swipe-ignore-list.py SOURCE. bottomSwipeIgnoreNamespace
is a comma-separated list; a single name matches as before, and a name only
matches whole.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

source = Path(sys.argv[1])
touch = (source / 'src/input/touch.c').read_text()
match = re.search(r'static bool\nnamespace_listed\([^)]*\)\n\{', touch)
assert match, 'namespace_listed'
end = touch.index('{', match.start()) + 1
depth = 1
while depth:
    if touch[end] == '{': depth += 1
    if touch[end] == '}': depth -= 1
    end += 1
fixture = '#include <assert.h>\n#include <stdbool.h>\n#include <string.h>\n' + touch[match.start():end] + r'''
int main(void) {
    assert(namespace_listed("wvkbd", "wvkbd"));
    assert(namespace_listed("wvkbd,omarchy-notification-center", "omarchy-notification-center"));
    assert(namespace_listed("wvkbd,omarchy-notification-center,omarchy-control-center", "omarchy-control-center"));
    assert(!namespace_listed("wvkbd,omarchy-notification-center", "omarchy-notification"));
    assert(!namespace_listed("wvkbd", "wvkbd2"));
    assert(!namespace_listed("", "wvkbd"));
    return 0;
}
'''
with tempfile.TemporaryDirectory() as work:
    c = Path(work) / 'listed.c'
    c.write_text(fixture)
    binary = Path(work) / 'listed'
    subprocess.run(['cc', '-Wall', '-Werror', '-o', str(binary), str(c)], check=True)
    subprocess.run([str(binary)], check=True)
print('swipe ignore list: ok')
