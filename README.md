# Discord AI Assistant Bot

## Overview

This bot is a multi-functional Discord assistant powered by OpenAI's API. It offers features such as FAQ management, waitlist handling, and interactive conversations with server members.

## Features

- **FAQ Management**: Automatically updates a knowledge base by monitoring a forum channel for new posts and adding Q&A pairs to a JSON file.
- **Waitlist System**: Handles a waitlist system for managing user access, including automated role assignment in the Discord server.
- **AI Conversations**: Provides interactive conversations using OpenAI's assistant model. Responses are restricted to specific channels configured via environment variables.
- **Logging**: Detailed logs are maintained with automatic log rotation, ensuring smooth operation and easy troubleshooting.

## Installation

1. **Clone the Repository**:

    ```bash
    git clone https://github.com/your-repo-url
    cd your-repo
    ```

2. **Install Dependencies**:
    Ensure Python 3.x is installed on the server. Then run the following command to install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. **Configure Environment Variables**:
    Create a `.env` file in the root directory of the project and populate it with the necessary environment variables as shown below:

    ```env
    DISCORD_TOKEN=your_discord_token
    OPENAI_API_KEY=your_openai_api_key
    OPENAI_ORG_ID=your_openai_org_id
    ASSISTANT_ID=your_assistant_id
    ALLOWED_CHANNELS=comma_separated_channel_ids
    ROLE_ID=role_id_for_waitlist
    FORUM_ID=forum_channel_id
    ```

4. **Run the Bot**:
    Once everything is set up, you can run the bot using the following command:

    ```bash
    python bot.py
    ```

5. **Setting Up Auto-Restart**:
    To ensure the bot restarts automatically every 24 hours, configure a cron job or use `pm2`. For example, with cron, you can schedule a daily restart:

    ```bash
    0 0 * * * /usr/bin/systemctl restart bot_service_name.service
    ```

## Monitoring and Logs

Logs are saved in the `bot_logs.log` file and automatically rotated to prevent excessive file size. You can monitor the bot's activity and debug issues by checking these logs.

## Troubleshooting

- **Bot Not Responding**: Ensure that the bot has the correct permissions on Discord, including access to the channels specified in the environment variables.
- **API Issues**: Verify that the OpenAI and Discord API keys are valid and check for any rate limits imposed by the APIs.
- **Environment Variable Issues**: Double-check that all required environment variables are correctly configured in the `.env` file.
