#!/usr/bin/env python3
"""The boot splash stays until the shell has drawn (0012).

Run by check(): test-startup-picture.py SOURCE. At boot no compositor came
before, so there is no handover frame; startupPicture names the boot loader's
splash, which then stands in for the black cover. A session that starts
locked takes the lock before its lock screen has drawn: the splash must lie
over the lock (whose black background would hide it), take no input, and
not occlude the lock surface. A handover frame keeps its place below.
"""
from pathlib import Path
import sys

source = Path(sys.argv[1])
rcxml = (source / 'src/config/rcxml.c').read_text()
assert '"startupPicture.core"' in rcxml, 'option parsed'
output = (source / 'src/output.c').read_text()

create = output[output.index('\nstartup_cover_create('):]
create = create[:create.index('\n}\n')]
assert create.index('handover_load(output)') < create.index('startup_picture_load(output)'), \
    'a handover frame comes first'
assert 'point_accepts_input = rotation_accepts_input' in create, 'no input on the picture'

tick = output[output.index('\nstartup_tick('):]
tick = tick[:tick.index('\n}\n')]
start = tick.index('if (output->startup_frame_is_picture) {')
middle = tick.index('} else {', start)
picture = tick[start:middle]
assert 'place_above(cover, &output->session_lock_tree->node)' in picture, 'over the lock'
assert 'set_opacity(output->startup_frame, 0.999f)' in picture, 'lock surface keeps drawing'
other = tick[middle:tick.index('\n\t}\n', middle)]
assert 'place_below(cover, &output->session_lock_tree->node)' in other, \
    'handover frame below the lock'

load = output[output.index('\nstartup_picture_load('):]
load = load[:load.index('\n}\n')]
assert 'wlr_output_preferred_mode' in load and '0xff000000' in load, 'opaque, native mode'
print('startup picture: ok')
