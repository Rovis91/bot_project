"""
Waitlist Cog for Discord Bot
=============================

This module implements the `WaitlistCog` for managing a waitlist of users in a Discord bot. The bot assigns roles to users 
on the waitlist and sends them welcome messages. It processes the waitlist during bot startup, assigning a specified role.

Main Features:
--------------
1. **Waitlist Management**:
   - Users are automatically added to a waitlist upon joining the server.
   - The waitlist is saved to and loaded from a JSON file (`waitlist.json`).

2. **Role Assignment**:
   - Assigns roles to users from the waitlist when the bot starts.

3. **Logging**:
   - Provides detailed logging for actions such as saving/loading the waitlist, assigning roles, and sending messages.
"""

import discord
from discord.ext import commands
import json
import logging
import os

class WaitlistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.WAITLIST_FILE = 'data/waitlist.json'
        self.waitlist = []
        self.welcomed_users = set()

        # Load the waitlist from the JSON file at startup
        self.load_waitlist()

    def save_waitlist(self):
        """Save the current waitlist to a JSON file."""
        try:
            with open(self.WAITLIST_FILE, 'w') as f:
                json.dump(self.waitlist, f)
            logging.info("Waitlist saved successfully.")
        except Exception as e:
            logging.error(f"Error saving waitlist: {e}")

    def load_waitlist(self):
        """Load the waitlist from a JSON file."""
        try:
            if os.path.exists(self.WAITLIST_FILE):
                with open(self.WAITLIST_FILE, 'r') as f:
                    self.waitlist = json.load(f)
                logging.info("Waitlist loaded successfully.")
            else:
                # Create the file if it doesn't exist
                with open(self.WAITLIST_FILE, 'w') as f:
                    json.dump([], f)
                logging.info("Waitlist file created.")
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error while loading waitlist: {e}")
            self.waitlist = []

    async def process_waitlist(self):
        """Process the waitlist and assign roles to users when the bot starts."""
        await self.check_existing_members()
        await self.assign_roles_to_waitlist()

    async def check_existing_members(self):
        """Check existing members and update the waitlist and roles."""
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.id not in self.welcomed_users and not any(role.name == "Accès Groupe Facebook" for role in member.roles):
                    await self.on_member_join(member)
        logging.info("Checked existing members and updated the waitlist.")

    async def assign_roles_to_waitlist(self):
        """Assign roles to users on the waitlist when the bot starts."""
        for guild in self.bot.guilds:
            role = discord.utils.get(guild.roles, name="Accès Groupe Facebook")
            if not role:
                logging.error("Role 'Accès Groupe Facebook' not found in the server.")
                continue

            for user_id in self.waitlist:
                member = guild.get_member(user_id)
                if member and role not in member.roles:
                    try:
                        await member.add_roles(role)
                        await self.send_private_message(member)
                        logging.info(f"Assigned role to {member.name}.")
                    except discord.Forbidden:
                        logging.error(f"Permission denied: cannot assign role to {member.name}.")
                    except discord.HTTPException as e:
                        logging.error(f"HTTP error while assigning role to {member.name}: {e}")

    async def send_private_message(self, member):
        """Send a private message to the user after assigning the role."""
        try:
            message_content = (
                "Hello ! 👋\n\n"
                "J’ai le plaisir de t’annoncer que tu viens d’être ajouté dans le salon #groupe-reviews. ✅\n\n"
                "À l’intérieur tu y trouveras plus de 30 groupes que j’utilise personnellement afin d’avoir accès à un maximum d’articles.\n\n"
                "Je te laisse rejoindre les groupes en cliquant sur les liens 🔗\n\n"
                "À bientôt, ✌️"
            )
            await member.send(message_content)
            logging.info(f"Private message sent to {member.name}.")
        except discord.Forbidden:
            logging.warning(f"Cannot send private message to {member.name} - permissions insufficient.")
        except discord.HTTPException as e:
            logging.error(f"HTTP error while sending private message to {member.name}: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener for when the bot is ready."""
        logging.info(f'{self.bot.user} has connected to Discord!')

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Event listener for when a new member joins."""
        if member.id not in self.waitlist:
            self.waitlist.append(member.id)
            self.save_waitlist()
            logging.info(f"Added {member.name} to the waitlist.")
            await self.assign_roles_to_waitlist()

async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(WaitlistCog(bot))
