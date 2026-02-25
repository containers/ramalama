MAKEFLAGS += -j2
OS := $(shell uname;)
SELINUXOPT ?= $(shell test -x /usr/sbin/selinuxenabled && selinuxenabled && echo -Z)
PREFIX ?= /usr/local
BINDIR ?= ${PREFIX}/bin
SHAREDIR ?= ${PREFIX}/share
PYTHON ?= $(shell command -v python3 python|head -n1)
DESTDIR ?= /
PATH := $(PATH):$(HOME)/.local/bin
MYPIP ?= pip
IMAGE ?= ramalama
PROJECT_DIR ?= $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
EXCLUDE_DIRS ?= .venv venv .tox build
EXCLUDE_OPTS ?= $(addprefix --exclude-dir=,$(EXCLUDE_DIRS))
PYTHON_SCRIPTS ?= $(shell grep -lEr "^\#\!\s*/usr/bin/(env +)?python(3)?(\s|$$)" $(EXCLUDE_OPTS) $(PROJECT_DIR) || true)
RUFF_TARGETS ?= ramalama scripts test bin/ramalama
E2E_IMAGE ?= localhost/e2e:latest

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

.PHONY: install-uv
install-uv:
	./install-uv.sh

.PHONY: install-requirements
install-requirements:
	${MYPIP} install ".[dev]"

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
	${MYPIP} install . --no-deps --root $(DESTDIR) --prefix ${PREFIX}

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

.PHONY: docs docs-manpages docsite-docs
docs: docs-manpages docsite-docs

docs-manpages:
	$(MAKE) -C docs

docsite-docs:
	$(MAKE) -C docsite convert

.PHONY: lint
lint:
	! git grep -n -- '#!/usr/bin/python3' -- ':!Makefile'
	ruff check $(RUFF_TARGETS)
	shellcheck *.sh */*.sh */*/*.sh

.PHONY: check-format
check-format:
	ruff check --select I $(RUFF_TARGETS)
	ruff format --check $(RUFF_TARGETS)

.PHONY: format
format:
	ruff check --select I --fix $(RUFF_TARGETS)
	ruff format $(RUFF_TARGETS)

.PHONY: codespell
codespell:
	codespell $(PROJECT_DIR) $(PYTHON_SCRIPTS)

.PHONY: test-run
test-run:
	_RAMALAMA_TEST=local RAMALAMA=$(CURDIR)/bin/ramalama bats -T test/system/030-run.bats
	_RAMALAMA_OPTIONS=--nocontainer _RAMALAMA_TEST=local bats -T test/system/030-run.bats

.PHONY: man-check
man-check:
ifeq ($(OS),Linux)
	hack/man-page-checker
	hack/xref-helpmsgs-manpages
endif

.PHONY: type-check
type-check:
	mypy $(addprefix --exclude=,$(EXCLUDE_DIRS)) --exclude test $(PROJECT_DIR)

.PHONY: validate
validate: codespell lint man-check type-check

.PHONY: pypi-build
pypi-build:   clean
	make docs
	python3 -m build --sdist
	python3 -m build --wheel

.PHONY: pypi
pypi: pypi-build
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

.PHONY: e2e-image
e2e-image:
	podman inspect $(E2E_IMAGE) &> /dev/null || \
		podman build -t $(E2E_IMAGE) -f container-images/e2e/Containerfile .

e2e-tests-in-container: extra-opts = --security-opt unmask=/proc/* --device /dev/net/tun

%-in-container: e2e-image
	podman run --rm \
		--userns=keep-id:size=200000 \
		--security-opt label=disable \
		--security-opt=mask=/sys/bus/pci/drivers/i915 \
		$(extra-opts) \
		-v /tmp \
		-v $(CURDIR):/src \
		$(E2E_IMAGE) make $*

.PHONY: ci
ci:
	test/ci.sh

.PHONY: requires-tox
requires-tox:
	@command -v tox >/dev/null 2>&1 || ${MYPIP} install tox

.PHONY: unit-tests
unit-tests: requires-tox
	tox

.PHONY: unit-tests-verbose
unit-tests-verbose: requires-tox
	tox -- --full-trace --capture=tee-sys

.PHONY: cov-tests
cov-tests: requires-tox
	tox -- --cov

.PHONY: detailed-cov-tests
detailed-cov-tests: requires-tox
	tox -e coverage

.PHONY: e2e-tests
e2e-tests: requires-tox
	# This makefile target runs the new e2e-tests pytest based
	tox -q -e e2e

.PHONY: e2e-tests-nocontainer
e2e-tests-nocontainer: requires-tox
	# This makefile target runs the new e2e-tests pytest based
	tox -q -e e2e -- --no-container

.PHONY: e2e-tests-docker
e2e-tests-docker: requires-tox
	# This makefile target runs the new e2e-tests pytest based
	tox -q -e e2e -- --container-engine=docker

.PHONY: end-to-end-tests
end-to-end-tests: validate e2e-tests e2e-tests-nocontainer ci
	make clean
	hack/tree_status.sh

.PHONY: test
test: tests

.PHONY: tests
tests: unit-tests end-to-end-tests

.PHONY: rag-requirements
rag-requirements:
	touch container-images/common/requirements-rag.in
	make -C container-images/common rag-requirements

.PHONY: clean
clean:
	make -C docs clean
	make -C docsite clean clean-generated
	find . -depth -print0 | git check-ignore --stdin -z | xargs -0 rm -rf
