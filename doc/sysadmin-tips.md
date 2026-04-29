# Run in production management CLI commands with default deployment:
! Achtung ! Dangerous example -> db purge
```bash
sudo -u urlchecker bash -lc '
set -a
source /etc/url-checker/.env
set +a
source /usr/share/url-checker/.venv/bin/activate
export PYTHONPATH=/usr/share/url-checker/src
python3 /usr/share/url-checker/src/url_checker/management.py db-purge
'
```
