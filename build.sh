#!/bin/bash

# Installer ffmpeg avant de démarrer l'application
apt-get update
apt-get install -y ffmpeg

# Démarrer l'application
python app.py
