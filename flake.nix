{
  inputs = {
    nixpkgs = {
      url = "github:NixOS/nixpkgs/nixos-unstable";
    };
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];

      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;

      mkRamaLama = pkgs: with pkgs;
        callPackage
          (
            { ramalamaOverrides ? { }
            , llamaCppOverrides ? { }
            }:
              python3Packages.buildPythonPackage ({
                name = "ramalama";
                src = ./.;
                pyproject = true;
                build-system = with python3Packages; [ setuptools ];
                dependencies = with python3Packages; [
                  argcomplete
                  pyyaml
                  jsonschema
                  jinja2
                  (llama-cpp.override llamaCppOverrides)
                ];
                nativeBuildInputs =
                  (with pkgs; [ codespell shellcheck isort bats jq apacheHttpd ]) ++
                  (with pkgs.python3Packages; [ flake8 black pytest ]);
              } // ramalamaOverrides)
          )
          { llamaCppOverrides.vulkanSupport = true; }
          ;

      ramalama = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          package = mkRamaLama pkgs;
        in {
          inherit package;
          app = {
            type = "app";
            program = toString (pkgs.writeShellScript "ramalama" "${package}/bin/ramalama \"$@\"");
          };
        }
      );
    in {
      packages = forAllSystems (system: {
        ramalama = ramalama.${system}.package;
        default = ramalama.${system}.package;
      });

      apps = forAllSystems (system: {
        ramalama = ramalama.${system}.app;
        default = ramalama.${system}.app;
      });
    };
}
