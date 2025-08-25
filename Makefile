.PHONY: build-frontend clean-frontend install-frontend dev help build clean install install-dev dev-backend dev-frontend uv-lock uv-add

# Default target
help:
	@echo "Available targets:"
	@echo "  build                - Build everything (frontend + backend setup)"
	@echo "  build-frontend       - Build the frontend and place files for FastAPI"
	@echo "  clean                - Clean all build artifacts"
	@echo "  clean-frontend       - Clean frontend build artifacts"
	@echo "  install              - Install all dependencies (using uv)"
	@echo "  install-frontend     - Install frontend dependencies"
	@echo "  install-dev          - Install with development dependencies"
	@echo "  run                  - Start FastAPI development server"
	@echo "  test                 - Run all tests"
	@echo "  test-watch           - Run tests in watch mode"
	@echo "  verify-build         - Verify build artifacts after building"
	@echo "  uv-lock              - Update uv.lock file"
	@echo "  uv-add               - Add a new dependency (usage: make uv-add PACKAGE=package-name)"
	@echo "  build-docker         - Build Docker image"
	@echo "  run-docker           - Run Docker image"
	@echo ""
	@echo "Environment Variables:"
	@echo "  VITE_BACKEND_URL     - Automatically set to \"\" during build for relative API paths"

# Build targets
build: install build-frontend

build-frontend: install-frontend
	@echo "🏗️  Building frontend..."
	cd frontend && VITE_BACKEND_URL="" npm i && VITE_BACKEND_URL="" npm run build
	@echo "📁 Creating web directories..."
	mkdir -p web/static web/templates
	@echo "📋 Copying build artifacts..."
	cp -r frontend/dist/* web/static/
	@echo "🎯 Creating SPA template..."
	@mkdir -p web/templates
	@cp web/static/index.html web/templates/index.html
	@echo "✅ Frontend build complete!"
	@echo "   📂 Static files: web/static/"
	@echo "   📄 Template: web/templates/index.html"

# Clean targets
clean: clean-frontend
	@echo "🧹 Cleaning Python cache..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

clean-frontend:
	@echo "🧹 Cleaning frontend build artifacts..."
	rm -rf frontend/dist
	@echo "🧹 Cleaning web/static (preserving .gitkeep)..."
	@if [ -d "web/static" ]; then \
		find web/static -name ".gitkeep" -prune -o -type f -exec rm -f {} +; \
		find web/static -name ".gitkeep" -prune -o -type d -empty -exec rmdir {} + 2>/dev/null || true; \
	fi
	@echo "🧹 Cleaning web/templates (preserving .gitkeep)..."
	@if [ -d "web/templates" ]; then \
		find web/templates -name ".gitkeep" -prune -o -type f -exec rm -f {} +; \
		find web/templates -name ".gitkeep" -prune -o -type d -empty -exec rmdir {} + 2>/dev/null || true; \
	fi
	@echo "✅ Frontend cleaned (preserved .gitkeep files)!"

# Install targets
install: install-frontend
	@echo "🐍 Installing Python dependencies with uv..."
	uv sync

install-frontend:
	@echo "📦 Installing frontend dependencies..."
	@if command -v bun >/dev/null 2>&1; then \
		echo "Using bun..."; \
		cd frontend && bun install; \
	else \
		echo "Using npm..."; \
		cd frontend && npm install; \
	fi

# Development targets
run:
	@echo "🚀 Starting FastAPI development server..."
	uv run python -m uvicorn src.main_fastapi:app --reload --host 0.0.0.0 --port 8000

# Test targets
test:
	@echo "🧪 Running tests..."
	uv run --extra test python -m pytest

test-watch:
	@echo "🔍 Running tests in watch mode..."
	uv run --extra test python -m pytest --watch

# Additional uv-specific targets
install-dev:
	@echo "🐍 Installing Python dependencies with dev extras using uv..."
	uv sync --extra dev

uv-lock:
	@echo "🔒 Updating uv.lock file..."
	uv lock

uv-add:
	@echo "➕ Adding dependency: $(PACKAGE)"
	@if [ -z "$(PACKAGE)" ]; then \
		echo "❌ Error: Please specify PACKAGE=package-name"; \
		echo "   Example: make uv-add PACKAGE=requests"; \
		exit 1; \
	fi
	uv add $(PACKAGE)

# Production build verification
verify-build: build
	@echo "🔍 Verifying build..."
	@if [ -f "web/static/index.html" ]; then \
		echo "✅ Static files created successfully"; \
	else \
		echo "❌ Static files missing!"; \
		exit 1; \
	fi
	@if [ -f "web/templates/index.html" ]; then \
		echo "✅ Template created successfully"; \
	else \
		echo "❌ Template missing!"; \
		exit 1; \
	fi
	@echo "🎉 Build verification complete!"

build-docker:
	@echo "🐳 Building Docker image..."
	docker build -t video-generator .

run-docker:
	@echo "🐳 Running Docker image..."
	docker run --name video-generator --rm \
		-p 8000:8000 \
		--env-file .env \
		-v .storage \
		video-generator:latest