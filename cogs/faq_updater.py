from discord.ext import commands
import os
import json
import logging
from datetime import datetime
import glob

class FaqUpdater(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
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
        else:
            logging.info("No new posts found for FAQ update.")

    async def retrieve_new_forum_posts(self, forum_channel):
        # Retrieve the ID of the last processed post
        last_post_id = self.get_last_processed_post_id()
        posts = []

        # Make sure forum_channel is not None
        if forum_channel:
            # Iterate over the list of threads
            for thread in forum_channel.threads:  # Correct usage, no parentheses
                # Filter new threads based on the last processed post ID
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
                    # Add the thread and its messages to the posts list
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
            # Assuming the first message in the thread is the question
            # and the second message is the answer
            if len(post["messages"]) >= 2:
                answer = post["messages"][0]["content"]  # The first message is the answer
                question = post["messages"][1]["content"]  # The second message is the question
                qas.append({"question": question, "answer": answer})
        return qas


    def backup_and_update_faq(self, new_qas):
        faq_file_path = "vector_store/faq.json"
        backup_dir = "vector_store/"
        backup_path = f"{faq_file_path}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"

        try:
            # Backup the old FAQ file
            if os.path.exists(faq_file_path):
                os.rename(faq_file_path, backup_path)
                logging.info(f"Backup created at {backup_path}")

                # Manage backups: keep only the 5 most recent ones
                self.manage_backups(backup_dir, "faq.json.*.bak", 5)

        except Exception as e:
            logging.error(f"Failed to create backup: {e}")
            return

        # Update the FAQ file with new data
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
        # Find all backup files matching the pattern
        backup_files = sorted(glob.glob(os.path.join(directory, pattern)))

        # If there are more backups than the limit, delete the oldest ones
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
            logging.error(f"Failed to load last processed post ID: {e}")
            return None

    def update_last_processed_post(self, posts):
        # Sauvegarder l'ID du dernier post traité
        last_post_id = max(post["thread_id"] for post in posts)
        try:
            with open(self.last_processed_file, 'w') as f:
                json.dump({"last_post_id": last_post_id}, f)
            logging.info(f"Last processed post ID updated to {last_post_id}.")
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Failed to update last processed post ID: {e}")

async def setup(bot):
    await bot.add_cog(FaqUpdater(bot))
