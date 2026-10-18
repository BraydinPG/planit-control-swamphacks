#!/usr/bin/env bash
# One-time server setup (T079). Run as root on a fresh Ubuntu 24.04 server; safe to rerun.
#   ssh root@SERVER 'bash -s' < deploy/setup.sh
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q curl ca-certificates debian-keyring debian-archive-keyring apt-transport-https gnupg

# Caddy from its official repository.
if ! command -v caddy >/dev/null; then
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q
  apt-get install -y -q caddy
fi

# A non-root user owns the app; the API runs as this user.
id foresite >/dev/null 2>&1 || useradd --system --home /srv/foresite --shell /usr/sbin/nologin foresite
mkdir -p /srv/foresite/app /srv/foresite/frontend /srv/foresite/photos /srv/foresite/.cache

# uv installs the same Python and packages the team develops with (3.14).
if [ ! -x /usr/local/bin/uv ]; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
fi
export UV_PYTHON_INSTALL_DIR=/srv/foresite/python
uv python install 3.14
[ -x /srv/foresite/venv/bin/python ] || uv venv --python 3.14 /srv/foresite/venv

chown -R foresite:foresite /srv/foresite
# Caddy only traverses /srv/foresite to read the built frontend; photos and .env stay private.
chmod 711 /srv/foresite
chmod 750 /srv/foresite/photos

# Vultr's Ubuntu image enables ufw with only SSH open; Caddy needs 80 and 443.
if command -v ufw >/dev/null; then
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
fi

# Unattended security updates.
apt-get install -y -q unattended-upgrades
echo "setup complete"
