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

### labwc 1:0.20.2-6

- A swipe up from the bottom edge reaches the notification center and the
  control center as their own drag, which follows the finger, instead of
  closing them at once.

## 2026-11-20

### labwc 1:0.20.2-5

- A touch no longer leaves a hidden cursor behind that hovers whatever ends
  up under it: no stray hover highlights, tooltips or close marks after
  tapping or swiping, in any app.
