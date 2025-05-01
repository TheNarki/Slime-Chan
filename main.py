import os
import discord
from discord.ext import commands
import random
from google.cloud import dialogflow_v2
from google.oauth2 import service_account
import json
from discord import FFmpegPCMAudio, PCMVolumeTransformer
import asyncio
from discord import app_commands  # Import app_commands pour utiliser les commandes slash
from dotenv import load_dotenv
import yt_dlp  
from flask import Flask
from flask import Flask, jsonify, request
import requests  # Import the requests module
import threading
from datetime import datetime, time
import sqlite3

# Flask app pour garder le bot réveillé
app = Flask('')

# Connexion à la base de données
def get_db_connection():
    conn = sqlite3.connect('game.db')
    conn.row_factory = sqlite3.Row
    return conn

# Créer la table des joueurs si elle n'existe pas déjà
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            pseudo TEXT UNIQUE,
            argent INTEGER
        )
    ''')
    conn.commit()
    conn.close()

# Route pour ajouter un joueur
@app.route('/api/ajouter_joueur', methods=['POST'])
def ajouter_joueur():
    try:
        data = request.get_json()
        pseudo = data['pseudo']
        # Créer un joueur avec un solde initial de 0
        conn = get_db_connection()
        conn.execute('INSERT INTO players (pseudo, argent) VALUES (?, ?)', (pseudo, 0))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Joueur {pseudo} ajouté avec succès!"}), 200
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "Le joueur existe déjà!"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur: {str(e)}"}), 500

# Route pour ajouter de l'argent à un joueur
@app.route('/api/ajouter_argent', methods=['POST'])
def ajouter_argent():
    try:
        data = request.get_json()
        pseudo = data['pseudo']
        montant = data['montant']

        # Mettre à jour le solde du joueur
        conn = get_db_connection()
        joueur = conn.execute('SELECT * FROM players WHERE pseudo = ?', (pseudo,)).fetchone()

        if joueur:
            # Si le joueur existe, on met à jour son argent
            nouveau_solde = joueur['argent'] + montant
            conn.execute('UPDATE players SET argent = ? WHERE pseudo = ?', (nouveau_solde, pseudo))
            conn.commit()
            conn.close()
            return jsonify({"status": "success", "message": f"{montant} pièces ont été ajoutées à {pseudo}."}), 200
        else:
            conn.close()
            return jsonify({"status": "error", "message": "Joueur non trouvé!"}), 404

    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur: {str(e)}"}), 500


# Flask app pour garder le bot réveillé
app = Flask('')

@app.route('/')
def home():
    return "Bot Discord actif !"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    thread = threading.Thread(target=run)
    thread.start()

load_dotenv()

# Récupère le chemin absolu du dossier où se trouve le script Python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Crée un chemin vers le dossier sounds
sound_file = os.path.join(BASE_DIR, "sounds", "poisson.mp3", "Rick.mp3")

# Ajoutez cette ligne pour définir les options FFMPEG
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# Chemin vers le dossier des sons
SOUNDS_FOLDER = os.path.join(BASE_DIR, "sounds")

# Définition de la fonction get_sound_path
def get_sound_path(filename):
    return os.path.join(SOUNDS_FOLDER, filename)

music_queues = {}
volume_levels = {}

intents = discord.Intents.default()
intents.message_content = True  # Si vous utilisez des messages pour commander le bot

# Utilisation de BotDiscord comme instance du bot
class BotDiscord(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="/", intents=intents, application_id=os.getenv("APPLICATION_ID"))

        try:
            credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if not credentials_json:
                raise Exception("GOOGLE_APPLICATION_CREDENTIALS non défini")

            credentials_dict = json.loads(credentials_json)
            self.project_id = credentials_dict['project_id']

            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=['https://www.googleapis.com/auth/dialogflow']
            )
            self.session_client = dialogflow_v2.SessionsClient(credentials=credentials)
            print("Dialogflow initialisé avec succès")
        except Exception as e:
            print(f"Erreur d'initialisation Dialogflow: {e}")
            self.session_client = None

    async def setup_hook(self):
        await self.tree.sync()  # Synchronise les commandes slash

    async def detect_intent(self, text, session_id):
        if not self.session_client:
            return "Désolé, je ne peux pas traiter les messages pour le moment."

        session = self.session_client.session_path(self.project_id, session_id)
        text_input = dialogflow_v2.TextInput(text=text, language_code="fr")
        query_input = dialogflow_v2.QueryInput(text=text_input)

        try:
            response = self.session_client.detect_intent(
                request={"session": session, "query_input": query_input}
            )
            return response.query_result.fulfillment_text
        except Exception as e:
            print(f"Erreur Dialogflow: {e}")
            return "Désolé, une erreur s'est produite."

# Instanciation du bot
client = BotDiscord()

target_channels = [759668011950407706]

@client.event
async def on_ready():
    print("="*50)
    print(f"✅ Bot '{client.user}' connecté avec succès!")
    print(f"🔗 Connecté à {len(client.guilds)} serveurs")
    print(f"📝 Commandes slash disponibles avec /aide")
    print("="*50)
    await client.change_presence(activity=discord.Game(name="Discute avec moi! Saluez-moi !"))

#Change l'avatar du bot à 21h et 8h
async def change_avatar(path):
    if os.path.exists(path):
        with open(path, 'rb') as avatar_file:
            try:
                await client.user.edit(avatar=avatar_file.read())
                print(f"✅ Avatar changé avec succès ({path})")
            except Exception as e:
                print(f"❌ Erreur changement avatar : {e}")
    else:
        print(f"❌ Fichier introuvable : {path}")

async def avatar_scheduler():
    await client.wait_until_ready()
    while not client.is_closed():
        now = datetime.now().time()

        if now.hour == 21 and now.minute == 0:
            await change_avatar("Avatar/Sleep.png")
        elif now.hour == 8 and now.minute == 0:
            await change_avatar("Avatar/Jour.png")

        await asyncio.sleep(60)  # vérifie toutes les minutes

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Vérifie si le message est dans les salons cibles
    if target_channels and message.channel.id not in target_channels:
        return

    # Gestion des mots-clés "poisson" ou "steve"
    if any(kw in message.content.lower() for kw in ["poisson", "steve"]):
        if message.author.voice and message.author.voice.channel:
            voice_channel = message.author.voice.channel
            try:
                vc = message.guild.voice_client
                if not vc:
                    vc = await voice_channel.connect()
                elif vc.channel != voice_channel:
                    await vc.move_to(voice_channel)

                if "poisson" in message.content.lower():
                    sound_file = get_sound_path("poisson.mp3")
                    temp_avatar_file = f"avatar/Steve.jpg"
                    original_avatar_file = "avatar/Jour.png"
                else:
                    sound_file = get_sound_path("Steve.mp3")
                    temp_avatar_file = f"avatar/Jack.jpg"
                    original_avatar_file = "avatar/Jour.png"

                # Changer l’avatar pour le son joué
                if os.path.exists(temp_avatar_file):
                    with open(temp_avatar_file, "rb") as af:
                        await client.user.edit(avatar=af.read())
                else:
                    print(f"Fichier d'avatar introuvable : {temp_avatar_file}")

                vc.stop()
                vc.play(FFmpegPCMAudio(sound_file), after=lambda e: print("Lecture terminée."))

                await message.channel.send(f"🎵 Son lancé : {os.path.basename(sound_file)}")

                while vc.is_playing():
                    await asyncio.sleep(1)
                await vc.disconnect()

                # Remettre l’avatar d’origine
                if os.path.isfile(original_avatar_file):
                    with open(original_avatar_file, "rb") as af:
                        await client.user.edit(avatar=af.read())

            except Exception as e:
                await message.channel.send(f"Erreur : {e}")
        else:
            await message.channel.send("❌ Tu dois être dans un salon vocal pour que je joue le son !")
        return

    # Réaction à "ta gueule"
    if "ta gueule" in message.content.lower():
        voice_client = discord.utils.get(client.voice_clients, guild=message.guild)
        if voice_client and voice_client.is_connected():
            if voice_client.is_playing():
                voice_client.stop()
            await voice_client.disconnect()
            music_queues[message.guild.id] = []
            await message.channel.send("D'accord 😢")
        else:
            await message.channel.send("Hein ? Je disais rien moi 😶")
        return

    # 10% chance de jouer un son aléatoire
    if message.author.voice and message.author.voice.channel:
        if random.random() < 0.3:
            try:
                files = [f for f in os.listdir(SOUNDS_FOLDER) if f.endswith('.mp3')]
                if files:
                    selected_file = random.choice(files)
                    sound_path = os.path.join(SOUNDS_FOLDER, selected_file)
                    vc = message.guild.voice_client
                    if not vc:
                        vc = await message.author.voice.channel.connect()
                    elif vc.channel != message.author.voice.channel:
                        await vc.move_to(message.author.voice.channel)

                    if vc.is_playing():
                        vc.stop()

                    def after_play(e):
                        coro = vc.disconnect()
                        fut = asyncio.run_coroutine_threadsafe(coro, client.loop)
                        try:
                            fut.result()
                        except Exception as e:
                            print(f"Erreur lors de la déconnexion : {e}")

                    vc.play(FFmpegPCMAudio(sound_path), after=after_play)
                    await message.channel.send(f"🎵 Surprise musicale : `{selected_file}`")
                else:
                    await message.channel.send("📂 Aucun fichier .mp3 trouvé dans `/sounds`.")
            except Exception as e:
                await message.channel.send(f"❌ Erreur : {e}")
            return

    # Traitement par Dialogflow
    response = await client.detect_intent(message.content, str(message.author.id))
    if response:
        await message.channel.send(response)

        # Commande `!solde`
    if message.content.startswith("!solde"):
        try:
            parts = message.content.split()
            if len(parts) == 2:
                pseudo = parts[1]
            else:
                pseudo = message.author.display_name  # utilise le nom affiché de l'auteur

            response = requests.get(f'https://webslime.onrender.com/api/solde/{pseudo}')
            if response.status_code == 200:
                data = response.json()
                solde = data.get("solde", 0)
                await message.channel.send(f"💰 Le solde de **{pseudo}** est de **{solde}** pièces.")
            elif response.status_code == 404:
                await message.channel.send(f"❌ L'utilisateur **{pseudo}** n'existe pas.")
            else:
                await message.channel.send("Une erreur est survenue lors de la récupération du solde.")
        except Exception as e:
            await message.channel.send(f"❌ Erreur : {e}")

    # Nécessaire pour les slash commands
    await client.process_commands(message)
    # Commande pour ajouter un joueur
@client.command()
@commands.has_permissions(administrator=True)
async def ajouter(ctx, pseudo: str, montant: int):
    try:
        # Envoi de la requête à l'API Flask pour ajouter de l'argent
        response = requests.post('https://webslime.onrender.com/api/ajouter_argent', json={'pseudo': pseudo, 'montant': montant})

        if response.status_code == 200:
            await ctx.send(f"{montant} pièces ont été ajoutées à {pseudo}.")
        else:
            await ctx.send(f"Erreur : {response.json()['message']}")
    except Exception as e:
        await ctx.send(f"❌ Erreur : {e}")


# Commandes Slash
@client.tree.command(name="aide", description="Affiche la liste des commandes.")
async def help_command(interaction: discord.Interaction):
    await interaction.response.send_message("Voici mes commandes :\n/aide - Affiche cette aide\n/son - Joue un son")

# Lancer l'avatar_scheduler en parallèle
async def main():
    await client.start(os.getenv("DISCORD_BOT_TOKEN"))

@client.command()
@commands.has_permissions(administrator=True)
async def init_comptes(ctx):
    await ctx.send("🔄 Création des comptes d’économie...")

    for member in ctx.guild.members:
        if not member.bot:
            response = requests.post("https://ton-projet.onrender.com/api/creer_compte", json={"pseudo": member.name})
            if response.status_code == 200:
                print(f"✅ Compte créé pour {member.name}")
            else:
                print(f"❌ Erreur pour {member.name}: {response.text}")

    await ctx.send("✅ Comptes d’économie initialisés pour tous les membres.")

@client.tree.command(name="stop", description="Arrête la musique et vide la file.")
@commands.guild_only()
async def stop(interaction: discord.Interaction):
    try:
        await interaction.response.defer()

        guild_id = interaction.guild.id
        voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)

        if not voice_client or not voice_client.is_connected():
            await interaction.followup.send("❌ Je ne suis pas connecté à un salon vocal.")
            return

        if voice_client.is_playing():
            voice_client.stop()

        # Déconnexion et nettoyage
        await voice_client.disconnect()
        music_queues[guild_id] = []
        await interaction.followup.send("⏹️ Musique arrêtée et file vidée.")
    except Exception as e:
        print(f"Erreur : {e}")  # Log interne
        await interaction.followup.send("❌ Une erreur est survenue.")

@client.tree.command(name="liste", description="Affiche la liste des musiques locales disponibles dans /sounds")
async def liste(interaction: discord.Interaction):
    await interaction.response.defer()

    # Répertoire des sons locaux
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SOUNDS_FOLDER = os.path.join(BASE_DIR, "sounds")

    try:
        files = [f for f in os.listdir(SOUNDS_FOLDER) if f.endswith('.mp3')]
        if not files:
            await interaction.followup.send("📁 Aucun fichier .mp3 trouvé dans `/sounds`.")
            return

        message = "**🎵 Liste des musiques dispo :**\n"
        message += "\n".join(f"- `{file}`" for file in files)

        await interaction.followup.send(message)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur lors de la lecture du dossier : {e}")

@client.tree.command(name="joue", description="Joue une musique locale depuis le dossier /sounds")
@app_commands.describe(fichier="Nom du fichier (ex: Rick.mp3)")
async def joue(interaction: discord.Interaction, fichier: str):
    await interaction.response.defer()

    # Vérification du fichier
    file_path = os.path.join(SOUNDS_FOLDER, fichier)
    if not os.path.isfile(file_path):
        await interaction.followup.send(f"❌ Le fichier `{fichier}` n'existe pas dans `/sounds`.")
        return

    # Vérifier si l'utilisateur est dans un salon vocal
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("❌ Tu dois être connecté à un salon vocal.")
        return

    voice_channel = interaction.user.voice.channel if interaction.user.voice else None
    if not voice_channel:
        await interaction.followup.send("❌ Tu dois être connecté à un salon vocal.")
        return

    # Connexion
    voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)
    if not voice_client or not voice_client.is_connected():
        voice_client = await voice_channel.connect()
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    # Jouer le fichier
    try:
        if voice_client.is_playing():
            voice_client.stop()

        voice_client.play(
            FFmpegPCMAudio(file_path),
            after=lambda e: print(f"[DEBUG] Lecture terminée : {e}")
        )

        await interaction.followup.send(f"🎧 Lecture : `{fichier}`")

        # Attendre que la musique se termine
        while voice_client.is_playing():
            await asyncio.sleep(1)

        await voice_client.disconnect()
        print(f"[DEBUG] Déconnecté de {voice_channel.name}")

    except Exception as e:
        print(f"Erreur : {e}")  # Log interne
        await interaction.followup.send("❌ Une erreur est survenue.")

if __name__ == '__main__':
    keep_alive()
    asyncio.run(main())
init_db()
