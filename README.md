# Orchard packages

The package repository of the Orchard platform: the parts of a Linux system on
Apple A-chip devices that no stock distribution package provides, built once
and published for every Orchard distribution to install.

A distribution adds one repository to its package manager and gets Mesa with
the GPU driver, the patched compositor stack and the platform's small tools
from it, updated by the system's ordinary update. It builds none of them.

Packages are built **per base**, not per distribution. The base today is Arch
Linux ARM (pacman), for `aarch64` and `armv7h`. A second base gets a recipe
directory beside `pacman/` in each package (`apk/` for Alpine) and its own
published repository; nothing is built for one yet.

## Packages

| Package | aarch64 | armv7h | What |
|---|---|---|---|
| `mesa` | yes | - | Mesa from [OrchardLinux/mesa](https://github.com/OrchardLinux/mesa): OpenGL through Zink or in software, the Vulkan driver for the Apple PowerVR GPUs, and `gpu-probe`. Follows the fork's `main` automatically. Replaces Arch's `mesa`. |
| `wlroots0.20` | yes | yes | Arch's wlroots 0.20 with fast rotated software compositing and a GLES2 renderer that reads shared-memory buffers in place. Replaces Arch's `wlroots0.20`. |
| `labwc` | yes | yes | Labwc with the tablet patches: touch input fixes, bottom-edge swipe, session transitions, the overview. Replaces Arch's `labwc`. |
| `libva-v4l2-request` | yes | - | VA-API on orchard's hardware video decoders. |
| `omactivity` | yes | yes | The touch task manager, from [OrchardLinux/omactivity](https://github.com/OrchardLinux/omactivity). Follows its `main` automatically. |
| `folio-touch` | yes | yes | Files: Folio with touch mode, from the `touch-mode` branch of [OrchardLinux/folio](https://github.com/OrchardLinux/folio), followed automatically. Provides `folio` and conflicts with upstream Omarchy's. |
| `omafox` | yes | yes | Firefox follows the Omarchy theme. |
| `omacalc` | - | yes | Omarchy's calculator, which upstream Omarchy publishes for 64-bit only. |

Packages that replace an Arch package keep Arch's name and carry epoch 1. pacman
takes a package from the first repository that lists it, so with `[orchard]`
first, `pacman -S labwc` and `pacman -Syu` install ours, and a system that
still has Arch's build moves to ours on its next update.

## Using the repository

In `/etc/pacman.conf`, before every other repository (and before `[omarchy]`
on an Omarchy system):

```ini
[orchard]
SigLevel = Optional TrustAll
Server = https://github.com/OrchardLinux/packages/releases/download/repo-$arch

[omarchy]
Server = https://pkgs.omarchy.org/stable/$arch

[core]
Include = /etc/pacman.d/mirrorlist
# ... extra, alarm, aur as Arch Linux ARM ships them
```

Then `pacman -Syu`.

The repository is **not signed yet**, hence `SigLevel = Optional TrustAll`:
pacman trusts what GitHub serves over HTTPS. [docs/signing.md](docs/signing.md)
has the steps that remain and the entry to use afterwards.

`gpu-probe` is at `/usr/lib/orchard/gpu-probe`; `/usr/lib/omarchy-a/gpu-probe`
links to it for omarchy-a's login session.

## Layout

```
packages/NAME/source.json     the pinned source: URL, checksum, commit; "track" if it follows a branch
packages/NAME/patches/        changes to the source, for every base
packages/NAME/pacman/         the Arch recipe (PKGBUILD)
packages/NAME/tests/          tests of the patches; the recipe's check() runs them
ci/                           the build container and the build, publish and install-check scripts
tools/pkgrepo                 what to build, moving pins (see --help)
```

## How it builds

**Only what changed.** The published repository is the cache. Every push to
`main` compares each recipe's version (`epoch:pkgver-pkgrel`) with the
published index and builds the packages whose version is not there, each in
its own job, for each of its architectures. A push that changes no version
builds nothing and ends after the plan (about 15 seconds).

So a change to a package is: edit its patches or recipe, raise `pkgrel`
(`tools/pkgrepo rebuild NAME`), push. A changed recipe under a version that
is already published is refused with that advice rather than published
silently.

**Sources that move on their own.** A package with `"track"` in its
`source.json` follows that branch of its source repository. The workflow
*Follow sources* looks every 20 minutes, moves the pin to the branch's newest
commit (checksum, version and all), commits that to `main` and starts the
build, which then builds that one package. The version contains the commit's
number on the branch (`0.1.0.3.g3ffeac29dea`: the third commit), so a newer
commit is always a newer package. Development stays in the source
repository; it needs no packaging of its own. A source
repository can also announce a push and skip the wait:

```sh
gh api repos/OrchardLinux/packages/dispatches -f event_type=source-updated \
  -F 'client_payload[repo]=OrchardLinux/mesa' -F 'client_payload[sha]=COMMIT'
```

from a workflow there, which needs a token that may send this event; none
exists yet. A commit is only taken if the tracked branch contains it and it
continues the pinned one. A branch marked `"rebased"` (Folio's touch mode,
which is rebased onto upstream) is also followed across a rebase, as long as
its commits still count upwards.

**Arch moves underneath.** Mesa runs on the LLVM it was built with, and
pacman refuses an update that would break that. Every six hours *Follow
sources* asks pacman whether each published package still installs beside
today's Arch packages; one that does not gets its `pkgrel` raised and is built
again. Until that build is published (about ten minutes), `pacman -Syu` on a
tablet stops with a dependency error and changes nothing.

**Publishing.** One job writes the index, one run at a time. Packages are
uploaded first and the index last; the package files of the previous index
are kept, older ones removed. Then a fresh Arch Linux ARM container per
architecture installs Arch's `labwc`, `wlroots0.20` and `mesa`, adds
`[orchard]`, and has to end up with every package of the repository installed
from it and a clean `pacman -Dk`.

**Builders.** GitHub's free arm64 runners. `aarch64` builds in a pinned Arch
Linux ARM image; `armv7h` in Arch Linux ARM's official ARMv7 root, run by the
runner's 64-bit kernel in 32-bit mode, without emulation. Each build first
updates its container fully, installs what the recipe names, and runs
`makepkg` as an unprivileged user. Mesa keeps a compiler cache between builds.

Locally, on an arm64 Linux host with Docker:

```sh
ci/build-package labwc aarch64 1:0.20.2-1     # package in out/
python3 -m unittest discover -s tests
```

## License

GPL-2.0-or-later for this repository's own files ([LICENSE](LICENSE)). The
packaged software keeps its own licenses; [NOTICE](NOTICE) lists them and
where each recipe and patch came from.
