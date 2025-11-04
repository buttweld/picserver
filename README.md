# picserver
A local picture server that displays the uploaded pictures on an EPD 7in3f e-ink display.
## Raspberry Pi Setup
Install Raspberry Pi OS Lite 32-bit to an SD card using Raspberry Pi Imager:
 - Set user name and password.
 - Enter Wi-Fi credentials.
 - Enable SSH.
SSH into pi using:
```bash
ssh <username>@pi.local
```
Enable SPI in raspi-config menu (in Interface Options → SPI):
```bash
sudo raspi-config
```
Update apt package list
```bash
sudo apt update
```
Install git and clone the project to home directory:
```bash
sudo apt install git
cd
git clone https://github.com/buttweld/picserver.git
```
Install python3 and system-level packages:
```bash
sudo apt install python3
sudo apt install python3-venv
sudo apt install python3-pip
sudo apt install python3-pil
sudo apt install python3-spidev
sudo apt install python3-numpy
```
or all together with a single command:
```bash
sudo apt install -y \
python3 python3-venv python3-pip \
python3-pil python3-spidev python3-numpy
```
Install library dependencies individually:
```bash
sudo apt install build-essential
sudo apt install libjpeg-dev
sudo apt install zlib1g-dev
sudo apt install libopenjp2-7-dev
sudo apt install libtiff5-dev
```
or all together with a single command:
```bash
sudo apt install -y build-essential libjpeg-dev \
zlib1g-dev libopenjp2-7-dev libtiff5-dev
```
Create a virtual environment in project directory and activate:
```bash
cd picserver
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
```
Install additional packages on venv using requirements.txt:
```bash
pip install -r requirements.txt
```
Start the server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Check whether the server is running. On a browser, open:
```bash
http:\\pi.local:8000
```
Kill the server with CTRL+C, then deactivate venv:
```bash
deactivate
```
## Automatic Startup on Boot
Setup a system service in order for the server to run on start-up.
Copy scripts/picserver.service to /etc/systemd/system/

Note: modify contents to match your user name. Optionally add an
OpenWeatherMap API key and update coordinates.
```bash
sudo cp ~/picserver/scripts/picserver.service /etc/systemd/system/
```
Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable picserver
sudo systemctl start picserver
```
Check server status (CTRL+C to exit):
```bash
cd ~/picserver/scripts
./show_server_status.sh
```
Stop the or restart the service using the following (if desired):
```bash
./stop_server.sh
./restart_server.sh
```
