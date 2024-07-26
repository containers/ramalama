MAKEFLAGS += -j2
default: help

help:
	@echo "Build Container"
	@echo
	@echo "  - make build"
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
	./install.sh

.PHONY:
build:
	./container_build.sh

.PHONY:
test:
	./ci.sh

.PHONY: clean
clean:
	@find . -name \*~ -delete
