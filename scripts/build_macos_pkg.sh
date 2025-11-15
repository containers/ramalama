#!/bin/bash
#
# Build macOS installer package for RamaLama
#
# This script creates a self-contained .pkg installer that includes:
# - Standalone ramalama executable (built with PyInstaller)
# - All configuration files and man pages
# - Automatic PATH configuration
#
# Requirements:
# - macOS with Xcode Command Line Tools
# - Python 3.10+
# - PyInstaller (pip install pyinstaller)
#
# Usage: ./scripts/build_macos_pkg.sh

set -e

# Ensure we're on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "Error: This script must be run on macOS"
    exit 1
fi

# Check for required commands
for cmd in python3 pyinstaller pkgbuild productbuild; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "Error: Required command '$cmd' not found"
        echo "Please install required dependencies:"
        echo "  pip3 install pyinstaller"
        exit 1
    fi
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build/macos-pkg"

# Get version with error handling
if ! VERSION=$(cd "$PROJECT_ROOT/ramalama" && python3 -c "import version; print(version.version())" 2>/dev/null); then
    echo "Error: Failed to determine version"
    exit 1
fi

if [ -z "$VERSION" ]; then
    echo "Error: Version string is empty"
    exit 1
fi

echo "Building RamaLama v${VERSION} macOS Package"
echo "============================================="

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "$BUILD_DIR"
rm -rf "$PROJECT_ROOT/dist"
rm -rf "$PROJECT_ROOT/build"
mkdir -p "$BUILD_DIR"

# Build standalone executable with PyInstaller
echo "Building standalone executable..."
cd "$PROJECT_ROOT"
pyinstaller ramalama.spec --clean --noconfirm

# Verify build - PyInstaller creates either a single file or directory
BUILT_EXECUTABLE=""
if [ -f "$PROJECT_ROOT/dist/ramalama" ]; then
    BUILT_EXECUTABLE="$PROJECT_ROOT/dist/ramalama"
    echo "Found single-file executable: $BUILT_EXECUTABLE"
elif [ -f "$PROJECT_ROOT/dist/ramalama/ramalama" ]; then
    BUILT_EXECUTABLE="$PROJECT_ROOT/dist/ramalama/ramalama"
    echo "Found executable in bundle: $BUILT_EXECUTABLE"
elif [ -d "$PROJECT_ROOT/dist/ramalama.app" ]; then
    BUILT_EXECUTABLE="$PROJECT_ROOT/dist/ramalama.app/Contents/MacOS/ramalama"
    echo "Found app bundle: $PROJECT_ROOT/dist/ramalama.app"
else
    echo "Error: PyInstaller build failed - no executable found in dist/"
    echo "Contents of dist/:"
    ls -la "$PROJECT_ROOT/dist/" || true
    exit 1
fi

# Verify the executable is actually executable
if [ ! -x "$BUILT_EXECUTABLE" ]; then
    echo "Error: Built file is not executable: $BUILT_EXECUTABLE"
    exit 1
fi

echo "Standalone executable built successfully: $BUILT_EXECUTABLE"

# Create package structure
echo "Creating package structure..."
PKG_ROOT="$BUILD_DIR/package-root"
mkdir -p "$PKG_ROOT/usr/local/bin"
mkdir -p "$PKG_ROOT/usr/local/share/ramalama"
mkdir -p "$PKG_ROOT/usr/local/share/man/man1"
mkdir -p "$PKG_ROOT/usr/local/share/man/man5"
mkdir -p "$PKG_ROOT/usr/local/share/man/man7"
mkdir -p "$PKG_ROOT/usr/local/share/bash-completion/completions"
mkdir -p "$PKG_ROOT/usr/local/share/fish/vendor_completions.d"
mkdir -p "$PKG_ROOT/usr/local/share/zsh/site-functions"

# Copy executable
echo "Copying executable..."
if [ -d "$PROJECT_ROOT/dist/ramalama.app" ]; then
    # For app bundle, copy the executable from inside
    cp "$BUILT_EXECUTABLE" "$PKG_ROOT/usr/local/bin/ramalama"
else
    # For single file or directory bundle
    cp "$BUILT_EXECUTABLE" "$PKG_ROOT/usr/local/bin/ramalama"
fi
chmod +x "$PKG_ROOT/usr/local/bin/ramalama"

# Verify the copy worked
if [ ! -x "$PKG_ROOT/usr/local/bin/ramalama" ]; then
    echo "Error: Failed to copy executable to package root"
    exit 1
fi

# Copy configuration files
echo "Copying configuration files..."
cp "$PROJECT_ROOT/shortnames/shortnames.conf" "$PKG_ROOT/usr/local/share/ramalama/"
cp "$PROJECT_ROOT/docs/ramalama.conf" "$PKG_ROOT/usr/local/share/ramalama/"

