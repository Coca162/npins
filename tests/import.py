# Tests for the importers from other pinning tools
# We call the upstream tools directly to generate their own lockfiles against our test repositories,
# then import it into npins

with npins_subtest("import niv"):
    succeed("niv init --nixpkgs owner/dependency -b test-branch")
    succeed("niv add git --repo http://localhost/tagged-repo.git -b test-branch -n tagged-repo")
    # Niv infers the type from the URL's file ending, defaulting to "file"
    succeed("niv add file-pin -t http://localhost/testTarball")
    succeed("niv add tarball-pin -T tarball -t http://localhost/testTarball")
    # Placeholders in the URL template mean that the URL is versioned, so the pin gets imported as immutable
    succeed("niv add versioned-pin -T tarball -s version=testTarball -t 'http://localhost/<version>'")

    succeed("npins init --bare")
    succeed_snapshot("npins import-niv", "import_niv")

    dependency_head = ls_remote("https://github.com/owner/dependency.git", "refs/heads/test-branch")
    repo_head = ls_remote("http://localhost/tagged-repo.git", "refs/heads/test-branch")

    pins = dump_pins()
    assert set(pins.keys()) == {"nixpkgs", "tagged-repo", "file-pin", "tarball-pin", "versioned-pin"}, pins.keys()
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
    file_pin = pins["file-pin"]
    assert file_pin["type"] == "Url", file_pin
    assert file_pin["unpack"] is False
    assert file_pin.get("update_url") is None
    assert file_pin["url"] == "http://localhost/testTarball"
    tarball = pins["tarball-pin"]
    assert tarball["type"] == "Url", tarball
    assert tarball["unpack"] is True
    assert tarball.get("update_url") is None
    assert tarball["url"] == "http://localhost/testTarball"
    versioned = pins["versioned-pin"]
    assert versioned["type"] == "Url", versioned
    assert versioned["unpack"] is True
    assert versioned["url"] == "http://localhost/testTarball"
    assert versioned["hash"]

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

with npins_subtest("import lon"):
    succeed("lon init")
    succeed("lon add github owner/dependency test-branch")
    succeed("lon add git tagged-repo http://localhost/tagged-repo.git test-branch")
    succeed("lon add git submoduled-repo http://localhost/submoduled-repo.git main --submodules")
    succeed("lon add git frozen-repo http://localhost/untagged-repo.git foo --frozen")
    # Lon has no CLI command for adding tarball sources (they only come from importing from other tools)
    # I assume they'll get around to fully supporting tarball pins eventually, so in the meantime
    # fake some entries to test it (the proper way would be `lon init --from npins`, but I'd feel silly doing that)
    lock = json.loads(succeed("cat lon.lock"))
    lock["sources"]["tarball"] = {
        "type": "Tarball",
        "fetchType": "tarball",
        "url": "http://localhost/testTarball",
        "hash": FAKE_HASH,
    }
    lock["sources"]["mutable-tarball"] = {
        "type": "Tarball",
        "fetchType": "tarball",
        "origin": "http://localhost/latest",
        "url": "http://localhost/testTarball",
        "hash": FAKE_HASH,
    }
    write_json("lon.lock", lock)

    succeed("npins init --bare")
    succeed_snapshot("npins import-lon", "import_lon")

    dependency_head = ls_remote("https://github.com/owner/dependency.git", "refs/heads/test-branch")
    tagged_head = ls_remote("http://localhost/tagged-repo.git", "refs/heads/test-branch")
    submoduled_head = ls_remote("http://localhost/submoduled-repo.git", "refs/heads/main")
    untagged_head = ls_remote("http://localhost/untagged-repo.git", "refs/heads/foo")

    pins = dump_pins()
    assert set(pins.keys()) == {
        "dependency",
        "tagged-repo",
        "submoduled-repo",
        "frozen-repo",
        "tarball",
        "mutable-tarball",
    }, pins.keys()
    dependency = pins["dependency"]
    assert dependency["type"] == "Git", dependency
    assert dependency["repository"] == {"type": "GitHub", "owner": "owner", "repo": "dependency"}
    assert dependency["branch"] == "test-branch"
    assert dependency["revision"] == dependency_head
    assert dependency["url"] == f"https://github.com/owner/dependency/archive/{dependency_head}.tar.gz"
    tagged = pins["tagged-repo"]
    assert tagged["type"] == "Git", tagged
    assert tagged["repository"] == {"type": "Git", "url": "http://localhost/tagged-repo.git"}
    assert tagged["branch"] == "test-branch"
    assert tagged["revision"] == tagged_head
    assert tagged["url"] is None
    assert "frozen" not in tagged
    submoduled = pins["submoduled-repo"]
    assert submoduled["type"] == "Git", submoduled
    assert submoduled["submodules"] is True
    assert submoduled["revision"] == submoduled_head
    frozen = pins["frozen-repo"]
    assert frozen["type"] == "Git", frozen
    assert frozen["frozen"] is True
    assert frozen["revision"] == untagged_head
    tarball = pins["tarball"]
    assert tarball["type"] == "Url", tarball
    assert tarball["unpack"] is True
    assert tarball["url"] == "http://localhost/testTarball"
    assert tarball["hash"] != FAKE_HASH  # The hash was re-fetched on import
    mutable_tarball = pins["mutable-tarball"]
    assert mutable_tarball["type"] == "MutableUrl", mutable_tarball
    assert mutable_tarball["unpack"] is True
    assert mutable_tarball["update_url"] == "http://localhost/latest"
    assert mutable_tarball["url"] == "http://localhost/testTarball"

    # Import only a single entry into a second lockfile
    succeed("npins --lock-file sources2.json init --bare")
    succeed("npins --lock-file sources2.json import-lon --name tagged-repo")
    assert set(dump_pins("sources2.json").keys()) == {"tagged-repo"}
    fail("npins import-lon --name tagged-repo")
    fail("npins import-lon --name does-not-exist")

    # Make sure our version check actually works 🙃
    lock["version"] = "2"
    write_json("lon2.lock", lock)
    fail_snapshot("npins import-lon lon2.lock", "import_lon_bad_version")
