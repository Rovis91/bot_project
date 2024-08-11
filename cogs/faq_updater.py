import os
import json
import logging
from datetime import datetime
import discord
from discord.ext import commands
import asyncio

class FAQUpdater(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def initialize_setup(self):
        # Ensure necessary directories and files exist
        if not os.path.exists('data'):
            os.makedirs('data')

        last_processed_file = 'data/last_processed_post.json'
        if not os.path.exists(last_processed_file):
            with open(last_processed_file, 'w') as f:
                json.dump({"last_post_id": None}, f)

        # Load environment variables from .env file
        DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
        FORUM_ID = os.getenv('FORUM_ID')

        # Basic logging setup
        logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')

        # Ensure all required environment variables are present
        if not DISCORD_TOKEN or not FORUM_ID:
            logging.critical("Missing one or more necessary environment variables. Exiting.")
            exit(1)

        return DISCORD_TOKEN, FORUM_ID

    async def retrieve_new_forum_posts(self, forum_id):
        last_processed_file = 'data/last_processed_post.json'

        try:
            with open(last_processed_file, 'r') as f:
                data = json.load(f)
                last_post_id = data.get("last_post_id")
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Failed to load last processed post ID: {str(e)}")
            last_post_id = None

        logging.info(f"Last processed post ID: {last_post_id}")

        posts = await self.fetch_discord_posts(forum_id)

        # Filter new posts based on the last processed post ID
        new_posts = [post for post in posts if last_post_id is None or post[-1]['id'] > last_post_id]

        logging.info(f"Found {len(new_posts)} new posts.")
        return new_posts

    async def fetch_thread_messages(self, thread):
        logging.info(f"Fetching messages from thread: {thread.name}")
        all_messages = []
        async for message in thread.history(limit=100):
            all_messages.append({
                "id": message.id,
                "content": message.content,
                "author": message.author.name,
                "timestamp": str(message.created_at),
                "thread_name": thread.name
            })

        return all_messages

    async def fetch_discord_posts(self, forum_id):
        channel = self.bot.get_channel(int(forum_id))

        if channel is None:
            logging.error(f"Channel with ID {forum_id} not found.")
            return []

        if isinstance(channel, discord.ForumChannel):
            all_threads = await asyncio.gather(*[self.fetch_thread_messages(thread) for thread in channel.threads])

            logging.info(f"Total threads processed: {len(all_threads)}")
            return all_threads
        else:
            logging.error(f"Channel with ID {forum_id} is not a forum channel.")
            return []

    def process_new_posts(self, threads_content):
        qas = []
        for thread in threads_content:
            if len(thread) >= 2:
                answer = thread[0]["content"]
                question = thread[1]["content"]
                qas.append({"question": question, "answer": answer})

        return qas

    def backup_and_update_faq(self, new_qas):
        faq_file_path = "vector_store/faq.json"
        backup_path = f"{faq_file_path}.{datetime.now().strftime('%Y%m%d')}.bak"

        # Handle the case where the backup file already exists
        if os.path.exists(backup_path):
            logging.warning(f"Backup file {backup_path} already exists. Creating a new backup.")
            backup_path = f"{faq_file_path}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"

        # Backup the current FAQ file
        try:
            if os.path.exists(faq_file_path):
                os.rename(faq_file_path, backup_path)
                logging.info(f"Backup created at {backup_path}")
        except Exception as e:
            logging.error(f"Failed to create backup: {str(e)}")

        # Update the FAQ file with new Q&A pairs
        try:
            with open(faq_file_path, 'w') as f:
                if os.path.exists(backup_path):
                    with open(backup_path, 'r') as backup_file:
                        faq_data = json.load(backup_file)
                else:
                    faq_data = {"FAQ": []}

                faq_data["FAQ"].extend(new_qas)
                json.dump(faq_data, f, indent=4, ensure_ascii=False)
            logging.info(f"faq.json updated with new entries.")
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Failed to update faq.json: {str(e)}")

    async def run_faq_retriever(self):
        DISCORD_TOKEN, FORUM_ID = self.initialize_setup()

        new_posts = await self.retrieve_new_forum_posts(FORUM_ID)
        if not new_posts:
            logging.info("No new posts to process.")
            return

        # Process the posts to generate Q&A
        new_qas = self.process_new_posts(new_posts)
        if new_qas:
            self.backup_and_update_faq(new_qas)
        else:
            logging.info("No valid Q&A pairs generated. No updates made.")

        last_post_id = new_posts[-1][-1]['id'] if new_posts else None
        if last_post_id:
            try:
                with open('data/last_processed_post.json', 'w') as f:
                    json.dump({"last_post_id": last_post_id}, f)
                logging.info(f"Updated last processed post ID to {last_post_id}")
            except IOError as e:
                logging.error(f"Failed to update last processed post ID: {str(e)}")


async def setup(bot):
    cog = FAQUpdater(bot)
    await cog.run_faq_retriever()  # Run the FAQ retriever on startup
    await bot.add_cog(cog)
