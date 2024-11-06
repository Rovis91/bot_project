import discord
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize bot client
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# Set forum channel IDs
FORUM_IDS = [int(os.getenv("FORUM_ID_1")), int(os.getenv("FORUM_ID_2"))]

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    
    # Initialize data structure for storing FAQ content
    faq_data = []

    # Iterate over each forum ID to retrieve content
    for forum_id in FORUM_IDS:
        forum_channel = bot.get_channel(forum_id)
        if not forum_channel:
            print(f"Forum channel with ID {forum_id} not found.")
            continue

        # Retrieve active threads
        active_threads = forum_channel.threads

        # Retrieve archived threads
        archived_threads = []
        async for archived_thread in forum_channel.archived_threads(limit=None):
            archived_threads.append(archived_thread)

        # Combine active and archived threads
        combined_threads = active_threads + archived_threads

        # Iterate over each thread (FAQ post) in the forum channel
        for thread in combined_threads:
            thread_data = {
                "question": thread.name,
                "answer": ""
            }

            # Retrieve only the first message in each thread as the answer
            async for message in thread.history(limit=1):
                thread_data["answer"] = message.content
                break  # Only take the first message

            faq_data.append(thread_data)

    # Save data to JSON file
    export_data = {
        "faq": faq_data
    }
    
    with open("faq_export.json", "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=4)

    print("FAQ export completed.")

    # Close the bot after export
    await bot.close()

# Run bot using the token from environment variables
bot.run(os.getenv("DISCORD_TOKEN"))
