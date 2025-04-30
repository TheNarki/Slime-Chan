# Image officielle Python avec Debian
FROM python:3.11-slim

# Installer ffmpeg et dépendances de base
RUN apt-get update && \
    apt-get install -y ffmpeg git curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail
WORKDIR /app

# Copier tous les fichiers de ton projet dans le conteneur
COPY . /app

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Spécifie les variables d’environnement (à configurer dans Koyeb)
ENV PYTHONUNBUFFERED=1

# Ouvre le port si ton app Flask en a besoin (ex. 5000)
EXPOSE 5000

# Commande pour démarrer ton app
# Remplace "main.py" par le nom réel de ton fichier principal (ex: bot.py ou app.py)
CMD ["python", "main.py"]
