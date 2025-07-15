MAKEFLAGS += -j2
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
PYTHON_SCRIPTS := $(shell grep -lEr "^\#\!\s*/usr/bin/(env +)?python(3)?(\s|$$)" --exclude-dir={.venv,venv} $(PROJECT_DIR) || true)
PYTEST_COMMON_CMD ?= PYTHONPATH=. pytest test/unit/ -vv
BATS_IMAGE ?= localhost/bats:latest

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

install-detailed-cov-requirements:
	pip install ".[cov-detailed]"

.PHONY: install-cov-requirements
install-cov-requirements:
	pip install ".[cov]"

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
	_RAMALAMA_TEST=local RAMALAMA=$(CURDIR)/bin/ramalama bats -T test/system/030-run.bats
	_RAMALAMA_OPTIONS=--nocontainer _RAMALAMA_TEST=local bats -T test/system/030-run.bats

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

.PHONY: bats
bats:
	RAMALAMA=$(CURDIR)/bin/ramalama bats -T test/system/

.PHONY: bats-nocontainer
bats-nocontainer:
	_RAMALAMA_TEST_OPTS=--nocontainer RAMALAMA=$(CURDIR)/bin/ramalama bats -T test/system/

.PHONY: bats-docker
bats-docker:
	_RAMALAMA_TEST_OPTS=--engine=docker RAMALAMA=$(CURDIR)/bin/ramalama bats -T test/system/

.PHONY: bats-image
bats-image:
	podman inspect $(BATS_IMAGE) &> /dev/null || \
		podman build -t $(BATS_IMAGE) -f container-images/bats/Containerfile .

bats-in-container: extra-opts = --security-opt unmask=/proc/* --device /dev/net/tun --device /dev/fuse

%-in-container: bats-image
	podman run -it --rm \
		--userns=keep-id:size=200000 \
		--security-opt label=disable \
		--security-opt=mask=/sys/bus/pci/drivers/i915 \
		$(extra-opts) \
		-v $(CURDIR):/src \
		$(BATS_IMAGE) make $*

.PHONY: ci
ci:
	test/ci.sh

.PHONY: unit-tests
unit-tests:
	$(PYTEST_COMMON_CMD)

.PHONY: unit-tests-verbose
unit-tests-verbose:
	$(PYTEST_COMMON_CMD) --full-trace --capture=tee-sys

.PHONY: cov-run
cov-run: install-cov-requirements
	PYTHONPATH=. coverage run -m pytest test/unit/

.PHONY: cov-tests
cov-tests: cov-run
	PYTHONPATH=. coverage report

.PHONY: detailed-cov-tests
detailed-cov-tests: install-detailed-cov-requirements cov-run
	PYTHONPATH=. coverage report -m
	PYTHONPATH=. coverage html
	PYTHONPATH=. coverage json
	PYTHONPATH=. coverage lcov
	PYTHONPATH=. coverage xml


.PHONY: end-to-end-tests
end-to-end-tests: validate bats bats-nocontainer ci
	make clean
	hack/tree_status.sh

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
