import discord
from discord.ext import commands
import os
import json
import logging
from dotenv import load_dotenv

# Configure logging for better traceability
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')

# Load environment variables from the .env file
load_dotenv()

# Get the Discord token from environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

if not DISCORD_TOKEN:
    logging.error("Discord token is not defined. Make sure the 'DISCORD_TOKEN' environment variable is set correctly.")
    raise ValueError("Discord token is not defined.")

# Initialize bot intents
intents = discord.Intents.default()
intents.message_content = True  # Allows access to message content
intents.members = True  # Allows access to server members

# Initialize the bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Reset the threads.json file at startup
def reset_threads_file():
    try:
        if not os.path.exists('data'):
            os.makedirs('data')
            logging.info("The 'data' folder was created as it did not exist.")

        with open('data/threads.json', 'w') as f:
            json.dump({}, f)
        logging.info("The threads.json file has been reset.")
    except Exception as e:
        logging.error(f"Error resetting threads.json file: {e}")
        raise

# Asynchronous function to load cogs
async def load_cogs():
    COGS = ["cogs.openai_threads", "cogs.waitlist", "cogs.faq_updater"]
    for cog in COGS:
        try:
            logging.info(f"Attempting to load cog: {cog}")
            await bot.load_extension(cog)
            logging.info(f"The cog {cog} was successfully loaded.")
        except Exception as e:
            logging.error(f"Unable to load cog {cog}. Error: {e}")
            raise

    # Appel explicite à update_faq après chargement des cogs
    faq_updater_cog = bot.get_cog('FaqUpdater')
    if faq_updater_cog:
        await faq_updater_cog.update_faq()
        logging.info("FAQ update process triggered successfully.")

# Function to start the bot
@bot.event
async def on_ready():
    try:
        reset_threads_file()  # Reset the threads.json file at startup
        logging.info("Threads file reset successfully.")
        
        await load_cogs()  # Load cogs
        logging.info("All cogs loaded successfully.")
        
        logging.info(f"{bot.user.name} is connected and ready.")
    except Exception as e:
        logging.critical(f"Failed to start the bot: {e}")
        await bot.close()

# Run the bot
if __name__ == "__main__":
    try:
        logging.info("Starting the bot...")
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logging.critical(f"Failed to run the bot: {e}")
