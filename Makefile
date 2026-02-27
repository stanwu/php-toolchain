.PHONY: help build

help:
	@echo "Available commands:"
	@echo "  build   - Run the build script."
	@echo "  help    - Show this help message."

build:
	@echo "Running build script..."
	@bash PROMPTS/build.sh
