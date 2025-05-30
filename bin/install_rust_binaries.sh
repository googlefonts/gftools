#!/usr/bin/env bash
# Install rust binaries for fontc, diffenator3 and fontspector
# into an active Python virtual environment

set -e

if [ -z "$VIRTUAL_ENV" ]; then
  echo "No Python virtual environment detected. Please activate one first."
  exit 1
fi

BIN_DIR="$VIRTUAL_ENV/bin"

install_from_tarball() {
  local url="$1"
  echo "Installing binaries from $url to $BIN_DIR"
  local tmpdir
  tmpdir=$(mktemp -d)
  curl -L "$url" | tar -xz -C "$tmpdir"
  find "$tmpdir" -type f -exec mv {} "$BIN_DIR" \;
  rm -rf "$tmpdir"
}

# Detect platform and set archive suffix
if [[ "$(uname)" == "Darwin" ]]; then
  if [[ "$(uname -m)" == "arm64" ]]; then
    SUFFIX="aarch64-apple-darwin.tar.gz"
  else
    SUFFIX="x86_64-apple-darwin.tar.gz"
  fi
elif [[ "$(uname)" == "Linux" ]]; then
  SUFFIX="unknown-linux-musl.tar.gz"
else
  echo "Unsupported OS: $(uname)"
  exit 1
fi

install_from_tarball "https://github.com/googlefonts/diffenator3/releases/download/v0.1.2/diffenator3-v0.1.2-$SUFFIX"
install_from_tarball "https://github.com/fonttools/fontspector/releases/download/fontspector-v1.0.2/fontspector-v1.0.2-$SUFFIX"
install_from_tarball "https://github.com/googlefonts/fontc/releases/download/fontc-v0.2.0/fontc-$SUFFIX"

chmod +x "$BIN_DIR/diffenator3" "$BIN_DIR/diff3proof" "$BIN_DIR/fontspector" "$BIN_DIR/fontc"
echo "Done."
