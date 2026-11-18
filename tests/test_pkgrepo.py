"""tools/pkgrepo: versions read from the recipes, pin moves, and what a publish keeps."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import gzip
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import shutil
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

    def test_the_kernel_packages_exist_for_both_bases(self):
        for platform, arch, alpine in (('apple-16k', 'aarch64', 'aarch64'), ('apple-4k', 'aarch64', 'aarch64'),
                                       ('apple-armv7', 'armv7h', 'armv7')):
            name = 'linux-orchard-' + platform
            self.assertEqual(pkgrepo.bases(name), ['arch', 'alpine'])
            self.assertEqual(pkgrepo.recipe(name)['arch'], [arch])
            self.assertEqual(pkgrepo.recipe(name, 'alpine')['arch'], [alpine])
            version = pkgrepo.pin(name)['orchard']
            self.assertEqual(pkgrepo.recipe(name)['version'], version + '-1')
            self.assertEqual(pkgrepo.recipe(name, 'alpine')['version'], version + '-r0')

    def test_every_kernel_package_runs_the_same_hooks_and_trigger(self):
        first = ROOT / 'packages/linux-orchard-apple-16k'
        for other in ('apple-4k', 'apple-armv7'):
            directory = ROOT / 'packages' / ('linux-orchard-' + other)
            for hook in ('05-orchard-boot-entries-save.hook', '95-orchard-boot-entries.hook'):
                self.assertEqual((directory / 'arch' / hook).read_text(), (first / 'arch' / hook).read_text())
            for script in ('trigger', 'pre-upgrade', 'pre-deinstall'):
                self.assertEqual((directory / f'alpine/linux-orchard-{other}.{script}').read_text(),
                                 (first / f'alpine/linux-orchard-apple-16k.{script}').read_text())
        self.assertIn('exec /usr/lib/orchard/boot-entries sync', (first / 'arch/95-orchard-boot-entries.hook').read_text())
        self.assertIn('/usr/lib/orchard/boot-entries sync', (first / 'alpine/linux-orchard-apple-16k.trigger').read_text())

    def test_versions_order_as_pacman_orders_them(self):
        self.assertGreater(pkgrepo.vercmp('0.1.1', '0.1.0.3.g3ffeac29dea'), 0)
        self.assertLess(pkgrepo.vercmp('0.1.0', '0.1.0.3.g3ffeac29dea'), 0)
        self.assertGreater(pkgrepo.vercmp('27.0.0', '27.0.0.dev.232935.g2c1aa767d8d'), 0)
        self.assertEqual(pkgrepo.vercmp('1.2', '1.2'), 0)

    def test_omarchy_a_follows_its_releases(self):
        self.assertEqual(pkgrepo.bases('omarchy-a'), ['arch'])
        self.assertEqual(pkgrepo.recipe('omarchy-a')['arch'], ['aarch64', 'armv7h'])
        self.assertEqual(pkgrepo.pin('omarchy-a')['track'], 'releases')
        text = pkgrepo.recipe('omarchy-a')['text']
        # omarchy-a's image build replaces _commit, pkgver and the first source and checksum.
        for key in ('pkgver', '_commit', 'source', 'sha256sums'):
            self.assertEqual(len(pkgrepo.re.findall(rf'^{key}=.*$', text, pkgrepo.re.M)), 1, key)
        self.assertRegex(text, r'(?m)^source=\("omarchy-a-\$\{_commit\}\.tar\.gz::\$\{url\}/archive/\$\{_commit\}\.tar\.gz"$')
        self.assertRegex(text, r"(?m)^sha256sums=\('[^']+'$")
        # makepkg alone: make, no omarchy-a tooling.
        self.assertIn('make -C "omarchy-a-${_commit}" install', text)
        self.assertNotIn('release.package', text)
        self.assertNotIn('python3', text.split('build()')[1])

    def test_omarchy_a_waits_for_its_first_release_then_bump_pins_it(self):
        commit = 'c' * 40
        archive = b'omarchy-a v0.4.0'
        digest = hashlib.sha256(archive).hexdigest()
        replies = {'repos/OrchardLinux/omarchy-a/releases/latest': {'tag_name': 'v0.4.0'},
                   'repos/OrchardLinux/omarchy-a/commits/v0.4.0': {'sha': commit}}
        with tempfile.TemporaryDirectory() as directory:
            packages = Path(directory) / 'packages'
            shutil.copytree(ROOT / 'packages/omarchy-a', packages / 'omarchy-a')
            # Before its first release: the pin names the repository and the tracking only.
            (packages / 'omarchy-a/source.json').write_text(pkgrepo.json.dumps(
                {'repository': 'OrchardLinux/omarchy-a', 'track': 'releases'}))
            with mock.patch.object(pkgrepo, 'PACKAGES', packages), \
                    mock.patch.object(pkgrepo, 'api', lambda path: replies[path]), \
                    mock.patch.object(pkgrepo, 'fetch', return_value=archive) as fetch, \
                    mock.patch('sys.stdout', io.StringIO()):
                self.assertTrue(pkgrepo.waiting('omarchy-a'))
                self.assertTrue(pkgrepo.bump_one('omarchy-a'))
                self.assertEqual(pkgrepo.recipe('omarchy-a')['version'], '0.4.0-1')
                self.assertFalse(pkgrepo.waiting('omarchy-a'))
                pkgrepo.check()
            fetch.assert_called_once_with(f'https://github.com/OrchardLinux/omarchy-a/archive/{commit}.tar.gz')
            text = (packages / 'omarchy-a/arch/PKGBUILD').read_text()
            self.assertIn(f"_commit={commit}\n", text)
            self.assertIn(f"sha256sums=('{digest}'\n", text)
            # The other sources keep their checksums.
            self.assertIn("'330e7d41e2ccf3f984af701c0d055d919cff66710dfe05ce9d77e4ae6e1adc16'", text)

    def test_a_newer_commit_is_a_newer_version(self):
        source = {'version': '27.0.0-devel', 'revision': 232935, 'commit': '2c1aa767d8d8836739260177144716271e05f686'}
        self.assertEqual(pkgrepo.tracked_pkgver(source), '27.0.0.dev.232935.g2c1aa767d8d')


class Plan(unittest.TestCase):
    def plan(self, published, recorded=None):
        output = io.StringIO()
        with mock.patch.object(pkgrepo, 'published', lambda arch, base='arch': published.get((base, arch), {})), \
                mock.patch.object(pkgrepo, 'state', lambda arch, base='arch': recorded or {}), \
                mock.patch.dict('os.environ', {}, clear=False), \
                mock.patch('sys.stdout', output), mock.patch('sys.stderr', io.StringIO()):
            pkgrepo.os.environ.pop('GITHUB_OUTPUT', None)
            pkgrepo.plan(mock.Mock(package=None))
        return dict(line.split('=', 1) for line in output.getvalue().splitlines() if '=' in line)

    def everything(self):
        return {(base, arch): {name: pkgrepo.recipe(name, base)['version'] for name in pkgrepo.names(base)
                               if arch in pkgrepo.recipe(name, base)['arch']}
                for base, row in pkgrepo.BASES.items() for arch in row['arches']}

    def test_an_empty_repository_builds_each_package_for_its_architectures(self):
        result = self.plan({})
        builds = {(b['package'], b['base'], b['arch']) for b in pkgrepo.json.loads(result['matrix'])['include']}
        self.assertIn(('mesa', 'arch', 'aarch64'), builds)
        self.assertNotIn(('mesa', 'arch', 'armv7h'), builds)
        self.assertIn(('omacalc', 'arch', 'armv7h'), builds)
        self.assertNotIn(('omacalc', 'arch', 'aarch64'), builds)
        self.assertNotIn(('mesa', 'alpine', 'aarch64'), builds)
        # orchard's kernel packages wait for an orchard release with kernel packages.
        self.assertIn(('linux-orchard-apple-armv7', 'alpine', 'armv7'), builds)
        self.assertIn({'base': 'alpine', 'arch': 'armv7'}, pkgrepo.json.loads(result['targets']))

    def test_a_package_waiting_for_its_first_release_is_not_built(self):
        with mock.patch.object(pkgrepo, 'waiting', lambda name: name == 'omarchy-a'):
            builds = {b['package'] for b in pkgrepo.json.loads(self.plan({})['matrix'])['include']}
        self.assertNotIn('omarchy-a', builds)
        with mock.patch.object(pkgrepo, 'waiting', lambda name: False):
            builds = {(b['package'], b['arch']) for b in pkgrepo.json.loads(self.plan({})['matrix'])['include']}
        self.assertLessEqual({('omarchy-a', 'aarch64'), ('omarchy-a', 'armv7h')}, builds)

    def test_nothing_builds_when_every_version_is_published(self):
        result = self.plan(self.everything())
        self.assertEqual(result['any'], 'false')

    def test_only_the_package_whose_version_moved_builds(self):
        published = self.everything()
        published[('arch', 'aarch64')]['mesa'] = '1:27.0.0.dev.r1.0000000-1'
        result = self.plan(published)
        self.assertEqual([(b['package'], b['base'], b['arch']) for b in pkgrepo.json.loads(result['matrix'])['include']],
                         [('mesa', 'arch', 'aarch64')])

    def test_a_changed_recipe_under_a_published_version_is_refused(self):
        with self.assertRaises(SystemExit) as stopped:
            self.plan(self.everything(), {'labwc': {'recipe': 'the digest of other patches'}})
        self.assertIn('Raise pkgrel', str(stopped.exception))


def apkindex(packages, signed=True):
    """An apk index as abuild-sign leaves it: the signature's tar, then the index's, gzipped apart."""
    def tar(members, end):
        data = io.BytesIO()
        archive = tarfile.open(fileobj=data, mode='w')
        for name, content in members:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        if end:
            archive.close()
            return data.getvalue()
        archive.fileobj.write(b'')  # no end-of-archive blocks: the next tar follows
        return data.getvalue()
    text = ''.join(f'C:Q1x=\nP:{name}\nV:{version}\nA:aarch64\n\n' for name, version in packages).encode()
    parts = [gzip.compress(tar([('APKINDEX', text), ('DESCRIPTION', b'Orchard packages')], True))]
    if signed:
        parts.insert(0, gzip.compress(tar([('.SIGN.RSA.orchard.rsa.pub', b'signature')], False)))
    return b''.join(parts)


class Local(unittest.TestCase):
    """pkgrepo local: what a distribution's local image build compiles, and in which order."""
    NAMES = ['labwc', 'wlroots0.20', 'mesa', 'omafox']

    def run_local(self, published, recorded=None):
        output = io.StringIO()
        with mock.patch.object(pkgrepo, 'published', lambda arch, base='arch': published), \
                mock.patch.object(pkgrepo, 'state', lambda arch, base='arch': recorded or {}), \
                mock.patch('sys.stdout', output):
            pkgrepo.local(SimpleNamespace(arch='aarch64', names=self.NAMES))
        return {row['name']: row for row in json.loads(output.getvalue())['packages']}, \
            [row['name'] for row in json.loads(output.getvalue())['packages']]

    def current(self):
        return {name: pkgrepo.recipe(name)['version'] for name in self.NAMES}

    def test_a_package_builds_after_what_it_needs_of_the_others(self):
        rows, order = self.run_local({})
        # labwc links wlroots; wlroots needs an opengl-driver, which Mesa provides.
        self.assertLess(order.index('mesa'), order.index('wlroots0.20'))
        self.assertLess(order.index('wlroots0.20'), order.index('labwc'))
        self.assertEqual(rows['labwc']['needs'], ['wlroots0.20'])
        self.assertEqual(rows['omafox']['needs'], [])
        self.assertTrue(all(row['build'] for row in rows.values()))

    def test_published_packages_of_the_same_recipe_are_not_built(self):
        recorded = {name: {'recipe': pkgrepo.recipe_digest(name)} for name in self.NAMES}
        rows, _ = self.run_local(self.current(), recorded)
        self.assertFalse(any(row['build'] for row in rows.values()))

    def test_a_recipe_ahead_of_the_published_version_builds(self):
        published = {**self.current(), 'labwc': '1:0.20.2-1'}
        rows, _ = self.run_local(published)
        self.assertEqual([name for name, row in rows.items() if row['build']], ['labwc'])
        self.assertEqual(rows['labwc']['published'], '1:0.20.2-1')

    def test_a_changed_recipe_under_the_published_version_builds(self):
        recorded = {name: {'recipe': pkgrepo.recipe_digest(name)} for name in self.NAMES}
        recorded['wlroots0.20'] = {'recipe': 'an older recipe'}
        rows, _ = self.run_local(self.current(), recorded)
        self.assertEqual([name for name, row in rows.items() if row['build']], ['wlroots0.20'])


