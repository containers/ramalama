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

# Create distribution XML for product archive
cat > "$BUILD_DIR/distribution.xml" << EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="1">
    <title>RamaLama</title>
    <organization>com.github.containers</organization>
    <domains enable_localSystem="true"/>
    <options customize="never" require-scripts="false"/>
    <welcome file="welcome.html"/>
    <readme file="readme.html"/>
    <license file="LICENSE"/>
    <conclusion file="conclusion.html"/>
    <choices-outline>
        <line choice="default">
            <line choice="com.github.containers.ramalama"/>
        </line>
    </choices-outline>
    <choice id="default"/>
    <choice id="com.github.containers.ramalama" visible="false">
        <pkg-ref id="com.github.containers.ramalama"/>
    </choice>
    <pkg-ref id="com.github.containers.ramalama" version="$VERSION" onConclusion="none">$PKG_NAME</pkg-ref>
</installer-gui-script>
EOF

# Create welcome message
cat > "$BUILD_DIR/welcome.html" << 'EOF'
<!DOCTYPE html>
<html>
<head><title>Welcome to RamaLama</title></head>
<body>
<h1>Welcome to RamaLama Installer</h1>
<p>This installer will install RamaLama, a command-line tool for working with AI LLM models.</p>
<p>RamaLama makes working with AI models simple and straightforward.</p>
</body>
</html>
EOF

# Create readme
cat > "$BUILD_DIR/readme.html" << 'EOF'
<!DOCTYPE html>
<html>
<head><title>RamaLama Information</title></head>
<body>
<h1>About RamaLama</h1>
<p>RamaLama is a command-line tool that facilitates local management and serving of AI Models.</p>
<h2>Requirements</h2>
<ul>
    <li>macOS 10.15 or later</li>
    <li>Podman or Docker (recommended)</li>
</ul>
<h2>After Installation</h2>
<p>Run <code>ramalama --help</code> to get started.</p>
<p>For more information, visit: https://github.com/containers/ramalama</p>
</body>
</html>
EOF

# Create conclusion
cat > "$BUILD_DIR/conclusion.html" << 'EOF'
<!DOCTYPE html>
<html>
<head><title>Installation Complete</title></head>
<body>
<h1>Installation Complete!</h1>
<p>RamaLama has been successfully installed.</p>
<h2>Next Steps:</h2>
<ol>
    <li>Restart your terminal or run: <code>source ~/.zshrc</code></li>
    <li>Verify installation: <code>ramalama --version</code></li>
    <li>Get help: <code>ramalama --help</code></li>
    <li>Pull a model: <code>ramalama pull tinyllama</code></li>
    <li>Run a chatbot: <code>ramalama run tinyllama</code></li>
</ol>
<p>Documentation: https://github.com/containers/ramalama</p>
</body>
</html>
EOF

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

