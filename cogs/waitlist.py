"""
Waitlist Cog for Discord Bot
=============================

This module implements the `WaitlistCog` for managing a waitlist of users in a Discord bot. The bot assigns roles to users 
who are on the waitlist and sends them welcome messages. It also periodically processes the waitlist to grant access to users 
by assigning a specified role.

Main Features:
--------------
1. **Waitlist Management**:
   - Users are automatically added to a waitlist upon joining the server.
   - The waitlist is saved to and loaded from a JSON file (`waitlist.json`).

2. **Welcome Messages**:
   - Sends welcome messages to new members, prompting them to join the waitlist.

3. **Role Assignment**:
   - Periodically grants access to users from the waitlist by assigning them a specific role (e.g., "Accès Groupe Facebook").
   - Handles errors such as insufficient permissions when assigning roles.

4. **Task Scheduling**:
   - Schedules the `give_access` task to run twice a day to process the waitlist.

5. **Logging**:
   - Provides detailed logging for actions such as saving/loading the waitlist, sending messages, and assigning roles.
   - Integrates with the global logging configuration set in the main bot script.

Usage:
------
- This cog is designed to be part of a larger Discord bot, and it should be loaded during the bot's startup.
- Ensure that the necessary environment variables and permissions are properly configured for the bot.

"""

import discord
from discord.ext import commands, tasks
import datetime
import json
import logging
import os

class WaitlistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.WAITLIST_FILE = 'data/waitlist.json'
        self.waitlist = []
        self.welcomed_users = set()
        self.load_waitlist()

    def save_waitlist(self):
        try:
            with open(self.WAITLIST_FILE, 'w') as f:
                json.dump([user.id for user in self.waitlist], f)
            logging.info("Liste d'attente sauvegardée.")
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde de la liste d'attente : {e}")

    def load_waitlist(self):
        try:
            with open(self.WAITLIST_FILE, 'r') as f:
                user_ids = json.load(f)
                for user_id in user_ids:
                    user = self.bot.get_user(user_id)
                    if user:
                        self.waitlist.append(user)
                logging.info("Liste d'attente chargée.")
        except FileNotFoundError:
            with open(self.WAITLIST_FILE, 'w') as f:
                json.dump([], f)
            logging.info("Fichier waitlist.json créé.")
        except json.JSONDecodeError as e:
            logging.error(f"Erreur de décodage JSON lors du chargement de la liste d'attente : {e}")
            self.waitlist = []

    async def check_existing_members(self):
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.id not in self.welcomed_users and not any(role.name == "Accès Groupe Facebook" for role in member.roles):
                    await self.on_member_join(member)

    @commands.Cog.listener()
    async def on_ready(self):
        self.load_waitlist()
        await self.check_existing_members()
        logging.info(f'{self.bot.user} has connected to Discord!')

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.id not in self.welcomed_users:
            try:
                await member.send("Bienvenue! Cliquez sur le bouton ci-dessous pour vous inscrire à la liste d'attente.", components=[
                    discord.ui.Button(label="S'inscrire à la liste d'attente", custom_id="register_waitlist")
                ])
                self.welcomed_users.add(member.id)
                logging.info(f"Message de bienvenue envoyé à {member.name}.")
            except discord.Forbidden:
                logging.warning(f"Impossible d'envoyer un message privé à {member.name} - permissions insuffisantes.")
            except discord.HTTPException as e:
                logging.error(f"Erreur HTTP lors de l'envoi d'un message privé à {member.name} : {e}")

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type == discord.InteractionType.component and interaction.custom_id == "register_waitlist":
            user = interaction.user
            if user not in self.waitlist:
                self.waitlist.append(user)
                self.save_waitlist()  # Sauvegarde de la liste d'attente mise à jour
                await interaction.response.send_message(f"{user.mention}, vous avez été ajouté à la liste d'attente.", ephemeral=True)
                logging.info(f"{user.name} a été ajouté à la liste d'attente.")
            else:
                await interaction.response.send_message("Vous êtes déjà dans la liste d'attente.", ephemeral=True)

    @tasks.loop(hours=12)
    async def give_access(self):
        if self.waitlist:
            user = self.waitlist.pop(0)
            self.save_waitlist()  # Sauvegarde de la liste d'attente mise à jour
            guild = discord.utils.get(self.bot.guilds, id=user.guild.id)  # Assurez-vous que l'utilisateur appartient toujours à un guild
            if guild:
                role = discord.utils.get(guild.roles, name="Accès Groupe Facebook")
                if role:
                    try:
                        await user.add_roles(role)
                        await self.send_private_message(user, role)  # Envoie du message privé après l'ajout du rôle
                        logging.info(f"{user.name} a reçu le rôle 'Accès Groupe Facebook'.")
                    except discord.Forbidden:
                        await user.send("Je n'ai pas les permissions nécessaires pour vous attribuer ce rôle.")
                        logging.error(f"Permissions insuffisantes pour attribuer le rôle à {user.name}.")
                    except discord.HTTPException as e:
                        await user.send(f"Une erreur s'est produite: {e}")
                        logging.error(f"Erreur HTTP lors de l'attribution du rôle à {user.name}: {e}")
            else:
                logging.warning(f"L'utilisateur {user.name} n'appartient plus à un serveur.")

    async def send_private_message(self, member, role):
        try:
            message_content = (
                "Hello ! 👋\n\n"
                "J’ai le plaisir de t’annoncer que tu viens d’être ajouté dans le salon #groupe-reviews. ✅\n\n"
                "À l’intérieur tu y trouveras plus de 30 groupes que j’utilise personnellement afin d’avoir accès à un maximum d’articles.\n\n"
                "Je te laisse rejoindre les groupes en cliquant sur les liens 🔗\n\n"
                "À bientôt, ✌️"
            )
            await member.send(message_content)
            logging.info(f"Message privé envoyé à {member.name}")
        except discord.Forbidden:
            logging.warning(f"Impossible d'envoyer un message privé à {member.name} - permissions insuffisantes.")
        except discord.HTTPException as e:
            logging.error(f"Erreur HTTP lors de l'envoi d'un message privé à {member.name}: {e}")

    @give_access.before_loop
    async def before_give_access(self):
        await self.bot.wait_until_ready()
        now = datetime.datetime.now()
        next_run = now.replace(hour=7 if now.hour < 7 else 19, minute=0, second=0, microsecond=0)
        if now.hour >= 19:
            next_run += datetime.timedelta(days=1)
        await discord.utils.sleep_until(next_run)
        logging.info("La tâche planifiée give_access a été initialisée.")

async def setup(bot):
    await bot.add_cog(WaitlistCog(bot))
