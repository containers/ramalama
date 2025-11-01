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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build/macos-pkg"
VERSION=$(cd "$PROJECT_ROOT/ramalama" && python3 -c "import version; print(version.version())")

echo "Building RamaLama v${VERSION} macOS Package"
echo "============================================="

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "$BUILD_DIR"
rm -rf "$PROJECT_ROOT/dist"
rm -rf "$PROJECT_ROOT/build"
mkdir -p "$BUILD_DIR"

# Install PyInstaller if not present
if ! command -v pyinstaller &> /dev/null; then
    echo "Installing PyInstaller..."
    pip3 install pyinstaller
fi

# Build standalone executable with PyInstaller
echo "Building standalone executable..."
cd "$PROJECT_ROOT"
pyinstaller ramalama.spec --clean --noconfirm

# Verify build
if [ ! -f "$PROJECT_ROOT/dist/ramalama" ]; then
    echo "Error: PyInstaller build failed - executable not found"
    exit 1
fi

echo "Standalone executable built successfully"

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
cp "$PROJECT_ROOT/dist/ramalama" "$PKG_ROOT/usr/local/bin/ramalama"
chmod +x "$PKG_ROOT/usr/local/bin/ramalama"

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

# Ensure /usr/local/bin is in PATH
EXPORT_LINE='export PATH="/usr/local/bin:$PATH"'
if ! grep -Fxq "$EXPORT_LINE" ~/.zshrc 2>/dev/null; then
    echo "$EXPORT_LINE" >> ~/.zshrc
fi

if ! grep -q '/usr/local/bin' ~/.bash_profile 2>/dev/null; then
    echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.bash_profile
fi

echo "RamaLama installed successfully!"
echo "You may need to restart your terminal or run: source ~/.zshrc"
echo "Try: ramalama --version"

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