class Orchard(unittest.TestCase):
    """A release of orchard is one command: every kernel package's version and checksums."""
    def test_the_release_moves_both_bases_of_every_kernel_package(self):
        layers = {f'platform-{p}.tar.gz': f'layer {p}'.encode() for p in ('apple-16k', 'apple-4k', 'apple-armv7')}
        sums = ''.join(f'{hashlib.sha256(data).hexdigest()}  ./{name}\n' for name, data in layers.items()).encode()
        base = 'https://github.com/OrchardLinux/orchard/releases/download/v9.1.0/'

        def fetch(url, binary=True, **_):
            data = sums if url == base + 'SHA256SUMS' else layers[url.removeprefix(base)]
            return data if binary else data.decode()
        with tempfile.TemporaryDirectory() as directory:
            packages = Path(directory)
            for name in ('linux-orchard-apple-16k', 'linux-orchard-apple-4k', 'linux-orchard-apple-armv7', 'mesa'):
                shutil.copytree(ROOT / 'packages' / name, packages / name)
            with mock.patch.object(pkgrepo, 'PACKAGES', packages), mock.patch.object(pkgrepo, 'fetch', fetch), \
                    mock.patch('sys.stdout', io.StringIO()):
                pkgrepo.orchard_release(mock.Mock(version='v9.1.0'))
                self.assertEqual(pkgrepo.recipe('linux-orchard-apple-4k')['version'], '9.1.0-1')
                self.assertEqual(pkgrepo.recipe('linux-orchard-apple-4k', 'alpine')['version'], '9.1.0-r0')
                pin = pkgrepo.pin('linux-orchard-apple-armv7')
                self.assertEqual(pin['sha512'], hashlib.sha512(b'layer apple-armv7').hexdigest())
                self.assertIn(pin['sha512'], pkgrepo.recipe('linux-orchard-apple-armv7', 'alpine')['text'])
                self.assertIn(pin['sha256'], pkgrepo.recipe('linux-orchard-apple-armv7')['text'])
                self.assertEqual(pkgrepo.recipe('mesa')['version'], pkgrepo.recipe('mesa')['version'])


