# Lexi: AI Chat Assistant for Telegram

<p align="center">
  ![Lexi Logo](lexi.jpg)
</p>

Lexi is a Telegram chatbot that connects to various Large Language Models (LLMs) such as OpenAI, Groq, Ollama, KoboldCpp, and Gemini. This allows you to have conversational experiences right within your Telegram app.

## Features

- **Multiple API Support**: Connect to different LLM providers including OpenAI, Groq, Ollama, KoboldCpp, and Gemini.
- **Customizable System Prompt**: Set up a system prompt to guide the AI's responses.
- **Multi-User Access**: Grant or restrict access to the bot based on user ID.
- **Flexible Group Chat Behavior**: Configure the bot to respond to mentions only, authorized users, or all users in group chats.
- **Context Handling**:  Maintains chat history within a session for more coherent conversations.
- **Token Usage Tracking**: Displays the number of tokens used per API call.

## Installation and Setup

### Prerequisites

1. **Python 3.9 or higher**
2. **A Telegram account**
3. **A Telegram bot token** (Create a bot using [@BotFather](https://t.me/botfather))
4. **API keys (optional, but required for some APIs like OpenAI, Groq, and Gemini)**

### Linux

1. **Clone the repository:**
   ```bash
   git clone https://github.com/crim50n/lexi.git
   cd lexi
   ```
2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Set environment variables:**
   ```bash
   export BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
   export ADMIN_USER_ID="YOUR_TELEGRAM_USER_ID"
   export BOT_USERNAME="YOUR_BOT_USERNAME"
   ```
5. **Run the bot:**
   ```bash
   python lexi.py
   ```

### Termux (Android)

1. **Install Termux and required packages:**
   ```bash
   pkg update
   pkg install python git python-pip
   ```
2. **Clone the repository:**
   ```bash
   git clone https://github.com/crim50n/lexi.git
   cd lexi
   ```
3. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
5. **Set environment variables:**
   ```bash
   export BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
   export ADMIN_USER_ID="YOUR_TELEGRAM_USER_ID"
   # Optional:
   export BOT_USERNAME="YOUR_BOT_USERNAME"
   ```
6. **Run the bot:**
   ```bash
   python lexi.py
   ```

## Configuration

The first time you run the bot as the administrator, use the `/setup` command in your Telegram chat with the bot to configure:

1. **API Type**: Choose your LLM provider (OpenAI, Groq, Ollama, etc.).
2. **API Host**: Use the default or provide a custom host address.
3. **API Key**: Enter your API key (if required by the chosen provider).
4. **API Model**: Select the specific LLM model you want to use.


## Usage

### General Commands

- `/start`: Start interacting with Lexi.
- `/help`: Show the help message with available commands.
- `/myid`: Show your Telegram ID.
- `/clearcontext`: Clear the conversation context.

### Admin Commands

- `/setup`: Configure Lexi's API settings.
- `/systemprompt`: Set a system-wide prompt.
- `/model`: Select a different LLM model.
- `/timeout`: Set the API request timeout in seconds (0 for infinite).
- `/adduser`: Add a user by their Telegram ID.
- `/deluser`: Delete a user by their Telegram ID.
- `/useraccess`: Toggle bot access between all users and authorized users only.
- `/groupmode`: Choose Lexi's behavior in groups (respond to mentions, authorized users, or all).
- `/parsemode`:  Choose the message parsing mode (Markdown, HTML, None, Auto).

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.
