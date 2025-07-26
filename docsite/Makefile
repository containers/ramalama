# RamaLama Documentation Site Makefile
# 
# This Makefile provides commands for building and managing the RamaLama
# documentation site powered by Docusaurus.

.PHONY: help convert dev build serve clean install clean-generated

# Default target - show help
help: ## Show this help message
	@echo "RamaLama Documentation Site"
	@echo "=========================="
	@echo
	@echo "Available commands:"
	@echo
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo

convert: ## Convert manpages from ../docs to MDX format for docsite
	@echo "Converting manpages to MDX format..."
	@python3 convert_manpages.py
	@echo "✅ Manpage conversion complete!"

install: ## Install dependencies
	@echo "Installing dependencies..."
	@npm install
	@echo "✅ Dependencies installed!"

dev: ## Start the development server
	@echo "Starting development server..."
	@npm start

build: ## Build the production site
	@echo "Building production site..."
	@npm run build
	@echo "✅ Build complete! Output in ./build/"

serve: ## Serve the built site locally
	@echo "Serving built site locally..."
	@npm run serve

clean: ## Clean build artifacts and node_modules
	@echo "Cleaning build artifacts..."
	@rm -rf build .docusaurus node_modules
	@echo "✅ Clean complete!"

clean-generated: ## Clean auto-generated MDX files
	@echo "Cleaning auto-generated MDX files..."
	@find docs -name "*.mdx" -exec grep -l "# This file is auto-generated from manpages. Do not edit manually." {} \; | while read file; do \
		echo "  Removing: $$file"; \
		rm "$$file"; \
	done
	@echo "✅ Auto-generated files cleaned!"

all: install convert build ## Install deps, convert manpages, and build site

# Development workflow targets
quick-dev: convert dev ## Convert manpages and start dev server

rebuild: clean install convert build ## Full rebuild from scratch
