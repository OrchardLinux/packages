"""The Labwc patches' own arithmetic, compiled from the patches as they are.

The overview's grid and gestures and the bottom-edge swipe are header-only
code that the patches add; their tests (packages/labwc/tests) run here on
every push, without building Labwc. The recipe's check() runs them again on
the patched source, with the touch configuration test, which needs wlroots.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

LABWC = Path(__file__).resolve().parents[1] / 'packages/labwc'


def added_file(patch, name):
    """The contents of a file the patch creates."""
    lines = (LABWC / 'patches' / patch).read_text().splitlines()
    start = lines.index(f'+++ b/{name}') + 2
    body = []
    for line in lines[start:]:
        if line.startswith(('diff --git', '--- ')):
            break
        body.append(line[1:])
    return '\n'.join(body) + '\n'


@unittest.skipUnless(shutil.which('cc'), 'needs a C compiler')
class PatchMath(unittest.TestCase):
    def run_test(self, patch, header, test):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            target = work / header
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(added_file(patch, 'include/' + header))
            subprocess.run(['cc', '-Wall', '-Werror', '-I', str(work), '-o', str(work / 'test'),
                            str(LABWC / 'tests' / test), '-lm'], check=True)
            result = subprocess.run([str(work / 'test')], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_overview_math_passes(self):
        self.run_test('0004-overview.patch', 'overview-math.h', 'test-overview.c')

    def test_bottom_swipe_passes(self):
        self.run_test('0002-bottom-edge-swipe.patch', 'input/bottom-swipe.h', 'test-bottom-swipe.c')


class Overview(unittest.TestCase):
    def test_choosing_a_window_moves_it_only_from_the_overview_choice(self):
        source = added_file('0004-overview.patch', 'src/overview.c')
        # Brought on screen in one place only: when a choice leaves the overview.
        self.assertEqual(source.count('bring_on_screen('), 2)
        finish = source[source.index('\nfinish(struct view *chosen)'):]
        self.assertIn('bring_on_screen(chosen);', finish[:finish.index('\n}\n')])


if __name__ == '__main__':
    unittest.main()
