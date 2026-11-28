#!/usr/bin/env python3
"""Compile the bottom swipe's way into the overview against stubs (0013).

Run by check(): test-bottom-swipe-overview.py SOURCE. Up to 45 % of the
screen the overview follows the finger one to one; past it, with a far
command and nothing following the finger, the overview goes back three
times as fast; with a follower or without a far command it holds.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

source = Path(sys.argv[1])
touch = (source / 'src/input/touch.c').read_text()
defines = '\n'.join(re.findall(r'^#define EDGE_\w+ .*$', touch, re.M))
assert 'EDGE_RECEDE' in defines and 'EDGE_FAR' in defines, 'EDGE_ defines'
match = re.search(r'static double\nedge_overview_travel\(double travel\)\n\{', touch)
assert match, 'edge_overview_travel'
end = touch.index('{', match.start()) + 1
depth = 1
while depth:
    if touch[end] == '{': depth += 1
    if touch[end] == '}': depth -= 1
    end += 1
fixture = '#include <assert.h>\n#include <math.h>\n#include <stddef.h>\n' + defines + r'''
static struct { double height; char *far_command; int fd; } edge;
''' + touch[match.start():end] + r'''
int main(void) {
    edge.height = 1000;
    edge.far_command = "launcher";
    edge.fd = -1;
#define NEAR(a, b) (fabs((a) - (b)) < 1e-6)
    /* The overview's own gestures open it over 0.3 of the height (300). */
    assert(NEAR(edge_overview_travel(90), 150));
    assert(NEAR(edge_overview_travel(180), 300));  /* open at 0.18 */
    assert(NEAR(edge_overview_travel(220), 220 * 0.3 / 0.18));
    assert(NEAR(edge_overview_travel(250), 130 * 0.3 / 0.18));   /* going back */
    assert(edge_overview_travel(400) == 0);     /* gone */
    assert(EDGE_OPEN < EDGE_RECEDE && EDGE_RECEDE < EDGE_FAR && EDGE_FAR < EDGE_GONE);
    edge.fd = 3;
    assert(edge_overview_travel(400) >= 300);   /* the launcher follows: holds still */
    edge.fd = -1;
    edge.far_command = NULL;
    assert(edge_overview_travel(400) >= 300);   /* nothing beyond: keeps following */
    return 0;
}
'''
with tempfile.TemporaryDirectory() as work:
    c = Path(work) / 'edge.c'
    c.write_text(fixture)
    binary = Path(work) / 'edge'
    subprocess.run(['cc', '-Wall', '-Werror', '-o', str(binary), str(c), '-lm'], check=True)
    subprocess.run([str(binary)], check=True)
config = (source / 'src/config/rcxml.c').read_text()
assert '"bottomSwipeOverview"' in config and '"bottomSwipeFarCommand"' in config
print('bottom swipe overview: ok')
