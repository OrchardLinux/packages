#!/bin/sh
# apk runs this after a transaction changed /usr/lib/modules/*, /usr/share/orchard
# or /usr/lib/orchard: this system's boot entries follow (orchard docs/boot-contract.md).
[ ! -x /usr/lib/orchard/boot-entries ] || exec /usr/lib/orchard/boot-entries sync