# Copy inference spec files
mkdir -p "$PKG_ROOT/usr/local/share/ramalama/inference"
cp "$PROJECT_ROOT"/inference-spec/schema/*.json "$PKG_ROOT/usr/local/share/ramalama/inference/"
cp "$PROJECT_ROOT"/inference-spec/engines/* "$PKG_ROOT/usr/local/share/ramalama/inference/"

# Copy man pages
echo "Copying documentation..."
cp "$PROJECT_ROOT"/docs/*.1 "$PKG_ROOT/usr/local/share/man/man1/" || true
cp "$PROJECT_ROOT"/docs/*.5 "$PKG_ROOT/usr/local/share/man/man5/" || true
cp "$PROJECT_ROOT"/docs/*.7 "$PKG_ROOT/usr/local/share/man/man7/" || true

# Copy shell completions
echo "Copying shell completions..."
cp "$PROJECT_ROOT"/completions/bash-completion/completions/* "$PKG_ROOT/usr/local/share/bash-completion/completions/" || true
cp "$PROJECT_ROOT"/completions/fish/vendor_completions.d/* "$PKG_ROOT/usr/local/share/fish/vendor_completions.d/" || true
cp "$PROJECT_ROOT"/completions/zsh/site-functions/* "$PKG_ROOT/usr/local/share/zsh/site-functions/" || true

# Create package metadata
echo "Creating package metadata..."
SCRIPTS_DIR="$BUILD_DIR/scripts"
mkdir -p "$SCRIPTS_DIR"

cat > "$SCRIPTS_DIR/postinstall" << 'EOF'
#!/bin/bash
# Post-installation script for RamaLama

set -e

# Function to add PATH to shell config if not already present
add_to_shell_config() {
    local config_file="$1"
    local export_line='export PATH="/usr/local/bin:$PATH"'
    
    # Only modify if file exists or can be created
    if [ -f "$config_file" ] || touch "$config_file" 2>/dev/null; then
        # Check if PATH already includes /usr/local/bin
        if ! grep -q '/usr/local/bin' "$config_file" 2>/dev/null; then
            echo "" >> "$config_file"
            echo "# Added by RamaLama installer" >> "$config_file"
            echo "$export_line" >> "$config_file"
        fi
    fi
}

# Get the actual user (not root if using sudo)
ACTUAL_USER="${USER:-${SUDO_USER:-$(whoami)}}"
USER_HOME=$(eval echo "~$ACTUAL_USER")

# Add to shell configurations if they exist
for shell_config in "$USER_HOME/.zshrc" "$USER_HOME/.bash_profile" "$USER_HOME/.bashrc"; do
    if [ -f "$shell_config" ]; then
        add_to_shell_config "$shell_config"
    fi
done

echo "=========================================="
echo "RamaLama installed successfully!"
echo "=========================================="
echo ""
echo "Location: /usr/local/bin/ramalama"
echo ""
echo "Next steps:"
echo "  1. Restart your terminal or run: source ~/.zshrc"
echo "  2. Verify installation: ramalama --version"
echo "  3. Get help: ramalama --help"
echo ""

exit 0
EOF

chmod +x "$SCRIPTS_DIR/postinstall"

# Build the package
echo "Building .pkg installer..."
PKG_NAME="RamaLama-${VERSION}-macOS.pkg"
PKG_OUTPUT="$BUILD_DIR/$PKG_NAME"

pkgbuild \
    --root "$PKG_ROOT" \
    --identifier "com.github.containers.ramalama" \
    --version "$VERSION" \
    --scripts "$SCRIPTS_DIR" \
    --install-location "/" \
    "$PKG_OUTPUT"

# Copy installer resource files from templates
echo "Preparing installer resources..."
TEMPLATE_DIR="$SCRIPT_DIR/macos-installer"

# Process distribution XML template - replace placeholders
sed "s/{{VERSION}}/$VERSION/g; s/{{PKG_NAME}}/$PKG_NAME/g" \
    "$TEMPLATE_DIR/distribution.xml.template" > "$BUILD_DIR/distribution.xml"

# Copy HTML files
cp "$TEMPLATE_DIR/welcome.html" "$BUILD_DIR/welcome.html"
cp "$TEMPLATE_DIR/readme.html" "$BUILD_DIR/readme.html"
cp "$TEMPLATE_DIR/conclusion.html" "$BUILD_DIR/conclusion.html"

# Copy LICENSE
cp "$PROJECT_ROOT/LICENSE" "$BUILD_DIR/"

# Build final product
PRODUCT_PKG="$BUILD_DIR/RamaLama-${VERSION}-macOS-Installer.pkg"
productbuild \
    --distribution "$BUILD_DIR/distribution.xml" \
    --resources "$BUILD_DIR" \
    --package-path "$BUILD_DIR" \
    "$PRODUCT_PKG"

echo ""
echo "✓ Build complete!"
echo "  Package: $PRODUCT_PKG"
echo "  Size: $(du -h "$PRODUCT_PKG" | cut -f1)"
echo ""
echo "To test installation:"
echo "  sudo installer -pkg '$PRODUCT_PKG' -target /"
echo ""
echo "To distribute:"
echo "  1. Sign the package (recommended for public distribution)"
echo "  2. Upload to GitHub Releases"
echo "  3. Optionally notarize with Apple"

