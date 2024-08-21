MAKEFLAGS += -j2
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

.PHONY:
test:
	./ci.sh

.PHONY: clean
clean:
	@find . -name \*~ -delete
