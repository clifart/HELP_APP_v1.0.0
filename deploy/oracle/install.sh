#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-git@github.com:clifart/HELP_APP_v1.0.0.git}"
APP_DIR="/opt/help_app"
DATA_DIR="/opt/help_app_data"

sudo apt-get update
sudo apt-get install -y git nginx python3-venv python3-pip

if [ ! -d "$APP_DIR/.git" ]; then
  sudo git clone --depth 1 "$REPO_URL" "$APP_DIR"
else
  sudo git -C "$APP_DIR" pull --ff-only
fi

sudo mkdir -p "$DATA_DIR"
sudo chown -R ubuntu:www-data "$APP_DIR" "$DATA_DIR"

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements_server.txt"

if [ ! -f /etc/help-app.env ]; then
  SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  sudo tee /etc/help-app.env >/dev/null <<EOF
HELP_APP_DATA_DIR=$DATA_DIR
HELP_APP_SECRET_KEY=$SECRET_KEY
HELP_APP_MASTER_KEY=CAMBIAR_CLAVE_TECNICA
HELP_APP_ENABLE_AUTOCIERRE=1
HELP_APP_HTTPS=0
TZ=America/Bogota
EOF
fi

sudo cp "$APP_DIR/deploy/oracle/help-app.service" /etc/systemd/system/help-app.service
sudo cp "$APP_DIR/deploy/oracle/nginx-help-app.conf" /etc/nginx/sites-available/help-app
sudo ln -sfn /etc/nginx/sites-available/help-app /etc/nginx/sites-enabled/help-app
sudo rm -f /etc/nginx/sites-enabled/default

sudo systemctl daemon-reload
sudo systemctl enable --now help-app
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl restart nginx

echo "TrazOp instalado."
echo "Edita /etc/help-app.env para cambiar HELP_APP_MASTER_KEY."
echo "Estado: sudo systemctl status help-app --no-pager"
