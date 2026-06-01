#!/usr/bin/env bash
# Hugin desktop setup — configures systemd timer + path watcher + notify
# Run this ON YOUR DESKTOP after cloning the repo.
# Requires: libnotify (for notify-send)

set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
echo "📦 Hugin Desktop Setup"
echo "   Repo: $HERE"
echo ""

# ── 1. Check dependencies ──────────────────────────────────────────────
if ! command -v notify-send &>/dev/null; then
    echo "⚠️  notify-send not found. Install libnotify:"
    echo "   Fedora: sudo dnf install libnotify"
    echo "   Ubuntu: sudo apt install libnotify-bin"
    echo ""
fi

# ── 2. Copy notification script ─────────────────────────────────────────
mkdir -p "$HOME/.local/bin"
cp "$HERE/desktop/hugin-notify" "$HOME/.local/bin/hugin-notify"
chmod +x "$HOME/.local/bin/hugin-notify"
echo "✅ Installed ~/.local/bin/hugin-notify"

# ── 3. Install systemd units (user scope) ───────────────────────────────
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"

ln -sf "$HERE/systemd/hugin-dashboard.service" "$UNIT_DIR/"
ln -sf "$HERE/systemd/hugin-dashboard.timer"    "$UNIT_DIR/"
ln -sf "$HERE/desktop/hugin-watch.path"         "$UNIT_DIR/"
ln -sf "$HERE/desktop/hugin-watch.service"       "$UNIT_DIR/"

systemctl --user daemon-reload
echo "✅ Systemd units linked"

# ── 4. Enable timer + path watcher ──────────────────────────────────────
systemctl --user enable --now hugin-dashboard.timer 2>&1 || true
systemctl --user enable --now hugin-watch.path 2>&1 || true
echo "✅ Timer + path watcher enabled"

# ── 5. Verify ────────────────────────────────────────────────────────────
echo ""
echo "🔍 Status:"
systemctl --user list-timers --all 2>/dev/null | grep hugin || echo "   (no timers — check systemctl --user list-timers)"
systemctl --user list-units --all 2>/dev/null | grep hugin || true
echo ""
echo "📋 Briefing directory: ~/.local/share/hugin/"
echo "   (create it if Syncthing doesn't sync it automatically)"
mkdir -p "$HOME/.local/hugin/state" "$HOME/.local/hugin"
echo "   Syncthing: sync ~/.local/share/hugin/ between machines"
echo ""
echo "✨ Done. Desktop notifications will fire when state syncs."
