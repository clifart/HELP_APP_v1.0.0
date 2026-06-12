# TrazOp en Oracle Cloud

## Crear la instancia

- Imagen: Ubuntu 24.04.
- Shape gratuito: VM.Standard.A1.Flex o VM.Standard.E2.1.Micro.
- Usar una sola instancia.
- Agregar la clave SSH durante la creacion.
- Abrir puertos TCP 22, 80 y posteriormente 443 en la VCN.

## Instalar

El repositorio es privado. En la instancia Oracle, crear una Deploy Key:

```bash
ssh-keygen -t ed25519 -C "oracle-trazop" -f ~/.ssh/trazop_deploy -N ""
cat ~/.ssh/trazop_deploy.pub
```

Copiar la clave mostrada en GitHub:

```text
Repositorio > Settings > Deploy keys > Add deploy key
```

Dejar desmarcada la opcion de escritura. Luego configurar SSH en Oracle:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/trazop_deploy
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
ssh-keyscan github.com >> ~/.ssh/known_hosts
ssh -T git@github.com
```

Instalar TrazOp:

```bash
git clone git@github.com:clifart/HELP_APP_v1.0.0.git /tmp/help_app_setup
chmod +x /tmp/help_app_setup/deploy/oracle/install.sh
/tmp/help_app_setup/deploy/oracle/install.sh
```

Cambiar la clave tecnica:

```bash
sudo nano /etc/help-app.env
sudo systemctl restart help-app
```

La app queda inicialmente en:

```text
http://IP_PUBLICA
```

## Actualizar desde GitHub

```bash
cd /opt/help_app
sudo -u ubuntu git pull --ff-only
/opt/help_app/.venv/bin/pip install -r requirements_server.txt
sudo systemctl restart help-app
```

Los datos permanecen en `/opt/help_app_data` y no se reemplazan con `git pull`.
El servicio usa la zona horaria `America/Bogota`.

## Copiar la base actual de forma privada

La base real no se sube a GitHub. Desde PowerShell en el PC:

```powershell
scp .\database.db ubuntu@IP_PUBLICA:/tmp/database.db
ssh ubuntu@IP_PUBLICA "sudo systemctl stop help-app && sudo mv /tmp/database.db /opt/help_app_data/database.db && sudo chown ubuntu:www-data /opt/help_app_data/database.db && sudo systemctl start help-app"
```

Hacer esta copia una sola vez, antes de que los usuarios comiencen a trabajar en Oracle.

## Activar HTTPS

Asociar un dominio o subdominio a la IP publica y ejecutar:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d TU_DOMINIO
sudo sed -i 's/HELP_APP_HTTPS=0/HELP_APP_HTTPS=1/' /etc/help-app.env
sudo systemctl restart help-app
```

Despues, cambiar la URL del APK por `https://TU_DOMINIO/`.
