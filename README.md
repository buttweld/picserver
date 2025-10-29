# picserver

FastAPI image upload + processing for Waveshare 7.3" e-paper (epd7in3f).

## Dev setup
```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000


## Copy scripts/picserver.service to /etc/systemd/system/, then:
sudo systemctl daemon-reload
sudo systemctl enable picserver
sudo systemctl start picserver
