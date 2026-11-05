#!/bin/bash
# Builds the release binary and assembles build/StatusTimer.app (ad-hoc signed).
set -euo pipefail

cd "$(dirname "$0")"

swift build -c release
BIN_DIR="$(swift build -c release --show-bin-path)"

APP="build/StatusTimer.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$BIN_DIR/StatusTimer" "$APP/Contents/MacOS/StatusTimer"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key><string>com.biliboss.statustimer</string>
    <key>CFBundleName</key><string>StatusTimer</string>
    <key>CFBundleDisplayName</key><string>StatusTimer</string>
    <key>CFBundleExecutable</key><string>StatusTimer</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>2.0</string>
    <key>CFBundleVersion</key><string>2</string>
    <key>LSMinimumSystemVersion</key><string>13.0</string>
    <key>LSUIElement</key><true/>
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

codesign --force --sign - --deep "$APP"
echo "Built $APP"
