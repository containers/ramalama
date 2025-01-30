This README provides a step-by-step guide on how to run ramalama on macOS.

```bash
brew install go
brew install podman
go install github.com/cpuguy83/go-md2man/v2@latest
python3 -m venv ~/.venvs/ramalama
source ~/.venvs/ramalama/bin/activate
pip install argcomplete
sudo make install
podman machine init
podman machine start
sudo make build
```

