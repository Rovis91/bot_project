import discord
from discord.ext import commands, tasks
import requests
import json
import os
import logging
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv

client = OpenAI()

class FAQUpdaterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.env_vars = self.load_env_variables()

    # Load environment variables
    def load_env_variables(self):
        load_dotenv()
        return {
            "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN"),
            "FORUM_ID": os.getenv("FORUM_ID"),
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "ASSISTANT_ID": os.getenv("ASSISTANT_ID"),
            "VECTOR_STORE_ID": os.getenv("VECTOR_STORE_ID")
        }

    # Fetch forum posts since last run
    def fetch_forum_posts(self, forum_id, last_run_time):
        logging.info("Fetching forum posts.")
        headers = {"Authorization": f"Bot {self.env_vars['DISCORD_TOKEN']}"}
        response = requests.get(f"https://discord.com/api/v9/channels/{forum_id}/messages", headers=headers)
        response.raise_for_status()
        posts = response.json()
        
        new_posts = [post for post in posts if datetime.strptime(post['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ') > last_run_time]
        logging.info(f"Found {len(new_posts)} new posts since last run.")
        return new_posts

    # Extract Q&A pairs from posts using GPT
    def extract_qa_from_posts(self, posts):
        logging.info("Extracting Q&A pairs from posts.")
        qas = []
        for post in posts:
            question = post['content']  # Assuming content is the question
            logging.info(f"Processing question: {question}")
            answer = self.gpt_generate_answer(question)  # Assume this function sends the question to GPT for an answer
            qas.append({"question": question, "answer": answer})
            logging.info(f"Generated answer: {answer}")
        logging.info(f"Extracted {len(qas)} Q&A pairs from posts.")
        return qas

    # Load existing FAQ JSON
    def load_existing_faq(self, faq_file_path):
        if os.path.exists(faq_file_path):
            logging.info(f"Loading existing FAQ from {faq_file_path}.")
            with open(faq_file_path, 'r') as f:
                return json.load(f)
        logging.info("No existing FAQ found, starting with an empty list.")
        return []

    # Append new Q&A to existing FAQ
    def append_to_faq(self, faq_data, new_qas):
        logging.info("Appending new Q&A pairs to the existing FAQ.")
        return faq_data + new_qas

    # Save updated FAQ JSON
    def save_faq_json(self, faq_file_path, updated_faq):
        logging.info(f"Saving updated FAQ to {faq_file_path}.")
        with open(faq_file_path, 'w') as f:
            json.dump(updated_faq, f, indent=4)
        logging.info("FAQ updated and saved.")

    # Create or update vector store
    def create_or_update_vector_store(self, faq_file_path, existing_files):
        try:
            logging.info("Creating or updating vector store.")
            # Upload the updated FAQ file
            faq_file_id = self.upload_file_to_openai(faq_file_path)

            # Ensure the file was uploaded correctly
            if not faq_file_id:
                raise ValueError("Failed to upload faq.json file to OpenAI.")

            # Gather all files to include in the vector store
            all_files = [faq_file_id]
            for file in existing_files:
                file_id = self.upload_file_to_openai(f"vector_store/{file}")
                if not file_id:
                    raise ValueError(f"Failed to upload {file} file to OpenAI.")
                all_files.append(file_id)

            # Create or update the vector store with the new FAQ and existing files
            new_vector_store = client.beta.vector_stores.create_and_poll(
                name='FAQ Store',
                file_ids=all_files,
                expires_after={
                    'anchor': 'last_active_at',
                    'days': 7
                }
            )

            # Link the vector store to the assistant
            client.beta.assistants.update(
                assistant_id=self.env_vars["ASSISTANT_ID"],
                tool_resources={'file_search': {'vector_store_ids': [new_vector_store.id]}}
            )
            logging.info(f"Vector store {new_vector_store.id} created and linked to assistant.")

        except Exception as e:
            logging.error(f"Failed to create or update vector store: {e}")
            self.revert_to_previous_version(faq_file_path)  # Function to revert to the previous vector store

    # Backup the existing vector store and FAQ
    def backup_and_revert(self, faq_file_path):
        try:
            backup_path = f"{faq_file_path}.bak"
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.rename(faq_file_path, backup_path)
            logging.info(f"Backup created for faq.json at {backup_path}.")
        except Exception as e:
            logging.error(f"Failed to backup faq.json: {e}")

    # Main process
    def main(self):
        faq_file_path = "vector_store/faq.json"
        existing_files = ['forma.json', 'plan.json', 'regles.json']

        logging.info("Starting main FAQ update process.")
        
        # Backup current FAQ and vector store
        self.backup_and_revert(faq_file_path)

        # Fetch new forum posts
        last_run_time = datetime.now()  # This should load from a file
        new_posts = self.fetch_forum_posts(self.env_vars["FORUM_ID"], last_run_time)

        # Extract Q&A pairs from posts
        new_qas = self.extract_qa_from_posts(new_posts)

        # Load existing FAQ
        existing_faq = self.load_existing_faq(faq_file_path)

        # Append new Q&A
        updated_faq = self.append_to_faq(existing_faq, new_qas)

        # Save updated FAQ
        self.save_faq_json(faq_file_path, updated_faq)

        # Create or update vector store
        self.create_or_update_vector_store(faq_file_path, existing_files)

        logging.info("FAQ update process completed.")

    # Upload file to OpenAI
    def upload_file_to_openai(self, file_path):
        logging.info(f"Uploading file {file_path} to OpenAI.")
        try:
            with open(file_path, 'rb') as file_data:
                response = client.beta.vector_stores.files.create_and_poll(
                    vector_store_id=self.env_vars["VECTOR_STORE_ID"],
                    file_id=file_data
                )
                file_id = response.id
                logging.info(f"Uploaded file {file_path} with file ID {file_id}.")
                return file_id
        except Exception as e:
            logging.error(f"Failed to upload file {file_path} to OpenAI: {e}")
            return None

    # Revert to the previous vector store version
    def revert_to_previous_version(self, faq_file_path):
        logging.info("Reverting to previous vector store version.")
        try:
            backup_path = f"{faq_file_path}.bak"
            if os.path.exists(backup_path):
                os.rename(backup_path, faq_file_path)
                logging.info(f"Reverted to previous version of {faq_file_path}.")
            else:
                logging.error(f"No backup file found to revert to for {faq_file_path}.")
        except Exception as e:
            logging.error(f"Failed to revert to previous version: {e}")

    # Ephemeral command for testing
    @commands.command(name="test_faq_update")
    async def test_faq_update(self, ctx):
        logging.info("Starting FAQ update via test command.")
        await ctx.send("Starting FAQ update... This may take a moment.")
        try:
            self.main()  # Run the main process manually
            await ctx.send("FAQ update completed successfully.")
        except Exception as e:
            logging.error(f"Error during FAQ update: {e}")
            await ctx.send(f"FAQ update failed: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info(f"{self.bot.user} is ready.")
        self.main()  # Run the main process when the bot starts

async def setup(bot):
    await bot.add_cog(FAQUpdaterCog(bot))