class Releases(unittest.TestCase):
    """Packages publish for releases of their sources: bump follows release tags only."""
    def answers(self, releases):
        def api(path):
            if '/releases/' in path:
                if not releases:
                    raise pkgrepo.HTTPError(path, 404, 'none', None, None)
                return {'tag_name': releases[0]}
            return {'sha': 'c' * 40}
        return mock.patch.object(pkgrepo, 'api', api)

    def test_a_repository_without_releases_keeps_its_pin(self):
        with self.answers([]), mock.patch('sys.stdout', io.StringIO()) as output:
            self.assertFalse(pkgrepo.bump_one('mesa'))
        self.assertIn('has no release', output.getvalue())

    def test_only_a_newer_version_tag_moves_a_pin(self):
        for tag in ('a0.2.0-1', 'v0.1.0'):
            with self.answers([tag]), mock.patch('sys.stdout', io.StringIO()):
                self.assertFalse(pkgrepo.bump_one('omactivity'), tag)

    def test_a_new_release_moves_the_pin_to_its_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            packages = Path(directory)
            shutil.copytree(ROOT / 'packages/omactivity', packages / 'omactivity')
            with mock.patch.object(pkgrepo, 'PACKAGES', packages), self.answers(['v0.1.1']), \
                    mock.patch.object(pkgrepo, 'fetch', return_value=b'archive'), mock.patch('sys.stdout', io.StringIO()):
                self.assertTrue(pkgrepo.bump_one('omactivity'))
                pkgrepo.check()
                pin = pkgrepo.pin('omactivity')
                self.assertEqual((pin['tag'], pin['track'], pin['commit']), ('v0.1.1', 'releases', 'c' * 40))
                self.assertEqual(pkgrepo.recipe('omactivity')['version'], '0.1.1-1')


