MAKEFLAGS += -j2
OS := $(shell uname;)
SELINUXOPT ?= $(shell test -x /usr/sbin/selinuxenabled && selinuxenabled && echo -Z)
PREFIX ?= /usr/local
BINDIR ?= ${PREFIX}/bin
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
install:
	install ${SELINUXOPT} -d -m 755 $(DESTDIR)$(BINDIR)
	install ${SELINUXOPT} -m 755 ramalama.py \
		$(DESTDIR)$(BINDIR)/ramalama
	RAMALAMA_VERSION=$(RAMALAMA_VERSION) \
	pip install . --root $(DESTDIR) --prefix ${PREFIX}

	make -C docs install
.PHONY:
build:
ifeq ($(OS),Linux)
	./container_build.sh
endif

.PHONY: docs
docs:
	make -C docs

.PHONY: lint
lint:
	@pip install -q black flake8
	echo $$PATH
	black --line-length 120 --exclude 'venv/*' *.py ramalama/*.py  # Format the code
	flake8 --max-line-length=120 --exclude=venv *.py ramalama/*.py  # Check for any inconsistencies

.PHONY: codespell
codespell:
	@pip install -q codespell
	codespell --dictionary=- -w

.PHONY: validate
validate: build codespell lint
ifeq ($(OS),Linux)
	hack/man-page-checker
	hack/xref-helpmsgs-manpages
endif

.PHONY: bats
bats:
	RAMALAMA=$(CURDIR)/ramalama.py bats -T test/system/

.PHONY: test
test: validate
	test/ci.sh
	make clean
	hack/tree_status.sh

.PHONY: clean
clean:
	@find . -name \*~ -delete
	@find . -name \*# -delete
	rm -rf $$(<.gitignore)
	make -C docs clean
