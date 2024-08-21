"""
FAQ Updater Cog for Discord Bot
================================

This module implements the `FaqUpdater` cog for a Discord bot, which handles the automatic extraction, backup, and update of a frequently asked questions (FAQ) JSON file from a Discord forum channel. 

Main Features:
--------------
1. **FAQ Extraction**:
   - Retrieves posts from a specified forum channel in Discord and extracts question-answer pairs from threads.
   - Updates a local `faq.json` file with new entries while managing backups.

2. **Backup Management**:
   - Automatically creates backups of the FAQ file with timestamps.
   - Retains the latest 5 backups and deletes older ones to manage storage.

3. **OpenAI Vector Store Integration**:
   - Uploads files from the `vector_store/` directory to OpenAI's API.
   - Creates a new vector store and links it to the bot's assistant, replacing the old vector store.

4. **Logging**:
   - Detailed logging throughout the cog, including file operations, API interactions, and error handling.
   - Integrates with the global logging configuration set in the main bot script.

5. **Reset Threads**:
   - Resets the `threads.json` file after successfully updating the vector store and linking it to the assistant.

Usage:
------
- This cog is designed to be part of a larger Discord bot, and it should be loaded during the bot's startup.
- Ensure that the necessary environment variables (`FORUM_ID`, `ASSISTANT_ID`, etc.) are properly configured.
"""

from discord.ext import commands
import os
import json
import logging
from datetime import datetime
import glob
from openai import OpenAI
from bot import reset_threads_file

