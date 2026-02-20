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
# Cleanup: unmount chroot bind-mounts on exit (success or error)
# ------------------------------------------------------------
cleanup() {
    for mnt in dev/pts dev sys proc; do
        if mountpoint -q "$ROOTFS/$mnt" 2>/dev/null; then
            umount "$ROOTFS/$mnt" || true
        fi
    done
}
trap cleanup EXIT

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
# Bind-mount kernel filesystems so apt-get works inside chroot
# ------------------------------------------------------------
echo "==> Mounting kernel filesystems..."
mount -t proc  proc         "$ROOTFS/proc"
mount --bind   /sys          "$ROOTFS/sys"
mount --bind   /dev          "$ROOTFS/dev"
mount --bind   /dev/pts      "$ROOTFS/dev/pts"

# Forward DNS from the host
cp /etc/resolv.conf "$ROOTFS/etc/resolv.conf"

# Prevent package post-install scripts from starting daemons
cat > "$ROOTFS/usr/sbin/policy-rc.d" << 'EOF'
#!/bin/sh
exit 101
EOF
chmod +x "$ROOTFS/usr/sbin/policy-rc.d"

# ------------------------------------------------------------
# Enable universe repository (python3-pip lives there)
# ------------------------------------------------------------
cat > "$ROOTFS/etc/apt/sources.list" << 'SOURCES'
deb http://archive.ubuntu.com/ubuntu jammy main universe
deb http://archive.ubuntu.com/ubuntu jammy-updates main universe
deb http://security.ubuntu.com/ubuntu jammy-security main universe
SOURCES

# ------------------------------------------------------------
# Install Python 3 and pip
# ------------------------------------------------------------
echo "==> Installing Python 3..."
DEBIAN_FRONTEND=noninteractive chroot "$ROOTFS" apt-get update -qq
DEBIAN_FRONTEND=noninteractive chroot "$ROOTFS" apt-get install -y --no-install-recommends \
    python3 python3-pip ca-certificates

# ------------------------------------------------------------
# Install Python dependencies
# ------------------------------------------------------------
echo "==> Installing Python packages..."
cp "$SRC_DIR/requirements.txt" "$ROOTFS/tmp/requirements.txt"
chroot "$ROOTFS" pip3 install --no-cache-dir -r /tmp/requirements.txt
rm "$ROOTFS/tmp/requirements.txt"
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
# Unmount kernel filesystems before archiving
# ------------------------------------------------------------
echo "==> Unmounting kernel filesystems..."
cleanup

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
