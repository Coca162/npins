{ lib }:
repositories:
{ config, pkgs, ... }:
{
  networking.firewall.allowedTCPPorts = [ 3000 ];
  # virtualisation.memorySize = 2048;
  services.forgejo = {
    enable = true;
    settings.service.DISABLE_REGISTRATION = true;
    # Allow provisioning the repositories by simply pushing them
    settings.repository = {
      ENABLE_PUSH_CREATE_USER = true;
      DEFAULT_PUSH_CREATE_PRIVATE = false;
    };
    settings.server = {
      DOMAIN = "forgejo";
      ROOT_URL = "http://forgejo:3000/";
    };
  };

  # Oneshot service that uploads the repos to Forgejo on boot
  systemd.services.forgejo-provision = {
    wantedBy = [ "multi-user.target" ];
    requires = [ "forgejo.service" ];
    after = [ "forgejo.service" ];
    path = [
      config.services.forgejo.package
      pkgs.gitMinimal
      pkgs.curl
    ];
    environment.GITEA_WORK_DIR = "/var/lib/forgejo";
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      User = "forgejo";
      Group = "forgejo";
      TimeoutStartSec = "5min";
    };
    script = ''
      # Wait for the service to accept requests (is there a prettier way?)
      until curl -sSf http://localhost:3000/api/v1/version > /dev/null; do sleep 1; done
      forgejo admin user create --username owner --password dontchangeme \
        --email owner@example.com --must-change-password=false
      # The repositories in the store are not owned by us
      git config --global --add safe.directory '*'
      ${lib.pipe repositories [
        (lib.mapAttrsToList (
          path: repo: ''
            git --git-dir=${repo} push --mirror http://owner:dontchangeme@localhost:3000/${path}.git
          ''
        ))
        (lib.concatStringsSep "\n")
      ]}
    '';
  };
}
