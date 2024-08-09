import discord
from discord.ext import commands
import os
import json
import logging
from dotenv import load_dotenv

# Configurer les logs pour mieux suivre ce qui se passe
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Récupérer le token Discord depuis les variables d'environnement
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

if not DISCORD_TOKEN:
    logging.error("Le token Discord n'est pas défini. Assurez-vous que la variable d'environnement 'DISCORD_TOKEN' est configurée correctement.")
    raise ValueError("Le token Discord n'est pas défini.")

# Initialisation des intents du bot
intents = discord.Intents.default()
intents.message_content = True  # Permet d'accéder au contenu des messages
intents.members = True  # Permet d'accéder aux membres du serveur

# Initialisation du bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Réinitialiser le fichier threads.json au démarrage
def reset_threads_file():
    try:
        if not os.path.exists('data'):
            os.makedirs('data')
            logging.info("Le dossier 'data' a été créé car il n'existait pas.")

        with open('data/threads.json', 'w') as f:
            json.dump({}, f)
        logging.info("Le fichier threads.json a été réinitialisé.")
    except Exception as e:
        logging.error(f"Erreur lors de la réinitialisation du fichier threads.json : {e}")
        raise

# Fonction asynchrone pour charger les cogs
async def load_cogs():
    COGS = ["openai_threads", "waitlist"]  # Liste des cogs à charger
    for cog in COGS:
        try:
            await bot.load_extension(f'cogs.{cog}')
            logging.info(f"Le cog {cog} a été chargé avec succès.")
        except Exception as e:
            logging.error(f"Impossible de charger le cog {cog}. Erreur : {e}")
            raise

# Fonction pour démarrer le bot
@bot.event
async def on_ready():
    try:
        reset_threads_file()  # Réinitialiser le fichier threads.json au démarrage
        await load_cogs()  # Charger les cogs
        logging.info(f"{bot.user.name} est connecté et prêt.")
    except Exception as e:
        logging.critical(f"Échec lors du démarrage du bot : {e}")
        await bot.close()

# Lancer le bot
if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logging.critical(f"Échec lors de l'exécution du bot : {e}")
