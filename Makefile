OS := $(shell uname;)
SELINUXOPT ?= $(shell test -x /usr/sbin/selinuxenabled && selinuxenabled && echo -Z)
PREFIX ?= /usr/local
BINDIR ?= ${PREFIX}/bin
SHAREDIR ?= ${PREFIX}/share
PYTHON ?= $(shell command -v python3 python|head -n1)
DESTDIR ?= /
PATH := $(PATH):$(HOME)/.local/bin
IMAGE ?= ramalama
PROJECT_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
PYTHON_SCRIPTS := $(shell grep -lEr '^\#!\s*/usr/bin/(env +)?python(3)?(\s|$$)' $(PROJECT_DIR) | grep -Ev "\.py$$" | grep -Ev "(.venv|venv|.tox)" 2> /dev/null || true)
PYTEST_COMMON_CMD ?= PYTHONPATH=. pytest test/unit/ -vv
E2E_TESTS_IMAGE ?= localhost/ramalama-e2e:latest

default: help

help:
	@echo "Build Container Image"
	@echo
	@echo "  - make build"
	@echo "  - make build IMAGE=ramalama"
	@echo "  - make multi-arch"
	@echo "  - make multi-arch IMAGE=ramalama"
	@echo "  Build using build cache, for development only"
	@echo "  - make build IMAGE=ramalama CACHE=-C"
	@echo
	@echo "Build docs"
	@echo
	@echo "  - make docs"
	@echo
	@echo "Install ramalama"
	@echo
	@echo "  - make install"
	@echo
	@echo "Test ramalama"
	@echo
	@echo "  - make test"
	@echo
	@echo "Clean the repository"
	@echo
	@echo "  - make clean"
	@echo

.PHONY: install-requirements
install-requirements:
	./install-uv.sh
	pip install ".[dev]"

.PHONY: install-completions
install-completions: completions
	install ${SELINUXOPT} -d -m 755 $(DESTDIR)${SHAREDIR}/bash-completion/completions
	install ${SELINUXOPT} -m 644 completions/bash-completion/completions/ramalama \
		$(DESTDIR)${SHAREDIR}/bash-completion/completions/ramalama
	install ${SELINUXOPT} -d -m 755 $(DESTDIR)${SHAREDIR}/fish/vendor_completions.d
	install ${SELINUXOPT} -m 644 completions/fish/vendor_completions.d/ramalama.fish \
		$(DESTDIR)${SHAREDIR}/fish/vendor_completions.d/ramalama.fish
	install ${SELINUXOPT} -d -m 755 $(DESTDIR)${SHAREDIR}/zsh/site-functions
	install ${SELINUXOPT} -m 644 completions/zsh/site-functions/_ramalama \
		$(DESTDIR)${SHAREDIR}/zsh/site-functions/_ramalama

.PHONY: install-shortnames
install-shortnames:
	install ${SELINUXOPT} -d -m 755 $(DESTDIR)$(SHAREDIR)/ramalama
	install ${SELINUXOPT} -m 644 shortnames/shortnames.conf \
		$(DESTDIR)$(SHAREDIR)/ramalama

.PHONY: completions
completions:
	mkdir -p completions/bash-completion/completions
	register-python-argcomplete --shell bash ramalama > completions/bash-completion/completions/ramalama

	mkdir -p completions/fish/vendor_completions.d
	register-python-argcomplete --shell fish ramalama > completions/fish/vendor_completions.d/ramalama.fish

	mkdir -p completions/zsh/site-functions
	-register-python-argcomplete --shell zsh ramalama > completions/zsh/site-functions/_ramalama

.PHONY: install
install: docs completions
	RAMALAMA_VERSION=$(RAMALAMA_VERSION) \
	pip install . --no-deps --root $(DESTDIR) --prefix ${PREFIX}

.PHONY: build
build:
	./container_build.sh ${CACHE} build $(IMAGE) -v "$(VERSION)"

.PHONY: build-rm
build-rm:
	./container_build.sh ${CACHE} -r build $(IMAGE) -v "$(VERSION)"

.PHONY: build_multi_arch
build_multi_arch:
	./container_build.sh ${CACHE} multi-arch $(IMAGE) -v "$(VERSION)"

.PHONY: install-docs
install-docs: docs
	make -C docs install

.PHONY: docs
docs:
	make -C docs

.PHONY: lint
lint:
ifneq (,$(wildcard /usr/bin/python3))
	/usr/bin/python3 -m compileall -q .
endif

	! grep -ri --exclude-dir ".venv" --exclude-dir "*/.venv" "#\!/usr/bin/python3" .
	flake8 $(PROJECT_DIR) $(PYTHON_SCRIPTS)
	shellcheck *.sh */*.sh */*/*.sh

.PHONY: check-format
check-format:
	black --check --diff $(PROJECT_DIR) $(PYTHON_SCRIPTS)
	isort --check --diff $(PROJECT_DIR) $(PYTHON_SCRIPTS)

.PHONY: format
format:
	black $(PROJECT_DIR) $(PYTHON_SCRIPTS)
	isort $(PROJECT_DIR) $(PYTHON_SCRIPTS)

.PHONY: codespell
codespell:
	codespell -w $(PROJECT_DIR) $(PYTHON_SCRIPTS)

.PHONY: test-run
test-run:
	tox -e e2e -- test/e2e/test_run.py
	tox -e e2e -- --no-container test/e2e/test_run.py

.PHONY: validate
validate: codespell lint check-format
ifeq ($(OS),Linux)
	hack/man-page-checker
	hack/xref-helpmsgs-manpages
endif

.PHONY: pypi
pypi:   clean
	make docs
	python3 -m build --sdist
	python3 -m build --wheel
	python3 -m twine upload dist/*

.PHONY: e2e-tests-image
e2e-tests-image:
	podman inspect $(E2E_TESTS_IMAGE) &> /dev/null || \
		podman build -t $(E2E_TESTS_IMAGE) -f container-images/e2e/Containerfile .

e2e-tests-in-container: extra-opts = --security-opt unmask=/proc/* --device /dev/net/tun

%-in-container: e2e-tests-image
	podman run -it --rm \
		--userns=keep-id:size=200000 \
		--security-opt label=disable \
		--security-opt=mask=/sys/bus/pci/drivers/i915 \
		$(extra-opts) \
		-v $(CURDIR):/src \
		$(E2E_TESTS_IMAGE) make $*

.PHONY: unit-tests
unit-tests:
	tox -q

.PHONY: unit-tests-verbose
unit-tests-verbose:
	tox -q -- --full-trace --capture=tee-sys

.PHONY: e2e-tests
e2e-tests:
	tox -q -e e2e

.PHONY: e2e-tests-nocontainer
e2e-tests-nocontainer:
	tox -q -e e2e -- --no-container

.PHONY: e2e-tests-docker
e2e-tests-docker:
	tox -q -e e2e -- --container-engine=docker

.PHONY: end-to-end-tests
end-to-end-tests: validate e2e-tests e2e-tests-nocontainer

.PHONY: ci-end-to-end-tests
ci-end-to-end-tests: validate e2e-tests e2e-tests-nocontainer
	test/ci.sh

.PHONY: coverage
coverage:
	tox -q -e coverage

.PHONY: test
test: tests

.PHONY: tests
tests: unit-tests end-to-end-tests

.PHONY: clean
clean:
	@find . -name \*~ -delete
	@find . -name \*# -delete
	@find . -name \*.rej -delete
	@find . -name \*.orig -delete
	rm -rf $$(<.gitignore)
	make -C docs clean
