MAKEFLAGS += -j2
OS := $(shell uname;)
SELINUXOPT ?= $(shell test -x /usr/sbin/selinuxenabled && selinuxenabled && echo -Z)
PREFIX ?= /usr/local
BINDIR ?= ${PREFIX}/bin
SHAREDIR ?= ${PREFIX}/share
PYTHON ?= $(shell command -v python3 python|head -n1)
DESTDIR ?= /
PATH := $(PATH):$(HOME)/.local/bin

default: help

help:
	@echo "Build Container"
	@echo
	@echo "  - make build"
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


.PHONY:
install-requirements:
	pipx install tqdm black flake8 argcomplete wheel omlmd huggingface_hub[cli] codespell

.PHONY:
install-completions:
	install ${SELINUXOPT} -d -m 755 $(DESTDIR)${SHAREDIR}/bash-completion/completions
	register-python-argcomplete --shell bash ramalama > $(DESTDIR)${SHAREDIR}/bash-completion/completions/ramalama
	install ${SELINUXOPT} -d -m 755 $(DESTDIR)${SHAREDIR}/fish/vendor_completions.d
	register-python-argcomplete --shell fish ramalama > $(DESTDIR)${SHAREDIR}/fish/vendor_completions.d/ramalama.fish

# FIXME: not available on Centos 9 yet.
#	install ${SELINUXOPT} -d -m 755 $(DESTDIR)${SHAREDIR}/zsh/site
#	register-python-argcomplete --shell zsh ramalama > $(DESTDIR)${SHAREDIR}/zsh/site/_ramalama

.PHONY:
install-shortnames:
	install ${SELINUXOPT} -d -m 755 $(DESTDIR)$(SHAREDIR)/ramalama
	install ${SELINUXOPT} -m 644 shortnames/shortnames.conf \
		$(DESTDIR)$(SHAREDIR)/ramalama

.PHONY:
completions:
	mkdir -p build/completions/bash-completion/completions
	register-python-argcomplete --shell bash ramalama > build/completions/bash-completion/completions/ramalama

	mkdir -p build/completions/fish/vendor_completions.d
	register-python-argcomplete --shell fish ramalama > build/completions/fish/vendor_completions.d/ramalama.fish

# FIXME: not available on Centos 9 yet.
#	mkdir -p build/completions/zsh/site
#	register-python-argcomplete --shell zsh ramalama > build/completions/zsh/site/_ramalama

.PHONY:
install: docs completions
	RAMALAMA_VERSION=$(RAMALAMA_VERSION) \
	pip install . --root $(DESTDIR) --prefix ${PREFIX}

.PHONY:
build:
ifeq ($(OS),Linux)
	./container_build.sh
endif

.PHONY: install-docs
install-docs: docs
	make -C docs install

.PHONY: docs
docs:
	make -C docs

.PHONY: lint
lint:
	black --line-length 120 --exclude 'venv/*' *.py ramalama/*.py  # Format the code
	flake8 --max-line-length=120 --exclude=venv *.py ramalama/*.py  # Check for any inconsistencies

.PHONY: codespell
codespell:
	codespell --dictionary=- -w

.PHONY: validate
validate: build codespell lint
ifeq ($(OS),Linux)
	hack/man-page-checker
	hack/xref-helpmsgs-manpages
endif

.PHONY:
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

.PHONY: ci
ci:
	test/ci.sh

.PHONY: test
test: validate bats bats-nocontainer ci
	make clean
	hack/tree_status.sh

.PHONY: clean
clean:
	@find . -name \*~ -delete
	@find . -name \*# -delete
	@find . -name \*.rej -delete
	@find . -name \*.orig -delete
	rm -rf $$(<.gitignore)
	make -C docs clean
