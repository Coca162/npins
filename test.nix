{
  testers,
  lib,
  npins,
  runCommand,
  openssl,
  gitMinimal,
  dockerTools,
  linkFarm,
  containerTests ? true,
}:
let
  # Can't call `callPackage` because it injects some overrides stuff we don't want …
  testHosts = import ./tests/vm.nix {
    inherit
      lib
      runCommand
      openssl
      gitMinimal
      dockerTools
      npins
      ;
  };

  # Note: We must use VMs here because Nixpkgs doesn't support Lix currently,
  # See <https://git.lix.systems/lix-project/lix/issues/1243>
  mkTest =
    name: script:
    testers.runNixOSTest {
      name = "npins-${name}-test";
      ${if containerTests then "containers" else "nodes"} = testHosts;
      globalTimeout = 600; # Defaults to 1h, but we're not Nixpkgs scale
      testScript = lib.concatLines [
        (builtins.readFile ./tests/common.py)
        (builtins.readFile script)
      ];
    };

  # The raw VM tests, which may write to $out/snapshots each
  tests = {
    cli = mkTest "cli" ./tests/cli.py;
    pinTypes = mkTest "pin-types" ./tests/pin-types.py;
    import = mkTest "import" ./tests/import.py;
  };

  # Take a test and ensure its snapshots output is unchanged relative to our local golden
  checkSnapshots =
    name: test:
    runCommand "npins-snapshot-check-${name}"
      {
        # Maximize the probability that the dev sees the build log containing the diff
        preferLocalBuild = true;
        allowSubstitutes = false;
      }
      (
        let
          # Import the golden path to the store if it exists, treat like an empty directory otherwise
          goldenPath = ./tests/snapshots_${name};
          path = if builtins.pathExists goldenPath then "${goldenPath}" else "$(mkdir empty; echo empty)";
        in
        ''
          if diff --unified --recursive ${path} ${test}/snapshots; then
            ln -s ${test} $out
          else
            echo "error: snapshot mismatch for test '${name}'"
            echo "Run \`just update-snapshots\` to accept the changes"
            exit 1
          fi
        ''
      );
in
# The tests we expose contain the output check
(lib.mapAttrs checkSnapshots tests)
// {
  # Run the tests and combine the outputs for `just update-snapshots` to copy
  snapshots = linkFarm "npins-test-snapshots" (
    lib.mapAttrsToList (name: test: {
      name = "snapshots_${name}";
      path = "${test}/snapshots";
    }) tests
  );
}
