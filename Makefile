MAKEFLAGS += -j2
OS := $(shell uname;)
SELINUXOPT ?= $(shell test -x /usr/sbin/selinuxenabled && selinuxenabled && echo -Z)
PREFIX ?= /usr/local
BINDIR ?= ${PREFIX}/bin
PYTHON ?= $(shell command -v python3 python|head -n1)
DESTDIR ?= /

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
	./container_build.sh

.PHONY: docs
docs:
	make -C docs

.PHONY: autopep8
autopep8:
	@pip install -q autopep8
	autopep8 --in-place --exit-code *.py ramalama/*py # Check style is correct

.PHONY: codespell
codespell:
	@pip install -q codespell
	codespell --dictionary=- -w

.PHONY: validate
validate: codespell autopep8
ifeq ($(OS),Linux)
	hack/man-page-checker
	hack/xref-helpmsgs-manpages
endif

.PHONY: test
test: validate
	test/ci.sh

.PHONY: clean
clean:
	@find . -name \*~ -delete
	@find . -name \*# -delete
	rm -rf $$(<.gitignore)
	make -C docs clean
