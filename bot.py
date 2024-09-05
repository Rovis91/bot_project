import discord
from discord.ext import commands, tasks
import os
import json
import logging
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
import signal
import asyncio

# Configure logging to capture INFO level and higher messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(threadName)s:%(message)s')

# Create a rotating file handler to save logs to a file
log_file = "bot_logs.log"
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)  # 5MB per file, with 5 backups
file_handler.setLevel(logging.INFO)

# Create a formatter and set it for the file handler
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
file_handler.setFormatter(formatter)

# Add the file handler to the root logger
logging.getLogger().addHandler(file_handler)

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
        os.makedirs('data', exist_ok=True)  # Create directory safely
        with open('data/threads.json', 'w') as f:
            json.dump({}, f)
        logging.info("The threads.json file has been reset.")
    except Exception as e:
        logging.error(f"Error resetting threads.json file: {e}")
        raise

async def load_cogs():
    COGS = ["cogs.openai_threads", "cogs.faq_updater"]
    for cog in COGS:
        try:
            logging.info(f"Attempting to load cog: {cog}")
            await bot.load_extension(cog)
            logging.info(f"The cog {cog} was successfully loaded.")
        except Exception as e:
            logging.error(f"Unable to load cog {cog}. Error: {e}")
            # Log the error and skip to the next cog

    # Explicitly call update_faq after loading the cogs
    faq_updater_cog = bot.get_cog('FaqUpdater')
    if faq_updater_cog:
        await faq_updater_cog.update_faq()
        logging.info("FAQ update process triggered successfully.")

# Heartbeat log to check if the bot is running
@tasks.loop(hours=1)
async def log_heartbeat():
    logging.info(f"Bot {bot.user.name} is still running and connected.")

# Function to start the bot
@bot.event
async def on_ready():
    try:
        reset_threads_file()  # Reset the threads.json file at startup
        logging.info("Threads file reset successfully.")
        
        await load_cogs()  # Load cogs
        logging.info("All cogs loaded successfully.")
        
        logging.info(f"{bot.user.name} is connected and ready.")
        
        # Start the heartbeat task
        log_heartbeat.start()
    except Exception as e:
        logging.critical(f"Failed to start the bot: {e}")
        await bot.close()

# Handle bot shutdown signal
def signal_handler(signal, frame):
    logging.info("Received shutdown signal, closing bot.")
    asyncio.get_event_loop().stop()

signal.signal(signal.SIGINT, signal_handler)

# Run the bot
if __name__ == "__main__":
    try:
        logging.info("Starting the bot...")
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logging.critical(f"Failed to run the bot: {e}")
