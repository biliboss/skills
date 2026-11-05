#!/bin/bash
# Builds the release binary and assembles build/DevConsole.app (ad-hoc signed).
set -euo pipefail

cd "$(dirname "$0")"

# A Command Line Tools SDK newer than the compiler fails the build (and a stale SDKROOT in the
# environment can point at it): always use the SDK that xcrun pairs with the selected toolchain.
if command -v xcrun >/dev/null 2>&1; then
  SDK="$(xcrun --sdk macosx --show-sdk-path 2>/dev/null || true)"
  [[ -n "$SDK" ]] && export SDKROOT="$SDK"
fi

swift build -c release
BIN_DIR="$(swift build -c release --show-bin-path)"

APP="build/DevConsole.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$BIN_DIR/DevConsole" "$APP/Contents/MacOS/DevConsole"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key><string>com.biliboss.devconsole</string>
    <key>CFBundleName</key><string>DevConsole</string>
    <key>CFBundleDisplayName</key><string>DevConsole</string>
    <key>CFBundleExecutable</key><string>DevConsole</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>0.5.0</string>
    <key>CFBundleVersion</key><string>1</string>
    <key>LSMinimumSystemVersion</key><string>13.3</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>NSAppTransportSecurity</key>
    <dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict>
</plist>
PLIST

codesign --force --sign - --deep "$APP"
echo "Built $APP"
