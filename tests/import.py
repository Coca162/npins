# Tests for the importers from other pinning tools
# We call the upstream tools directly to generate their own lockfiles against our test repositories,
# then import it into npins

with npins_subtest("import niv"):
    succeed("niv init --nixpkgs owner/dependency -b test-branch")
    succeed("niv add git --repo http://localhost/tagged-repo.git -b test-branch -n tagged-repo")
    succeed("niv add tarball-pin -t http://localhost/testTarball")

    succeed("npins init --bare")
    succeed_snapshot("npins import-niv", "import_niv")

    dependency_head = ls_remote("https://github.com/owner/dependency.git", "refs/heads/test-branch")
    repo_head = ls_remote("http://localhost/tagged-repo.git", "refs/heads/test-branch")

    pins = dump_pins()
    # FIXME WTF? `npins import-niv` currently just skips over tarball pins?!
    assert set(pins.keys()) == {"nixpkgs", "tagged-repo"}, pins.keys()
    nixpkgs = pins["nixpkgs"]
    assert nixpkgs["type"] == "Git", nixpkgs
    assert nixpkgs["repository"] == {"type": "GitHub", "owner": "owner", "repo": "dependency"}
    assert nixpkgs["branch"] == "test-branch"
    assert nixpkgs["revision"] == dependency_head
    assert nixpkgs["url"] == f"https://github.com/owner/dependency/archive/{dependency_head}.tar.gz"
    repo = pins["tagged-repo"]
    assert repo["type"] == "Git", repo
    assert repo["repository"] == {"type": "Git", "url": "http://localhost/tagged-repo.git"}
    assert repo["branch"] == "test-branch"
    assert repo["revision"] == repo_head
    assert repo["url"] is None

    # Import only a single entry into a second lockfile
    succeed("npins --lock-file sources2.json init --bare")
    succeed("npins --lock-file sources2.json import-niv --name tagged-repo")
    assert set(dump_pins("sources2.json").keys()) == {"tagged-repo"}
    fail("npins import-niv --name tagged-repo")
    fail("npins import-niv --name does-not-exist")

with npins_subtest("import flake"):
    flake_nix = """
    {
      inputs = {
        tagged-repo = {
          url = "git+http://localhost/tagged-repo.git?ref=test-branch";
          flake = false;
        };
        dependency = {
          url = "github:owner/dependency/test-branch";
          flake = false;
        };
        tarball = {
          # The `tarball+` prefix is required because the URL has no tarball-like file extension, which would make this a "file" input
          url = "tarball+http://localhost/testTarball";
          flake = false;
        };
        # Actually, this is a "file", because it has no extension
        not-tarball = {
          url = "http://localhost/testTarball";
          flake = false;
        };
      };
      outputs = _: { };
    }
    """
    succeed(f"mkdir flake && echo {shlex.quote(flake_nix)} > flake/flake.nix")
    succeed("cd flake && nix --extra-experimental-features 'nix-command flakes' flake lock")

    succeed("npins init --bare")
    succeed_snapshot("npins import-flake flake/flake.lock", "import_flake")

    dependency_head = ls_remote("https://github.com/owner/dependency.git", "refs/heads/test-branch")
    tagged_head = ls_remote("http://localhost/tagged-repo.git", "refs/heads/test-branch")

    pins = dump_pins()
    assert set(pins.keys()) == {"tagged-repo", "dependency", "tarball"}, pins.keys()
    tagged = pins["tagged-repo"]
    assert tagged["type"] == "Git", tagged
    assert tagged["repository"] == {"type": "Git", "url": "http://localhost/tagged-repo.git"}
    assert tagged["branch"] == "test-branch"
    assert tagged["revision"] == tagged_head
    assert tagged["url"] is None
    dependency = pins["dependency"]
    assert dependency["type"] == "Git", dependency
    assert dependency["repository"] == {"type": "GitHub", "owner": "owner", "repo": "dependency"}
    assert dependency["branch"] == "test-branch"
    assert dependency["revision"] == dependency_head
    assert dependency["url"] == f"https://github.com/owner/dependency/archive/{dependency_head}.tar.gz"
    # tarball = pins["tarball"]
    # assert tarball["type"] == "Url", tarball
    # assert tarball["unpack"] is True
    # assert tarball["url"] == "http://localhost/testTarball"

    # Import only a single entry into a second lockfile
    succeed("npins --lock-file sources2.json init --bare")
    succeed("npins --lock-file sources2.json import-flake --name dependency flake/flake.lock")
    assert set(dump_pins("sources2.json").keys()) == {"dependency"}
    fail("npins import-flake --name dependency flake/flake.lock")
