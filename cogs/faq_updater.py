"""
FAQ Updater Cog for Discord Bot
================================

This module implements the `FaqUpdater` cog for a Discord bot, which handles the automatic extraction, backup, and update of a frequently asked questions (FAQ) JSON file from two Discord forum channels.

Main Features:
--------------
1. **FAQ Extraction**:
   - Retrieves posts from two specified forum channels in Discord and extracts question-answer pairs from threads.
   - Updates a local `faq.json` file with new entries while managing backups.

2. **Backup Management**:
   - Automatically creates backups of the FAQ file with timestamps.
   - Retains the latest 5 backups and deletes older ones to manage storage.

3. **OpenAI Vector Store Integration**:
   - Uploads files from the `vector_store/` directory to OpenAI's API.
   - Creates a new vector store and links it to the bot's assistant, replacing the old vector store.
   - Deletes all OpenAI files with the `assistants` purpose after successfully deleting the old vector store.

4. **Logging**:
   - Detailed logging throughout the cog, including file operations, API interactions, and error handling.
   - Integrates with the global logging configuration set in the main bot script.

5. **Reset Threads**:
   - Resets the `threads.json` file after successfully updating the vector store and linking it to the assistant.

6. **Multi-channel Support**:
   - The cog now supports extracting FAQs from two separate forum channels specified via environment variables (`FORUM_ID_1` and `FORUM_ID_2`).

Usage:
------
- This cog is designed to be part of a larger Discord bot, and it should be loaded during the bot's startup.
- Ensure that the necessary environment variables (`FORUM_ID_1`, `FORUM_ID_2`, `ASSISTANT_ID`, etc.) are properly configured.
"""
from discord.ext import commands
import re
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
        self.newly_uploaded_file_ids = []  

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("Bot is ready, starting FAQ update process.")
        try:
            await self.update_faq()
        except Exception as e:
            logging.error(f"An error occurred during the FAQ update process: {str(e)}")

    async def update_faq(self):
        forum_ids = [os.getenv('FORUM_ID_1'), os.getenv('FORUM_ID_2')]
        new_posts = []

        last_post_ids = self.get_last_processed_post_id()

        for forum_id in forum_ids:
            if forum_id is None:
                logging.error(f"Forum ID not found in environment variables. Please check your .env file.")
                continue

            forum_channel = self.bot.get_channel(int(forum_id))
            if forum_channel is None:
                logging.error(f"Forum channel {forum_id} not found. Please check the ID.")
                continue

            channel_posts = await self.retrieve_new_forum_posts(forum_channel, last_post_ids.get(str(forum_id)))
            new_posts.extend(channel_posts)

        if new_posts:
            new_qas = self.extract_questions_and_answers(new_posts)
            self.backup_and_update_faq(new_qas)
            self.update_last_processed_post(new_posts)
            logging.info(f"Added {len(new_qas)} new entries to the FAQ.")

            # Update vector store and assistant after FAQ update
            await self.update_vector_store_and_assistant()

        else:
            logging.info("No new posts found for FAQ update.")

    async def retrieve_new_forum_posts(self, forum_channel, last_post_id):
        logging.info(f"Last processed post ID for channel {forum_channel.id}: {last_post_id}") 
        posts = []

        if forum_channel:
            for thread in forum_channel.threads:
                if last_post_id is None or thread.id > int(last_post_id):
                    logging.info(f"Processing thread {thread}")
                    async for message in thread.history(limit=1):  # Only need the first message
                        posts.append({
                            "channel_id": str(forum_channel.id),
                            "id": thread.id,
                            "thread_name": self.clean_text(thread.name),
                            "message_content": self.clean_text(message.content),
                            "author": self.clean_text(message.author.name),
                            "timestamp": str(message.created_at)
                        })

        logging.info(f"Found {len(posts)} new posts in channel {forum_channel.id}.")
        return posts
    
    def extract_questions_and_answers(self, posts):
        qas = []
        for post in posts:
            question = self.clean_text(post["thread_name"])  # Clean the question
            answer = self.clean_text(post["message_content"])  # Clean the answer

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

            # Create a dictionary with channel IDs as keys and their last processed post IDs as values
            channel_ids = [os.getenv('FORUM_ID_1'), os.getenv('FORUM_ID_2')]
            forum_ids = {str(channel_id): data.get(str(channel_id)) for channel_id in channel_ids if channel_id}

            return forum_ids
        except (json.JSONDecodeError, IOError) as e:
            logging.info(f"Failed to load last processed post IDs: {e}")
            return {str(channel_id): None for channel_id in [os.getenv('FORUM_ID_1'), os.getenv('FORUM_ID_2')] if channel_id}

    def update_last_processed_post(self, posts):
            """
            Updates the JSON file with the IDs of the last processed posts for each forum.
            
            Args:
                posts (list): A list of post dictionaries containing the channel_id and id.
            """
            last_processed_posts = {}

            # Get forum IDs from environment variables
            forum_ids = [os.getenv('FORUM_ID_1'), os.getenv('FORUM_ID_2')]

            for post in posts:
                channel_id = str(post["channel_id"])
                if channel_id in forum_ids:
                    if channel_id not in last_processed_posts or post["id"] > last_processed_posts[channel_id]:
                        last_processed_posts[channel_id] = post["id"]
            try:
                # Load existing data
                try:
                    with open(self.last_processed_file, 'r') as f:
                        existing_data = json.load(f)
                except (json.JSONDecodeError, IOError):
                    existing_data = {}

                # Update existing data with new information
                existing_data.update(last_processed_posts)

                # Write updated data back to file
                with open(self.last_processed_file, 'w') as f:
                    json.dump(existing_data, f, indent=4)
                logging.info("Last processed post IDs updated successfully.")
            except IOError as e:
                logging.error(f"Failed to update last processed post IDs: {e}")


    async def update_vector_store_and_assistant(self):
        assistant_id = os.getenv("ASSISTANT_ID")
        vector_store_dir = "vector_store/"
        old_vector_store_id = await self.get_most_recent_vector_store()

        try:
            # Step 1: Upload files
            self.newly_uploaded_file_ids = await self.upload_files_from_directory(vector_store_dir)

            if not self.newly_uploaded_file_ids:
                logging.error("No files uploaded. Aborting vector store creation.")
                return

            # Step 2: Delete the old vector store
            if old_vector_store_id:
                self.delete_old_vector_store(old_vector_store_id)

            # Step 3: Create a new vector store
            new_vector_store_id = self.create_new_vector_store(self.newly_uploaded_file_ids)

            if not new_vector_store_id:
                logging.error("Failed to create new vector store. Aborting process.")
                return

            # Step 4: Link the new vector store to the assistant
            self.link_vector_store_to_assistant(assistant_id, new_vector_store_id)

            # Step 5: Delete old files only after successful vector store creation
            await self.delete_old_files()

            # Step 6: Reset threads only if vector store update is successful
            reset_threads_file()

            logging.info("Vector store updated and assistant linked successfully.")

        except Exception as e:
            logging.error(f"An error occurred during the update process: {str(e)}")

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
        
    async def delete_old_files(self):
        try:
            response = self.client.files.list(purpose="assistants")
            for file in response.data:
                if file.id not in self.newly_uploaded_file_ids:  # Only delete files that weren't just uploaded
                    self.client.files.delete(file.id)
                    logging.info(f"Deleted old file with ID: {file.id}")
        except Exception as e:
            logging.error(f"Failed to delete old files: {str(e)}")

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


    def create_new_vector_store(self, file_ids):
        try:
            vector_store = self.client.beta.vector_stores.create(
                file_ids=file_ids,
                name=f"New Vector Store - {datetime.now().strftime('%m-%d')}"
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
    
    def clean_text(self, text):
        # Remove non-ASCII characters
        text = re.sub(r'[^\x00-\x7F]+', '', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Remove Discord mentions
        text = re.sub(r'<@!?\d+>', '', text)
        # Remove Discord channel mentions
        text = re.sub(r'<#\d+>', '', text)
        return text

async def setup(bot):
    await bot.add_cog(FaqUpdater(bot))
