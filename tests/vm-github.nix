{
  lib,
  runCommand,
  gitMinimal,
  mockCert,
  gitHttpBackend,
}:
repositories:
let
  # Generate a snippet of shell code for every hosted repository
  forEachRepo = f: lib.concatStringsSep "\n" (lib.mapAttrsToList f repositories);

  gitSetup = ''
    export HOME=$TMP
    git config --global --add safe.directory '*'
  '';

  # The git repositories themselves, served via git smart HTTP
  gitData = runCommand "github-git-data" { } (
    forEachRepo (
      path: repo: ''
        mkdir -p $out/${dirOf path}
        ln -s ${repo} $out/${path}.git
      ''
    )
  );

  # Archive tarballs of every commit, to be served on github.com
  webData = runCommand "github-web-data" { nativeBuildInputs = [ gitMinimal ]; } (
    gitSetup
    + forEachRepo (
      path: repo: ''
        mkdir -p $out/${path}/archive
        for rev in $(git --git-dir=${repo} rev-list --all); do
          git --git-dir=${repo} archive --format=tar.gz -o $out/${path}/archive/$rev.tar.gz $rev
        done
      ''
    )
  );

  # Metadata and stuff, to be served on api.github.com
  # Warning: this is not pretty code
  apiData = runCommand "github-api-data" { nativeBuildInputs = [ gitMinimal ]; } (
    gitSetup
    + forEachRepo (
      path: repo: ''
        # Repository metadata, e.g. queried by niv
        mkdir -p $out/repos/${dirOf path}
        echo "{\"default_branch\": \"$(git --git-dir=${repo} symbolic-ref --short HEAD)\"}" > $out/repos/${path}-info.json

        # The latest commit of each branch, as JSON (flake github fetcher)
        # and as plain sha (niv; see the Accept header dispatch in the nginx config)
        mkdir -p $out/repos/${path}/commits
        git --git-dir=${repo} for-each-ref refs/heads --format='%(refname:short) %(objectname)' | while read branch sha; do
          printf '{"sha": "%s"}' "$sha" > $out/repos/${path}/commits/$branch.json
          printf '%s' "$sha" > $out/repos/${path}/commits/$branch.sha
        done

        # Archive tarballs of every commit (flake github fetcher) and every tag (npins releases)
        mkdir -p $out/repos/${path}/tarball/refs/tags
        for rev in $(git --git-dir=${repo} rev-list --all); do
          git --git-dir=${repo} archive --format=tar.gz -o $out/repos/${path}/tarball/$rev $rev
        done
        for tag in $(git --git-dir=${repo} tag); do
          git --git-dir=${repo} archive --format=tar.gz -o $out/repos/${path}/tarball/refs/tags/$tag $tag
        done
      ''
    )
  );
in
{ config, ... }:
{
  networking.firewall.allowedTCPPorts = [
    80
    443
  ];

  # CGI wrapper for serving the repositories via git smart HTTP
  services.fcgiwrap.instances.git = {
    socket.user = "nginx";
    socket.group = "nginx";
  };

  services.nginx = {
    enable = true;

    # niv requests the plain commit sha with a special `Accept` header,
    # everyone else (e.g. the flake github fetcher) gets JSON
    appendHttpConfig = ''
      map $http_accept $github_commit_format {
        default "json";
        "~vnd\.github\.v3\.sha" "sha";
      }
    '';

    virtualHosts."github.com" = {
      addSSL = true;
      sslCertificate = "${mockCert}/cert.pem";
      sslCertificateKey = "${mockCert}/key.pem";

      # The archive tarballs of every commit
      root = "${webData}";
      # The git repositories
      locations."~ ^/[^/]+/[^/]+\\.git/".extraConfig = gitHttpBackend config "${gitData}";
    };

    virtualHosts."api.github.com" = {
      addSSL = true;
      sslCertificate = "${mockCert}/cert.pem";
      sslCertificateKey = "${mockCert}/key.pem";

      root = "${apiData}";
      locations."~ ^/repos/[^/]+/[^/]+$".extraConfig = ''
        default_type application/json;
        try_files $uri-info.json =404;
      '';
      # Named captures, because evaluating the map resets the numbered ones (sigh)
      locations."~ ^/repos/(?<gh_repo>[^/]+/[^/]+)/commits/(?<gh_ref>[^/]+)$".extraConfig = ''
        default_type application/json;
        try_files /repos/$gh_repo/commits/$gh_ref.$github_commit_format =404;
      '';
    };
  };
}
