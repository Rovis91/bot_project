import discord
from discord.ext import commands
import requests
import json
import os
import re
import asyncio
import logging

class OpenAIThreadsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        self.OPENAI_ORG_ID = os.getenv('OPENAI_ORG_ID')
        self.ASSISTANT_ID = os.getenv('ASSISTANT_ID')
        self.threads = self.load_threads()

    def load_threads(self):
        if os.path.exists('data/threads.json'):
            try:
                with open('data/threads.json', 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logging.error(f"Erreur lors du chargement de threads.json : {e}")
                return {}
        return {}

    def save_threads(self):
        try:
            with open('data/threads.json', 'w') as f:
                json.dump(self.threads, f)
            logging.info("Les threads ont été sauvegardés dans threads.json.")
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde des threads : {e}")

    def create_thread(self, channel_id, user_message):
        data = {
            "messages": [
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        }
        try:
            response = requests.post(
                'https://api.openai.com/v1/threads',
                headers={
                    'Authorization': f'Bearer {self.OPENAI_API_KEY}',
                    'OpenAI-Beta': 'assistants=v2',
                    'OpenAI-Organization': self.OPENAI_ORG_ID
                },
                json=data
            )
            response.raise_for_status()

            thread_data = response.json()
            self.threads[channel_id] = thread_data['id']
            self.save_threads()
            return thread_data

        except requests.exceptions.RequestException as e:
            logging.error(f"Erreur lors de la création du thread : {e}")
            return response.json()

    def get_latest_assistant_message(self, thread_id, run_id):
        try:
            messages_response = requests.get(
                f'https://api.openai.com/v1/threads/{thread_id}/messages',
                headers={
                    'Authorization': f'Bearer {self.OPENAI_API_KEY}',
                    'OpenAI-Beta': 'assistants=v2',
                    'OpenAI-Organization': self.OPENAI_ORG_ID
                },
                params={
                    'order': 'desc',
                    'limit': 1,
                    'run_id': run_id
                }
            )
            messages_response.raise_for_status()
            messages = messages_response.json()

            if 'data' not in messages:
                logging.error(f"Erreur: la clé 'data' est manquante dans la réponse de l'API. Réponse complète: {messages}")
                return None

            for msg in messages['data']:
                if msg['role'] == 'assistant':
                    if isinstance(msg['content'], list):
                        text_content = ""
                        for content_item in msg['content']:
                            if content_item['type'] == 'text':
                                text_content += content_item['text']['value'] + "\n"
                        return text_content.strip()
                    else:
                        return msg['content']
            return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Erreur lors de la récupération des messages : {e}")
            return None

    def split_message(self, message, max_length=2000):
        parts = []
        while len(message) > max_length:
            split_pos = message.rfind('\n', 0, max_length)
            if split_pos == -1:
                split_pos = max_length
            parts.append(message[:split_pos])
            message = message[split_pos:].strip()
        parts.append(message)
        return parts

    @commands.command(name='q')
    async def ask_question(self, ctx, *, question):
        channel_id = str(ctx.channel.id)

        if channel_id not in self.threads:
            thread_response = self.create_thread(channel_id, question)
            logging.info(f"Thread creation response: {thread_response}")

            if 'id' in thread_response:
                self.threads[channel_id] = thread_response['id']
                self.save_threads()
            else:
                error_message = thread_response.get('error', {}).get('message', 'Unknown error')
                logging.error(f"Erreur lors de la création du thread: {error_message}")
                await ctx.reply(f"Erreur lors de la création du thread: {error_message}")
                return
        else:
            thread_id = self.threads[channel_id]
            requests.post(
                f'https://api.openai.com/v1/threads/{thread_id}/messages',
                headers={
                    'Authorization': f'Bearer {self.OPENAI_API_KEY}',
                    'OpenAI-Beta': 'assistants=v2',
                    'OpenAI-Organization': self.OPENAI_ORG_ID
                },
                json={
                    'role': 'user',
                    'content': question
                }
            )

        async with ctx.channel.typing():
            for _ in range(3):  # Retry up to 3 times
                run_response = requests.post(
                    f'https://api.openai.com/v1/threads/{self.threads[channel_id]}/runs',
                    headers={
                        'Authorization': f'Bearer {self.OPENAI_API_KEY}',
                        'OpenAI-Beta': 'assistants=v2',
                        'OpenAI-Organization': self.OPENAI_ORG_ID
                    },
                    json={
                        "assistant_id": self.ASSISTANT_ID
                    }
                )
                run = run_response.json()
                logging.info(f"Run creation response: {run}")

                if 'status' in run:
                    while run['status'] not in ['completed', 'failed']:
                        run_response = requests.get(
                            f'https://api.openai.com/v1/threads/{self.threads[channel_id]}/runs/{run["id"]}',
                            headers={
                                'Authorization': f'Bearer {self.OPENAI_API_KEY}',
                                'OpenAI-Beta': 'assistants=v2',
                                'OpenAI-Organization': self.OPENAI_ORG_ID
                            }
                        )
                        run = run_response.json()
                        logging.info(f"Run status: {run['status']}")
                        await asyncio.sleep(1)  # Add a delay between checks

                    if run['status'] == 'failed':
                        last_error = run.get('last_error', 'Unknown error')
                        logging.error(f"Run failed: {last_error}")
                        await ctx.reply(f"Run failed: {last_error}")
                        return

                    assistant_message_content = self.get_latest_assistant_message(self.threads[channel_id], run["id"])

                    if assistant_message_content:
                        # Suppression des références entourées de 【】
                        clean_content = re.sub(r'【.*?】', '', assistant_message_content)

                        if len(clean_content) > 2000:
                            parts = self.split_message(clean_content)
                            for part in parts:
                                await ctx.reply(part)
                        else:
                            await ctx.reply(clean_content)
                    return
                else:
                    logging.error(f"Run response does not contain 'status': {run}")
                await asyncio.sleep(1)  # Add a delay before retrying

async def setup(bot):
    await bot.add_cog(OpenAIThreadsCog(bot))
