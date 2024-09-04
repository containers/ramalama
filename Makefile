MAKEFLAGS += -j2
OS := $(shell uname;)

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
	./install.py
	make -c docs install
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
