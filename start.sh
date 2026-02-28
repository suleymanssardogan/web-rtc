#!/bin/bash
echo "Installing dependencies..."
pip install -r requirements.txt || pip3 install -r requirements.txt

echo "Starting WebRTC Server..."
python server.py || python3 server.py
