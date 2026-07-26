# Default target, when you just call `just`
[private]
@list:
	just --list

# Run cargo unit tests
test *OPTIONS:
    cargo test --workspace

# Run nix integration tests and check their outputs against the recorded snapshots
# Use e.g. `just nix-test pinTypes` to run only that test
nix-test target='':
    nix-build --timeout 600 -A meta.tests{{ if target != '' { "." + target } else { "" } }} --no-out-link

# Run nix integration tests and check their outputs against the recorded snapshots on lix installations
# Use e.g. `just lix-test pinTypes` to run only that test
lix-test target='':
    # Container tests are unfortunately a CppNix-exclusive for now
    nix-build --timeout 600 -E '((import ./. {}).meta.tests.override { containerTests = false; }){{ if target != '' { "." + target } else { "" } }}' --no-out-link

# Overwrite the recorded snapshots with the current test outputs
update-snapshots:
    #!/usr/bin/env bash
    set -euo pipefail
    path=$(nix-build --timeout 600 -A meta.tests.snapshots --no-out-link)
    rm -r tests/snapshots_* || true
    cp -rL "$path"/* tests
    chmod -R u+w tests/snapshots_*

# Overwrite the recorded snapshots with the current test outputs
update-snapshots-lix:
    #!/usr/bin/env bash
    set -euo pipefail
    path=$(nix-build --timeout 600 -E '((import ./. {}).meta.tests.override { containerTests = false; }).snapshots' --no-out-link)
    rm -r tests/snapshots_* || true
    cp -rL "$path"/* tests
    chmod -R u+w tests/snapshots_*

# Update the README.md from README.md.in
update-readme:
  cp $(nix-build --timeout 300 readme.nix --no-out-link) README.md

# Some boring passthroughs for convenience and completeness

# Cargo build
build *OPTIONS:
    cargo build {{ OPTIONS }}

# Cargo check
check *OPTIONS:
    cargo check {{ OPTIONS }}
