# Orchard packages

The package repository of the Orchard platform: the parts of a Linux system on
Apple A-chip devices that no stock distribution package provides, built once
and published for every Orchard distribution to install.

A distribution adds one repository to its package manager and gets Mesa with
the GPU driver, the patched compositor stack and the platform's small tools
from it, updated by the system's ordinary update. It builds none of them.

Packages are built **per base**, not per distribution. A package's directory
holds one recipe per base it is built for: `arch/` for Arch Linux ARM
(pacman: `aarch64`, `armv7h`; omarchy-a) and `alpine/` for Alpine (apk:
`aarch64`, `armv7`; minimal-linux). Each base has its own published
repository. Most packages are Arch-only today; orchard's kernel packages are
built for both.

## Packages

| Package | aarch64 | armv7h | What |
|---|---|---|---|
| `mesa` | yes | - | Mesa from [OrchardLinux/mesa](https://github.com/OrchardLinux/mesa): OpenGL through Zink or in software, the Vulkan driver for the Apple PowerVR GPUs, and `gpu-probe`. Pinned to a commit of the fork's `main` until the fork tags its first release; then it follows releases. Replaces Arch's `mesa`. |
| `wlroots0.20` | yes | yes | Arch's wlroots 0.20 with fast rotated software compositing and a GLES2 renderer that reads shared-memory buffers in place. Replaces Arch's `wlroots0.20`. |
| `labwc` | yes | yes | Labwc with the tablet patches: touch input fixes, bottom-edge swipe, session transitions, the overview. Replaces Arch's `labwc`. |
| `qt6-base` | yes | yes | Arch Linux ARM's qt6-base 6.12.0 with Qt's text-input focus fix (QTBUG-146211) from its 6.12 branch: the on-screen keyboard closes when focus leaves a text field in a Qt app. Replaces Arch's `qt6-base` until Arch ships a Qt with the fix. |
| `libva-v4l2-request` | yes | - | VA-API on orchard's hardware video decoders. |
| `omactivity` | yes | yes | The touch task manager, from [OrchardLinux/omactivity](https://github.com/OrchardLinux/omactivity). Follows its releases (the published pin is newer than v0.1.0; its next release moves it). |
| `folio-touch` | yes | yes | Files: Folio with touch mode, from the `touch-mode` branch of [OrchardLinux/folio](https://github.com/OrchardLinux/folio), pinned to a commit until the fork tags a release newer than 0.4.0 (`v0.4.1`; its tag `a0.2.0-1` is no version tag). Provides `folio` and conflicts with upstream Omarchy's. |
| `omafox` | yes | yes | Firefox follows the Omarchy theme. |
| `omacalc` | - | yes | Omarchy's calculator, which upstream Omarchy publishes for 64-bit only. |
| `omarchy-a` | yes | yes | Omarchy A's own files: the touch desktop, its configuration and system defaults, from [OrchardLinux/omarchy-a](https://github.com/OrchardLinux/omarchy-a), built with its Makefile. Follows its releases; nothing is built until its first release that builds this way. Conflicts with upstream Omarchy's `omarchy`. |
| `linux-orchard-apple-16k`, `linux-orchard-apple-4k` | yes | - | orchard's kernel, modules, the boards' device trees, initrd and hardware defaults for A9 and later (16 KiB pages) or A7 to A8X: an orchard release's platform layer, installed unchanged by a plain PKGBUILD and APKBUILD; orchard's installer installs this package. Its pacman hooks (apk: scripts and trigger) run orchard's `boot-entries`, which keeps the system's boot entries current and the previous kernel as a fallback. The two conflict. |
| `linux-orchard-apple-armv7` | - | yes | The same for the 32-bit boards (Alpine: `armv7`). |

Packages that replace an Arch package keep Arch's name and carry epoch 1. pacman
takes a package from the first repository that lists it, so with `[orchard]`
first, `pacman -S labwc` and `pacman -Syu` install ours, and a system that
still has Arch's build moves to ours on its next update.
`qt6-base` is the exception: it carries a fix until Arch's Qt has it, so it
ranks above Arch's build by its pkgrel (`6.12.0-5.1`) instead, and tablets go
back to Arch's next build by the ordinary update once it is dropped.

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

On Alpine (minimal-linux), unsigned for now too, so apk needs `--allow-untrusted`:

```sh
echo https://github.com/OrchardLinux/packages/releases/download >> /etc/apk/repositories
apk update --allow-untrusted
```

apk asks for `SERVER/ARCH/APKINDEX.tar.gz`, so each architecture's apk
repository is the release named after it (`aarch64`, `armv7`).

A test tablet installed before kernel packages takes its kernel package once with
`pacman -S --overwrite '/usr/*' linux-orchard-PLATFORM` (Alpine: `apk add --allow-untrusted linux-orchard-PLATFORM`).

## Layout

```
packages/NAME/source.json     the pinned source: URL, checksum, commit; "track" if it follows a branch
packages/NAME/patches/        changes to the source, for every base
packages/NAME/arch/           the Arch recipe (PKGBUILD) and its files
packages/NAME/alpine/         the Alpine recipe (APKBUILD) and its scripts
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

**Releases only.** A package publishes when its source tags a release, never
for a push to the source or a nightly. A package with `"track"` in its
`source.json` follows the releases of its source repository (`"track"` names the
branch its first pin was taken from). The workflow *Follow sources* looks every
20 minutes; when the newest release has a version tag (`v1.2.3`) newer than the
published package, it moves the pin to that tag (commit, checksum, version),
commits that to `main` and starts the build, which then builds that one
package. A source repository can also announce a release and skip the wait:

```sh
gh api repos/OrchardLinux/packages/dispatches -f event_type=source-updated \
  -F 'client_payload[repo]=OrchardLinux/mesa' -F 'client_payload[tag]=v27.0.0'
```

from a workflow there, which needs a token that may send this event; none
exists yet. Still pinned to a commit until their first release: Mesa
(OrchardLinux/mesa has no release) and folio-touch (OrchardLinux/folio needs a
version tag newer than 0.4.0).

**orchard's kernels.** `linux-orchard-PLATFORM` has an Arch and an Alpine
recipe that fetch an orchard release's `platform-PLATFORM.tar.gz` (pinned by
checksum) and install it unchanged, with the pacman hooks, or the apk scripts
and trigger, that run the layer's `/usr/lib/orchard/boot-entries`. Plain
makepkg and abuild build them; nothing is compiled. Their version is orchard's
(`0.4.0-1`, Alpine `0.4.0-r0`). A release of orchard is a new pkgver and
checksum in both recipes, which one command writes from the release's assets:

```sh
tools/pkgrepo orchard-release v0.4.0
```

They are pinned to orchard 0.3.1 now, whose layer predates `boot-entries`; the
hooks and trigger skip it where it is missing. How the packages write boot entries is orchard's
[boot contract](https://github.com/OrchardLinux/orchard/blob/main/docs/boot-contract.md#kernel-packages).

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
from it and a clean `pacman -Dk`. A fresh Alpine container per architecture
does the same with the apk repository. The kernel packages, which conflict,
go one at a time, and on those containers, which the Orchard installer did not
set up, their hooks have to leave `/boot` and `/usr/lib/modules` alone. apk
indexes are signed with `ORCHARD_APK_KEY` once it exists, until then with a
key made for each publish.

**Builders.** GitHub's free arm64 runners. Alpine packages build with abuild in
Alpine's official image (the release minimal-linux uses), `armv7` in its
32-bit mode. `aarch64` builds in a pinned Arch
Linux ARM image; `armv7h` in Arch Linux ARM's official ARMv7 root, run by the
runner's 64-bit kernel in 32-bit mode, without emulation. Each build first
updates its container fully, installs what the recipe names, and runs
`makepkg` as an unprivileged user. Mesa keeps a compiler cache between builds.

Locally, on an arm64 Linux host with Docker, or a Mac with Podman's VM:

```sh
ci/build-package arch labwc aarch64 1:0.20.2-1                    # package in out/
ci/build-package alpine linux-orchard-apple-16k aarch64 0.3.1-r0
python3 -m unittest discover -s tests
```

To try a change in an image before it is published, build the distribution with
this checkout: `orchard build --packages ../packages` in omarchy-a (or `packages`
in its `orchard.local.toml`). It asks `tools/pkgrepo local` which of the image's
packages have a recipe here that the published repository lacks, and builds those
with `ci/build-package` (`OUT`: where the package goes, `LOCAL_REPO`: the ones built
before it, which it builds against).

## License

GPL-2.0-or-later for this repository's own files ([LICENSE](LICENSE)). The
packaged software keeps its own licenses; [NOTICE](NOTICE) lists them and
where each recipe and patch came from.
