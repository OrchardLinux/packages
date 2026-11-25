# Changelog

Notable changes to the packages: what someone using a tablet would notice
after `pacman -Syu` (or `apk upgrade`). Packages follow their sources'
releases; a release of a source itself (Omarchy A, orchard, Mesa) is in its
own changelog, and only what this repository changes is here.

Add an entry under **Unreleased** in the same pull request as the change,
under the package and the version it builds (`epoch:pkgver-pkgrel`). A push
to `main` publishes every changed version at once, so when merging, rename
**Unreleased** to that day's date (`## 2026-11-20`).

## Unreleased

### labwc 1:0.20.2-10

- At boot the splash waits up to 60 seconds for the PIN screen instead of 20.
  After a slow start it no longer goes black before the PIN screen appears.

## 2026-11-24

### omarchy-a 0.3.4-2

- The "Volume was not properly unmounted ... Please run fsck" message at
  boot goes away: the system now checks the boot partition at start and
  clears what an unclean shutdown left behind, from the next start after
  the update on.

## 2026-11-22

### labwc 1:0.20.2-8

- Pressing Home on the lock screen no longer leaves it held down: the lock
  screen gets the release too, so it stops repeating the key and keeping
  the screen lit.

## 2026-11-21

### labwc 1:0.20.2-7

- In the overview, a long press on a window (a right click, the Menu key)
  offers Minimize, Maximize or Restore, and Close, the buttons of a title
  bar for a window that has none. A tap beside the menu puts it away and
  leaves the overview open.

## 2026-11-20

### labwc 1:0.20.2-6

- A swipe up from the bottom edge reaches the notification center and the
  control center as their own drag, which follows the finger, instead of
  closing them at once.

### labwc 1:0.20.2-5

- A touch no longer leaves a hidden cursor behind that hovers whatever ends
  up under it: no stray hover highlights, tooltips or close marks after
  tapping or swiping, in any app.
