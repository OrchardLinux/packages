# Signing the repository

The repository is published unsigned today. This is what is left to do, in
order. Step 1 is Henrik's alone: the primary key must never exist on a machine
that runs CI or agents.

## What is in place

- `ci/publish` signs every package and the index when the secret
  `ORCHARD_SIGNING_KEY` is set, and publishes the `.sig` files beside them.
  With no secret it publishes unsigned. This path has not run yet.
- The publish job is the only job that sees the secret. It runs for pushes to
  `main` only, never for pull requests.

## 1. Create the key (offline, once)

One primary key that only certifies, kept offline, and one signing subkey for
CI. The primary key can replace the subkey at any time without tablets having
to trust a new key.

```sh
export GNUPGHOME=$(mktemp -d)     # a scratch keyring; ideally on a machine that is offline
NAME='OrchardLinux packages <ADDRESS>'      # choose the address

# Primary key: certify only, no expiry. No passphrase here; the backup below is encrypted.
gpg --batch --pinentry-mode loopback --passphrase '' --quick-generate-key "$NAME" ed25519 cert never
FPR=$(gpg --list-keys --with-colons "$NAME" | awk -F: '$1 == "fpr" { print $10; exit }')

# Signing subkey for CI, two years.
gpg --batch --pinentry-mode loopback --passphrase '' --quick-add-key "$FPR" ed25519 sign 2y

# Public key: goes into this repository and onto tablets.
gpg --armor --export "$FPR" > orchard.asc

# The CI secret: the signing subkey without the primary key's secret part.
gpg --armor --export-secret-subkeys "$FPR" > orchard-signing-subkey.asc

# The offline backup: everything, encrypted with a passphrase you choose. Also a revocation certificate.
gpg --export-secret-keys "$FPR" | gpg --symmetric --cipher-algo AES256 -o orchard-primary.gpg
gpg --gen-revoke "$FPR" > orchard-revoke.asc

echo "$FPR"
```

Keep `orchard-primary.gpg` and `orchard-revoke.asc` offline (two places).

## 2. Give CI the subkey

```sh
gh secret set ORCHARD_SIGNING_KEY --repo OrchardLinux/packages < orchard-signing-subkey.asc
rm -rf "$GNUPGHOME" orchard-signing-subkey.asc
```

Commit `orchard.asc` as `keyring/orchard.asc`.

## 3. Sign what is published

Signatures are made when a package is published, so every package has to go
through a publish once: raise each `pkgrel` (`tools/pkgrepo rebuild NAME...`)
and push. Check that each release has a `.sig` per package and
`orchard.db.sig`.

## 4. Tablets trust the key

Until an `orchard-keyring` package exists (not built yet; it would ship
`orchard.asc` and the fingerprint the way `archlinuxarm-keyring` does), an
image or a user adds the key once:

```sh
pacman-key --add orchard.asc
pacman-key --lsign-key FINGERPRINT
```

and the repository entry becomes

```ini
[orchard]
SigLevel = Required DatabaseOptional
Server = https://github.com/OrchardLinux/packages/releases/download/repo-$arch
```

`DatabaseOptional` is what upstream Omarchy's repository uses. The index is
signed too, so `SigLevel = Required` works; a tablet that syncs in the moment
between the upload of a new index and of its signature would then get an
error once and succeed on the next try.

`ci/container-verify` and `ci/container-installable` use `Optional TrustAll`
and need the same change (add the key, `Required`).

## Replacing the CI subkey

With the primary key restored from the backup: revoke or expire the old
subkey (`gpg --edit-key FPR`), add a new one as in step 1, export the public
key and the subkey again, set the secret again, commit the new
`keyring/orchard.asc`. Tablets that trust the primary key accept the new
subkey once they have the updated public key (the keyring package's job).
