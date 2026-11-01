#!/usr/bin/env bash
# =============================================================================
# Alveria Browser — One-Line Instant Installer
# =============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=================================================="
echo "🚀 [Alveria] Setting up Alveria Stealth Browser..."
echo "=================================================="

# 1. Dependency check
if ! python3 -c "import playwright" 2>/dev/null; then
    echo "📦 [Alveria] Installing Playwright via pip..."
    pip3 install --quiet playwright || pip install --quiet playwright
fi

# 2. Auto-download core binary
echo "⚡ [Alveria] Ensuring core stealth binary..."
python3 alveria_browser.py install

# 3. Create CLI symlink if possible
if [ -w /usr/local/bin ]; then
    ln -sf "$DIR/bin/alveria-browser" /usr/local/bin/alveria-browser
    echo "🔗 [Alveria] Global CLI symlinked: /usr/local/bin/alveria-browser"
elif command -v sudo >/dev/null 2>&1; then
    sudo ln -sf "$DIR/bin/alveria-browser" /usr/local/bin/alveria-browser 2>/dev/null && \
    echo "🔗 [Alveria] Global CLI symlinked: /usr/local/bin/alveria-browser" || true
fi

echo "=================================================="
echo "✅ [Alveria] Setup complete! You can now run:"
echo "   python3 alveria_browser.py fetch https://example.com"
echo "   or simply: alveria-browser fetch https://example.com"
echo "=================================================="