class FaqUpdater(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = OpenAI()
        self.faq_file_path = "vector_store/faq.json"
        self.last_processed_file = "data/last_processed_post.json"

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("Bot is ready, starting FAQ update process.")
        await self.update_faq()

    async def update_faq(self):
        forum_channel = self.bot.get_channel(int(os.getenv('FORUM_ID')))
        if forum_channel is None:
            logging.error("Forum channel not found. Please check the FORUM_ID.")
            return

        new_posts = await self.retrieve_new_forum_posts(forum_channel)

        if new_posts:
            new_qas = self.extract_questions_and_answers(new_posts)
            self.backup_and_update_faq(new_qas)
            self.update_last_processed_post(new_posts)
            logging.info(f"Added {len(new_qas)} new entries to the FAQ.")

            # Update vector store and assistant after FAQ update
            await self.update_vector_store_and_assistant()

        else:
            logging.info("No new posts found for FAQ update.")

    async def retrieve_new_forum_posts(self, forum_channel):
        last_post_id = self.get_last_processed_post_id()
        posts = []

        if forum_channel:
            for thread in forum_channel.threads:
                if last_post_id is None or thread.id > last_post_id:
                    all_messages = []
                    async for message in thread.history(limit=100):
                        all_messages.append({
                            "id": message.id,
                            "content": message.content,
                            "author": message.author.name,
                            "timestamp": str(message.created_at),
                            "thread_name": thread.name
                        })
                    posts.append({
                        "thread_id": thread.id,
                        "thread_name": thread.name,
                        "messages": all_messages
                    })

        logging.info(f"Found {len(posts)} new posts.")
        return posts

    def extract_questions_and_answers(self, posts):
        qas = []
        for post in posts:
            if len(post["messages"]) >= 2:
                answer = post["messages"][0]["content"]
                question = post["messages"][1]["content"]
                qas.append({"question": question, "answer": answer})
        return qas

    def backup_and_update_faq(self, new_qas):
        faq_file_path = "vector_store/faq.json"
        backup_dir = "vector_store/"
        backup_path = f"{faq_file_path}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"

        try:
            if os.path.exists(faq_file_path):
                os.rename(faq_file_path, backup_path)
                logging.info(f"Backup created at {backup_path}")
                self.manage_backups(backup_dir, "faq.json.*.bak", 5)

        except Exception as e:
            logging.error(f"Failed to create backup: {e}")
            return

        try:
            faq_data = {"FAQ": []}
            if os.path.exists(backup_path):
                with open(backup_path, 'r') as f:
                    faq_data = json.load(f)

            faq_data["FAQ"].extend(new_qas)

            with open(faq_file_path, 'w') as f:
                json.dump(faq_data, f, indent=4, ensure_ascii=False)

            logging.info("FAQ file updated successfully.")
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Failed to update faq.json: {e}")

    def manage_backups(self, directory, pattern, limit):
        backup_files = sorted(glob.glob(os.path.join(directory, pattern)))

        if len(backup_files) > limit:
            for old_backup in backup_files[:-limit]:
                try:
                    os.remove(old_backup)
                    logging.info(f"Deleted old backup: {old_backup}")
                except Exception as e:
                    logging.error(f"Failed to delete old backup {old_backup}: {e}")

    def get_last_processed_post_id(self):
        try:
            with open(self.last_processed_file, 'r') as f:
                data = json.load(f)
                return data.get("last_post_id")
        except (json.JSONDecodeError, IOError) as e:
            logging.info(f"Failed to load last processed post ID: {e}")
            return None

    def update_last_processed_post(self, posts):
        last_post_id = max(post["thread_id"] for post in posts)
        try:
            with open(self.last_processed_file, 'w') as f:
                json.dump({"last_post_id": last_post_id}, f)
            logging.info(f"Last processed post ID updated to {last_post_id}.")
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Failed to update last processed post ID: {e}")

    async def update_vector_store_and_assistant(self):
        assistant_id = os.getenv("ASSISTANT_ID")
        vector_store_dir = "vector_store/"
        old_vector_store_id = await self.get_most_recent_vector_store()

        try:
            # Step 1: Upload files
            file_ids = await self.upload_files_from_directory(vector_store_dir)

            if not file_ids:
                logging.error("No files uploaded. Aborting vector store creation.")
                return

            # Step 2: Create a new vector store
            new_vector_store_id = self.create_new_vector_store(file_ids)

            # Step 3: Delete the old vector store
            if old_vector_store_id:
                self.delete_old_vector_store(old_vector_store_id)

            # Step 4: Link the new vector store to the assistant
            self.link_vector_store_to_assistant(assistant_id, new_vector_store_id)

            # Step 5: Reset threads
            reset_threads_file()

            logging.info("Vector store updated and assistant linked successfully.")

        except Exception as e:
            logging.error(f"An error occurred during the update process: {str(e)}")

    async def get_most_recent_vector_store(self):
        try:
            vector_stores = self.client.beta.vector_stores.list(limit=1, order="desc")
            for store in vector_stores:
                logging.info(f"Most recent vector store ID: {store.id}")
                return store.id
            return None
        except Exception as e:
            logging.error(f"Failed to retrieve vector stores: {str(e)}")
            return None

    async def upload_files_from_directory(self, directory):
        file_ids = []
        try:
            for filename in os.listdir(directory):
                if filename.endswith(".bak"):
                    logging.info(f"Skipping backup file: {filename}")
                    continue

                filepath = os.path.join(directory, filename)
                with open(filepath, 'rb') as file:
                    uploaded_file = self.client.files.create(
                        file=file,
                        purpose='assistants'
                    )
                    file_ids.append(uploaded_file.id)
                    logging.info(f"Uploaded file: {filename} with ID: {uploaded_file.id}")
        except Exception as e:
            logging.error(f"Failed to upload files: {str(e)}")
        return file_ids

    def create_new_vector_store(self, file_ids):
        try:
            vector_store = self.client.beta.vector_stores.create(
                file_ids=file_ids,
                name="New Vector Store"
            )
            logging.info(f"Created new vector store with ID: {vector_store.id}")
            return vector_store.id
        except Exception as e:
            logging.error(f"Failed to create vector store: {str(e)}")
            return None

    def delete_old_vector_store(self, vector_store_id):
        try:
            self.client.beta.vector_stores.delete(vector_store_id=vector_store_id)
            logging.info(f"Deleted old vector store with ID: {vector_store_id}")
        except Exception as e:
            logging.error(f"Failed to delete old vector store: {str(e)}")

    def link_vector_store_to_assistant(self, assistant_id, vector_store_id):
        if not vector_store_id:
            logging.error("Cannot link vector store: vector_store_id is null.")
            return

        try:
            updated_assistant = self.client.beta.assistants.update(
                assistant_id=assistant_id,
                tool_resources={
                    "file_search": {
                        "vector_store_ids": [vector_store_id]
                    }
                }
            )
            logging.info(f"Linked new vector store to assistant: {updated_assistant.id}")
        except Exception as e:
            logging.error(f"Failed to link vector store to assistant: {str(e)}")

async def setup(bot):
    await bot.add_cog(FaqUpdater(bot))
