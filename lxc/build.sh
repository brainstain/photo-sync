#!/usr/bin/env bash
# build.sh — builds an LXC template for photos-sync
# Must be run as root (or via sudo). Invoke from the photo-sync/ directory.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(dirname "$SCRIPT_DIR")"   # photo-sync/ — contains *.py source files
BUILD_DIR="$SRC_DIR/lxc-build"
ROOTFS="$BUILD_DIR/rootfs"
META_DIR="$BUILD_DIR/meta"

# ------------------------------------------------------------
# Clean previous build
# ------------------------------------------------------------
echo "==> Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$ROOTFS" "$META_DIR"

# ------------------------------------------------------------
# Bootstrap Ubuntu 22.04 LTS (jammy)
# ------------------------------------------------------------
echo "==> Bootstrapping Ubuntu 22.04 (jammy)..."
debootstrap --arch=amd64 jammy "$ROOTFS" http://archive.ubuntu.com/ubuntu

# ------------------------------------------------------------
# Install Python 3 and pip
# ------------------------------------------------------------
echo "==> Installing Python 3..."
chroot "$ROOTFS" apt-get update -qq
chroot "$ROOTFS" apt-get install -y --no-install-recommends \
    python3 python3-pip ca-certificates

# ------------------------------------------------------------
# Install Python dependencies
# ------------------------------------------------------------
echo "==> Installing Python packages..."
chroot "$ROOTFS" pip3 install --no-cache-dir \
    synology-api==0.7.3 \
    flask==3.1.0

# ------------------------------------------------------------
# Install application source files
# ------------------------------------------------------------
echo "==> Copying application files..."
mkdir -p "$ROOTFS/opt/photos-sync"
cp "$SRC_DIR"/*.py "$ROOTFS/opt/photos-sync/"

# ------------------------------------------------------------
# Write /etc/default/photos-sync (environment configuration file)
# ------------------------------------------------------------
echo "==> Writing environment file..."
cat > "$ROOTFS/etc/default/photos-sync" << 'ENVFILE'
# /etc/default/photos-sync
# Configure photos-sync before starting the service.
# After editing this file, run: systemctl restart photos-sync

# Required: Synology NAS credentials
PHOTOS_USERNAME=
PHOTOS_PASSWORD=

# Required: Synology NAS address and port
PHOTOS_URL=
PHOTOS_PORT=

# Optional: Maximum in-memory cache size in MB (default: 250)
PHOTOS_MAX_CACHE=

# Optional: Sync interval in seconds (default: 60)
PHOTOS_INTERVAL=

# Optional: HTTP server port (default: 5000)
PHOTOS_SERVER_PORT=
ENVFILE

# ------------------------------------------------------------
# Write systemd unit file
# ------------------------------------------------------------
echo "==> Writing systemd unit file..."
cat > "$ROOTFS/etc/systemd/system/photos-sync.service" << 'UNITFILE'
[Unit]
Description=photos-sync — Synology NAS photo sync and HTTP server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=/etc/default/photos-sync
ExecStart=/usr/bin/python3 /opt/photos-sync/filesync.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNITFILE

# ------------------------------------------------------------
# Enable service at boot
# ------------------------------------------------------------
echo "==> Enabling service..."
mkdir -p "$ROOTFS/etc/systemd/system/multi-user.target.wants"
ln -sf /etc/systemd/system/photos-sync.service \
    "$ROOTFS/etc/systemd/system/multi-user.target.wants/photos-sync.service"

# ------------------------------------------------------------
# Write LXC image metadata
# ------------------------------------------------------------
echo "==> Writing metadata..."
CREATION_DATE=$(date +%s)
cat > "$META_DIR/metadata.yaml" << YAML
architecture: x86_64
creation_date: $CREATION_DATE
properties:
  description: photos-sync on Ubuntu 22.04 LTS (jammy)
  os: ubuntu
  release: jammy
  variant: default
templates: {}
YAML

# ------------------------------------------------------------
# Package rootfs and metadata as tarballs
# ------------------------------------------------------------
echo "==> Creating rootfs.tar.xz (this may take a few minutes)..."
tar -cJf "$BUILD_DIR/rootfs.tar.xz" -C "$ROOTFS" .

echo "==> Creating meta.tar.xz..."
tar -cJf "$BUILD_DIR/meta.tar.xz" -C "$META_DIR" .

echo ""
echo "Build complete. Artifacts:"
echo "  $BUILD_DIR/rootfs.tar.xz"
echo "  $BUILD_DIR/meta.tar.xz"
