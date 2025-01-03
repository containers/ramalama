import "./App.css";
import installIcon from "./assets/gravity-ui--arrow-shape-down-to-line.svg";
import githubIcon from "./assets/octicon--mark-github-24.svg";
import communityIcon from "./assets/gravity-ui--persons.svg";
import hardwareIcon from "./assets/gravity-ui--gear.svg";
import llamaMascot from "./assets/ramalama-logo-llama-only.svg";
import aboutGraphic1 from "./assets/ramalama-about-graphic-1.svg";
import aboutGraphic2 from "./assets/ramalama-about-graphic-2.svg";
import aboutGraphic3 from "./assets/ramalama-about-graphic-3.svg";
import aboutGraphic4 from "./assets/ramalama-about-graphic-4.svg";

function App() {
  return (
    <>
      {/* Welcome Section */}
      <div className="welcome viewport welcome-grid">
        <div className="welcome-info">
          <h1 className="welcome-h1-orange">rama</h1>
          <h1 className="welcome-h1">lama</h1>
          <h2 className="welcome-h2">
            Make working with AI boring through the use of OCI containers
          </h2>
          <ul>
            <li>
              <a href="https://github.com/containers/ramalama?tab=readme-ov-file#install">
                <button>
                  {" "}
                  <img src={installIcon} alt="Install Icon"></img>{" "}
                  <p>Installation guide here</p>
                </button>
              </a>
            </li>
            <li>
              <a href="https://github.com/containers/ramalama">
                <button>
                  {" "}
                  <img src={githubIcon} alt="GitHub Icon"></img>{" "}
                  <p>Contribute to the project</p>
                </button>
              </a>
            </li>
            <li>
              <a href="https://matrix.to/#/#ramalama:fedoraproject.org">
                <button>
                  {" "}
                  <img src={communityIcon} alt="Community Icon"></img>{" "}
                  <p>Interact with the community</p>
                </button>
              </a>
            </li>
            <li>
              <a href="https://github.com/containers/ramalama?tab=readme-ov-file#hardware-support">
                <button>
                  {" "}
                  <img src={hardwareIcon} alt="Hardware Icon"></img>{" "}
                  <p>Hardware support here</p>
                </button>
              </a>
            </li>
          </ul>
        </div>
        <div className="welcome-image">
          <img
            className="llama-mascot"
            src={llamaMascot}
            alt="RamaLama mascot"
          ></img>
        </div>
      </div>

      {/* Install Section */}
      <div className="install viewport orange-background" id="install">
        <div className="install-info">
          <h1 className="install-h1">It&apos;s one line and that&apos;s it!</h1>
          <h2 className="install-h2">
            Install RamaLama by running this in your command line:
          </h2>
          <h3 className="install-h3">Linux and Mac:</h3>
          <p className="install-code">
            <div>curl -fsSL https://raw.githubcontent.com/</div><div>containers/ramalama/s/install.sh | bash</div>
          </p>
          <h3 className="install-h3">RamaLama is also available on PyPi!</h3>
          <p className="install-code">pip install ramalama</p>
          <a href="https://github.com/containers/ramalama?tab=readme-ov-file#install">
            <button className="install-button">
              More install methods here
            </button>
          </a>
        </div>
      </div>

      {/* Demo Section */}
      <div className="demo viewport orange-background">
        <div className="demo-info">
          <h1 className="demo-header">Watch it in action</h1>
          {/* GIF Here */}
        </div>
      </div>

      {/* About Section */}
      <div className="about about-viewport" id="about">
        <div className="about-info">
          <h1 className="about-header">How does it work?</h1>
          <div className="about-grid">
            <img className="about-graphic-1" src={aboutGraphic1} alt="RamaLama About Graphic 1"></img>
            <p className="about-text-1">
              When RamaLama is first run, it inspects your system for GPU
              support, falling back to CPU support if no GPUs are present.
            </p>

            <img className="about-graphic-2" src={aboutGraphic2} alt="RamaLama About Graphic 2"></img>
            <p className="about-text-2">
              It then uses a container engine like Podman or Docker to download
              a container image from quay.io/ramalama.
            </p>

            <img className="about-graphic-3" src={aboutGraphic3} alt="RamaLama About Graphic 3"></img>
            <p className="about-text-3">
              Once the container image is in place, RamaLama pulls the specified
              AI Model from any of types of model registries.
            </p>

            <img className="about-graphic-4" src={aboutGraphic4} alt="RamaLama About Graphic 4"></img>
            <p className="about-text-4">
              Time to run our inferencing runtime. RamaLama offers switchable
              inferencing runtimes, namely llama.cpp and vLLM, for running
              containerized models.
            </p>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="footer orange-background">
        <footer>
          <p>© Ramalama</p>
          <p>
            <a href="https://github.com/containers/ramalama">Github</a> |{" "}
            <a href="https://matrix.to/#/#ramalama:fedoraproject.org">Matrix</a>{" "}
            |{" "}
            <a href="https://github.com/containers/ramalama/blob/main/README.md">
              Docs
            </a>
          </p>
          <p>Sponsored by Red Hat</p>
          <p>CC-BY-4.0</p>
        </footer>
      </div>
    </>
  );
}

export default App;