class Publish(unittest.TestCase):
    def test_an_apk_index_names_its_files_signed_or_not(self):
        for signed in (True, False):
            self.assertEqual(pkgrepo.entries(apkindex([('linux-orchard-apple-16k', '0.4.0-r0')], signed), 'alpine'),
                             {'linux-orchard-apple-16k': ('0.4.0-r0', 'linux-orchard-apple-16k-0.4.0-r0.apk')})

    def test_apk_files_of_neither_index_go(self):
        with tempfile.TemporaryDirectory() as directory:
            new, old = Path(directory, 'new'), Path(directory, 'old')
            new.write_bytes(apkindex([('linux-orchard-apple-16k', '0.5.0-r0')]))
            old.write_bytes(apkindex([('linux-orchard-apple-16k', '0.4.0-r0')]))
            output = io.StringIO()
            with mock.patch('sys.stdout', output):
                pkgrepo.prune(mock.Mock(base='alpine', index=[str(new), str(old)], assets=[
                    'APKINDEX.tar.gz', 'built.json', 'linux-orchard-apple-16k-0.3.0-r0.apk',
                    'linux-orchard-apple-16k-0.4.0-r0.apk', 'linux-orchard-apple-16k-0.5.0-r0.apk']))
        self.assertEqual(output.getvalue().split(), ['linux-orchard-apple-16k-0.3.0-r0.apk'])

    def test_the_files_of_the_new_and_the_previous_index_stay(self):
        with tempfile.TemporaryDirectory() as directory:
            new, old = Path(directory, 'new.db'), Path(directory, 'old.db')
            new.write_bytes(index([('labwc', '1:0.20.2-3', 'labwc-1.0.20.2-3-aarch64.pkg.tar.zst')]))
            old.write_bytes(index([('labwc', '1:0.20.2-2', 'labwc-1.0.20.2-2-aarch64.pkg.tar.zst')]))
            output = io.StringIO()
            with mock.patch('sys.stdout', output):
                pkgrepo.prune(mock.Mock(base='arch', index=[str(new), str(old), str(Path(directory, 'none'))], assets=[
                    'orchard.db', 'built.json', 'labwc-1.0.20.2-1-aarch64.pkg.tar.zst',
                    'labwc-1.0.20.2-2-aarch64.pkg.tar.zst', 'labwc-1.0.20.2-3-aarch64.pkg.tar.zst']))
        self.assertEqual(output.getvalue().split(), ['labwc-1.0.20.2-1-aarch64.pkg.tar.zst'])


if __name__ == '__main__':
    unittest.main()
