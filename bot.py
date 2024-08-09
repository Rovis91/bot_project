import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import json

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Récupérer le token Discord depuis les variables d'environnement
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
ROLE_ID = os.getenv('ROLE_ID')

if not DISCORD_TOKEN:
    raise ValueError("Le token Discord n'est pas défini. Assurez-vous que la variable d'environnement 'DISCORD_TOKEN' est configurée correctement.")

# Initialisation des intents du bot
intents = discord.Intents.default()
intents.message_content = True  # Permet d'accéder au contenu des messages
intents.members = True  # Permet d'accéder aux membres du serveur

# Initialisation du bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Réinitialiser le fichier threads.json au démarrage
def reset_threads_file():
    with open('data/threads.json', 'w') as f:
        json.dump({}, f)
    print("Le fichier threads.json a été réinitialisé.")

# Fonction asynchrone pour charger les cogs
async def load_cogs():
    COGS = ["openai_threads", "waitlist"]  # Mise à jour pour charger les bons cogs
    for cog in COGS:
        try:
            await bot.load_extension(f'cogs.{cog}')
            print(f"Le cog {cog} a été chargé avec succès.")
        except Exception as e:
            print(f"Impossible de charger le cog {cog}. Erreur : {e}")

async def perform_role_check():
    print("Début de la fonction perform_role_check")
    role_id = int(ROLE_ID)
    guild = bot.guilds[0]  # Supposons que le bot soit dans un seul serveur
    print(f"Récupération du serveur: {guild.name}")
    
    role = guild.get_role(role_id)
    if role is None:
        print(f"Le rôle avec l'ID {ROLE_ID} n'a pas été trouvé.")
        return

    bot_member = guild.me
    if role.position >= bot_member.top_role.position:
        print("Le bot n'a pas les permissions nécessaires pour gérer ce rôle en raison de la hiérarchie des rôles.")
        print(f"Assurez-vous que le rôle du bot ({bot_member.top_role.name}) est supérieur au rôle à attribuer ({role.name}).")
        return

    members = guild.members
    print(f"Nombre total de membres: {len(members)}")

    members_without_role = [member for member in members if role_id not in [r.id for r in member.roles]]
    print(f"Nombre de membres sans le rôle: {len(members_without_role)}")

    members_sorted = sorted(members_without_role, key=lambda m: m.joined_at)
    print("Membres triés par date d'entrée")

    members_to_grant_role = members_sorted[:2]
    for member in members_to_grant_role:
        try:
            await member.add_roles(role)
            print(f"Rôle ajouté à {member.name}")
        except discord.errors.Forbidden:
            print(f"Permission refusée lors de l'ajout du rôle à {member.name}")

    print("Rôle ajouté aux membres sélectionnés")

@tasks.loop(hours=24)
async def check_and_grant_role():
    await bot.wait_until_ready()
    await perform_role_check()

# Démarrage du bot
@bot.event
async def on_ready():
    reset_threads_file()  # Réinitialiser le fichier threads.json au démarrage
    await load_cogs()
    print(f"{bot.user.name} est connecté et prêt.")
    check_and_grant_role.start()  # Lancer la tâche planifiée

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
