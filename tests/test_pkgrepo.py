"""tools/pkgrepo: versions read from the recipes, pin moves, and what a publish keeps."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
loader = SourceFileLoader('pkgrepo', str(ROOT / 'tools/pkgrepo'))
pkgrepo = module_from_spec(spec_from_loader('pkgrepo', loader))
loader.exec_module(pkgrepo)


def index(packages):
    """A pacman index as repo-add writes it."""
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w:gz') as archive:
        for name, version, filename in packages:
            desc = f'%FILENAME%\n{filename}\n\n%NAME%\n{name}\n\n%VERSION%\n{version}\n'.encode()
            member = tarfile.TarInfo(f'{name}-{version}/desc')
            member.size = len(desc)
            archive.addfile(member, io.BytesIO(desc))
    return data.getvalue()


class Recipes(unittest.TestCase):
    def test_every_recipe_agrees_with_its_pin(self):
        pkgrepo.check()

    def test_versions_carry_the_epoch_of_the_arch_packages_they_replace(self):
        for name in ('mesa', 'labwc', 'wlroots0.20'):
            self.assertTrue(pkgrepo.recipe(name)['version'].startswith('1:'), name)

    def test_architectures(self):
        self.assertEqual(pkgrepo.recipe('mesa')['arch'], ['aarch64'])
        self.assertEqual(pkgrepo.recipe('omacalc')['arch'], ['armv7h'])
        self.assertEqual(pkgrepo.recipe('labwc')['arch'], ['aarch64', 'armv7h'])

    def test_a_newer_commit_is_a_newer_version(self):
        source = {'version': '27.0.0-devel', 'revision': 232935, 'commit': '2c1aa767d8d8836739260177144716271e05f686'}
        self.assertEqual(pkgrepo.tracked_pkgver(source), '27.0.0.dev.r232935.2c1aa767d8d')


class Plan(unittest.TestCase):
    def plan(self, published, recorded=None):
        output = io.StringIO()
        with mock.patch.object(pkgrepo, 'published', lambda arch: published.get(arch, {})), \
                mock.patch.object(pkgrepo, 'state', lambda arch: recorded or {}), \
                mock.patch.dict('os.environ', {}, clear=False), \
                mock.patch('sys.stdout', output), mock.patch('sys.stderr', io.StringIO()):
            pkgrepo.os.environ.pop('GITHUB_OUTPUT', None)
            pkgrepo.plan(mock.Mock(package=None))
        return dict(line.split('=', 1) for line in output.getvalue().splitlines() if '=' in line)

    def everything(self):
        return {arch: {name: pkgrepo.recipe(name)['version'] for name in pkgrepo.names()
                       if arch in pkgrepo.recipe(name)['arch']} for arch in pkgrepo.ARCHES}

    def test_an_empty_repository_builds_each_package_for_its_architectures(self):
        result = self.plan({})
        builds = {(b['package'], b['arch']) for b in pkgrepo.json.loads(result['matrix'])['include']}
        self.assertIn(('mesa', 'aarch64'), builds)
        self.assertNotIn(('mesa', 'armv7h'), builds)
        self.assertIn(('omacalc', 'armv7h'), builds)
        self.assertNotIn(('omacalc', 'aarch64'), builds)

    def test_nothing_builds_when_every_version_is_published(self):
        result = self.plan(self.everything())
        self.assertEqual(result['any'], 'false')

    def test_only_the_package_whose_version_moved_builds(self):
        published = self.everything()
        published['aarch64']['mesa'] = '1:27.0.0.dev.r1.0000000-1'
        result = self.plan(published)
        self.assertEqual([(b['package'], b['arch']) for b in pkgrepo.json.loads(result['matrix'])['include']],
                         [('mesa', 'aarch64')])

    def test_a_changed_recipe_under_a_published_version_is_refused(self):
        with self.assertRaises(SystemExit) as stopped:
            self.plan(self.everything(), {'labwc': {'recipe': 'the digest of other patches'}})
        self.assertIn('Raise pkgrel', str(stopped.exception))


class Publish(unittest.TestCase):
    def test_the_files_of_the_new_and_the_previous_index_stay(self):
        with tempfile.TemporaryDirectory() as directory:
            new, old = Path(directory, 'new.db'), Path(directory, 'old.db')
            new.write_bytes(index([('labwc', '1:0.20.2-3', 'labwc-1.0.20.2-3-aarch64.pkg.tar.zst')]))
            old.write_bytes(index([('labwc', '1:0.20.2-2', 'labwc-1.0.20.2-2-aarch64.pkg.tar.zst')]))
            output = io.StringIO()
            with mock.patch('sys.stdout', output):
                pkgrepo.prune(mock.Mock(index=[str(new), str(old), str(Path(directory, 'none'))], assets=[
                    'orchard.db', 'built.json', 'labwc-1.0.20.2-1-aarch64.pkg.tar.zst',
                    'labwc-1.0.20.2-2-aarch64.pkg.tar.zst', 'labwc-1.0.20.2-3-aarch64.pkg.tar.zst']))
        self.assertEqual(output.getvalue().split(), ['labwc-1.0.20.2-1-aarch64.pkg.tar.zst'])


if __name__ == '__main__':
    unittest.main()
