import json
import logging
import os
import time
import threading
import tiktoken

import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

import lexi_ai_api

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_USERNAME = os.environ.get("BOT_USERNAME")
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID"))

CONFIG_DATA_FILE = "config.json"
USER_DATA_FILE = "users.json"

GROUP_MODES = {
    "respond_to_mentions_only": "Respond only to mentions",
    "respond_to_allowed_users": "Respond only to authorized users",
    "respond_to_all_users": "Respond to all users"
}

PARSE_MODES = {
    "Markdown": "Markdown",
    "HTML": "HTML",
    "None": "None"
}

bot = telebot.TeleBot(BOT_TOKEN)

allowed_users = {}
config = {}
chat_contexts = {}
typing_active = {}
global_host = None
global_model = None
global_api_type = None
global_api_key = None
global_allow_all_users = False
global_system_prompt = None
global_parse_mode = "Markdown"
api_request_timeout = 120
group_mode = "respond_to_mentions_only"
max_context_tokens = 2048


def load_data():
    global allowed_users, config, global_host, global_model, global_api_type, \
        global_api_key, global_allow_all_users, global_system_prompt, group_mode, global_parse_mode, max_context_tokens

    allowed_users = load_json_data(USER_DATA_FILE, default={str(ADMIN_USER_ID): ADMIN_USER_ID})
    logging.info(f"Loaded allowed users: {allowed_users}")

    config = load_json_data(CONFIG_DATA_FILE, default={
        "api_type": None,
        "host": None,
        "model": None,
        "api_key": None,
        "allow_all_users": False,
        "system_prompt": None,
        "group_mode": "respond_to_mentions_only",
        "parse_mode": "Markdown",
        "max_context_tokens": 2048
    })
    logging.info(f"Loaded config: {config}")

    global_api_type = config.get("api_type")
    global_host = config.get("host")
    global_model = config.get("model")
    global_api_key = config.get("api_key")
    global_parse_mode = config.get("parse_mode", "Markdown")
    max_context_tokens = config.get("max_context_tokens", 2048)

    if global_api_type and global_host and global_model:
        logging.info(
            f"Using API: {global_api_type}, Host: {global_host}, Model: {global_model}, "
            f"API Key: {'***' if global_api_key else None}"
        )
    else:
        logging.warning("API configuration incomplete.")

    global_allow_all_users = config.get("allow_all_users", False)
    global_system_prompt = config.get("system_prompt")
    group_mode = config.get("group_mode", "respond_to_mentions_only")
    logging.info(
        f"Allow all users: {global_allow_all_users}, System prompt: {global_system_prompt}, "
        f"Group Mode: {group_mode}, Parse Mode: {global_parse_mode}, Max context tokens: {max_context_tokens}"
    )


def load_json_data(file_path, default=None):
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning(f"No {file_path} file found. Using default values.")
        return default


def save_data(file_path, data):
    with open(file_path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    logging.info(f"Saved data to {file_path}")


def send_typing_action(chat_id, bot, typing_active):
    logging.info(f"Sending typing action to chat {chat_id}...")
    while typing_active.get(chat_id, False):
        try:
            bot.send_chat_action(chat_id, 'typing')
            time.sleep(5)
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 429:
                retry_after = int(e.description.split("after ")[-1])
                logging.warning(f"Rate limited. Retrying after {retry_after} seconds.")
                time.sleep(retry_after)
            else:
                logging.error(f"Telegram API Error: {e}")
                break


def check_config(chat_id):
    logging.info(f"Checking config for chat {chat_id}...")
    if not global_api_type or not global_host or not global_model:
        bot.send_message(chat_id, "API configuration is incomplete. Use /setup command.")
        logging.warning("API configuration incomplete.")
        return False

    plugin = lexi_ai_api.SUPPORTED_API_TYPES.get(global_api_type)
    if plugin and getattr(plugin, "api_key_required", False) and not global_api_key:
        bot.send_message(chat_id, f"API key is required for {global_api_type}. Use /setup command.")
        logging.warning(f"API key required but not provided for {global_api_type}.")
        return False

    logging.info("Configuration is valid.")
    return True


def count_tokens(messages, model: str) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        logging.warning(f"Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = 0
    for message in messages:
        num_tokens += 4
        for key, value in message.items():
            if value is not None:
                num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens -= 1
    num_tokens += 3
    return num_tokens


def send_api_request(
        chat_id,
        reply_to_message_id=None,
        api_type=None,
        host=None,
        model=None,
        api_key=None,
        system_prompt=None,
        parse_mode=None,
        bot=None,
        typing_active=None,
        api_request_timeout=120,
        max_context_tokens=2048
):
    global chat_contexts

    typing_active[chat_id] = True
    typing_thread = threading.Thread(target=send_typing_action, args=(chat_id, bot, typing_active))
    typing_thread.start()

    try:
        while count_tokens(chat_contexts[chat_id], model) > max_context_tokens:
            logging.warning(f"Context for chat {chat_id} exceeds token limit. Removing oldest messages...")
            chat_contexts[chat_id].pop(1)

        if chat_contexts[chat_id][0]["role"] == "system" and chat_contexts[chat_id][0]["content"] is None:
            chat_contexts[chat_id] = chat_contexts[chat_id][1:]

        response_text = lexi_ai_api.send_api_request(
            api_type=api_type,
            host=host,
            model=model,
            api_key=api_key,
            messages=chat_contexts[chat_id],
            system_prompt=system_prompt,
            api_request_timeout=api_request_timeout
        )

        if response_text:
            chat_contexts[chat_id].append({"role": "assistant", "content": response_text})

            chunks = split_into_chunks(response_text, 4096)

            for index, chunk in enumerate(chunks):
                try:
                    bot.send_message(
                        chat_id,
                        chunk,
                        reply_to_message_id=reply_to_message_id if index == 0 else None,
                        parse_mode=parse_mode
                    )
                except ApiTelegramException:
                    logging.warning(f"Error sending message with Markdown. Retrying without Markdown...")
                    bot.send_message(
                        chat_id,
                        chunk,
                        reply_to_message_id=reply_to_message_id if index == 0 else None
                    )
        else:
            bot.send_message(chat_id, "Error: Empty response from API")
            logging.error("Empty response from API")

    except (TimeoutError, ConnectionError, RuntimeError) as e:
        bot.send_message(chat_id, str(e))
        logging.error(f"Error during API request: {e}")
    finally:
        typing_active[chat_id] = False


def split_into_chunks(text, chunk_size):
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


@bot.message_handler(commands=["start"])
def handle_start_command(message):
    global chat_contexts
    chat_id = message.chat.id
    user_id = message.from_user.id
    logging.info(f"User {user_id} started a dialogue in chat {chat_id}")

    if user_id == ADMIN_USER_ID:
        start_setup_admin(chat_id)
        return

    if message.chat.type == 'private':
        if str(user_id) in allowed_users or global_allow_all_users:
            bot.send_message(chat_id, "Hello! I'm an AI chatbot, ready to chat with you.",
                             parse_mode=global_parse_mode)
        else:
            bot.send_message(chat_id,
                             "Hello! I'm an AI chatbot.\n"
                             "Please contact the administrator for access.",
                             parse_mode=global_parse_mode)

    if chat_id not in chat_contexts:
        chat_contexts[chat_id] = [{"role": "system", "content": global_system_prompt}]


@bot.message_handler(commands=["help"])
def handle_help_command(message):
    user_id = message.from_user.id
    logging.info(f"User {user_id} requested help")
    if user_id == ADMIN_USER_ID:
        help_text = """
        *Available admin commands:*

        /start - Start interacting with the bot
        /help - Show this help message
        /myid - Show your Telegram ID
        /clearcontext - Clear context

        /setup - Setup the bot
        /systemprompt - Set a system prompt
        /model - Select a model
        /timeout - Set API request timeout
        /adduser - Add a user
        /deluser - Delete a user
        /useraccess - Toggle access between all users and authorized users only
        /groupmode - Choose the bot's behavior in groups
        /parsemode - Choose the message parsing mode (Markdown, HTML, None)
        /contextlimit - Set the context size limit in tokens
        """
    else:
        help_text = """
        *Available commands:*

        /start - Start chatting with the bot
        /help - Show this help message
        /myid - Show your Telegram ID
        /clearcontext - Clear context
        """
    bot.reply_to(message, help_text, parse_mode='Markdown')


@bot.message_handler(commands=['systemprompt'])
def handle_system_prompt_command(message):
    global global_system_prompt, config, chat_contexts
    if message.from_user.id != ADMIN_USER_ID:
        bot.send_message(message.chat.id, "You don't have permission to use this command.")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_remove = types.InlineKeyboardButton('Remove Prompt', callback_data='remove_system_prompt')
    btn_show = types.InlineKeyboardButton('Show Prompt', callback_data='show_system_prompt')
    btn_set = types.InlineKeyboardButton('Set Prompt', callback_data='set_system_prompt')
    markup.add(btn_remove, btn_show, btn_set)

    bot.send_message(message.chat.id, "System prompt management:", reply_markup=markup)


@bot.message_handler(commands=['model'])
def handle_model_command(message):
    global global_api_type, global_model, config, global_api_key
    if message.from_user.id != ADMIN_USER_ID:
        bot.send_message(message.chat.id, "You don't have permission to use this command.")
        return

    show_available_models_for_api(message.chat.id, global_api_key)


@bot.message_handler(commands=['setup'])
def handle_setup_command(message):
    if message.from_user.id != ADMIN_USER_ID:
        bot.reply_to(message, "You don't have permission to use this command.")
        return

    start_setup_admin(message.chat.id)


@bot.message_handler(commands=['parsemode'])
def handle_parse_mode_command(message):
    global global_parse_mode, config
    if message.from_user.id != ADMIN_USER_ID:
        bot.reply_to(message, "You don't have permission to use this command.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for mode, description in PARSE_MODES.items():
        markup.add(types.InlineKeyboardButton(description, callback_data=f"set_parse_mode_{mode}"))

    bot.send_message(message.chat.id, "Choose message parsing mode:", reply_markup=markup)


@bot.message_handler(commands=['clearcontext'])
def handle_clear_context_command(message):
    global chat_contexts
    chat_id = message.chat.id
    chat_contexts[chat_id] = [{"role": "system", "content": global_system_prompt}]
    bot.reply_to(message, "Context cleared ")
    logging.info(f"Context cleared for chat {chat_id}")


@bot.message_handler(commands=['adduser'])
def handle_add_user_command(message):
    global allowed_users
    if message.from_user.id != ADMIN_USER_ID:
        bot.reply_to(message, "You don't have permission to use this command.")
        return

    bot.reply_to(message, "Please enter the user ID to add:")
    bot.register_next_step_handler(message, get_user_id_to_add)


@bot.message_handler(commands=['deluser'])
def handle_delete_user_command(message):
    global allowed_users
    if message.from_user.id != ADMIN_USER_ID:
        bot.reply_to(message, "You don't have permission to use this command.")
        return

    bot.reply_to(message, "Please enter the user ID to delete:")
    bot.register_next_step_handler(message, get_user_id_to_delete)


@bot.message_handler(commands=['useraccess'])
def handle_user_access_command(message):
    global global_allow_all_users, config
    if message.from_user.id != ADMIN_USER_ID:
        return

    global_allow_all_users = not global_allow_all_users
    config["allow_all_users"] = global_allow_all_users
    save_data(CONFIG_DATA_FILE, config)

    if global_allow_all_users:
        bot.reply_to(message, "The bot is now available to all users.")
        logging.info("Allowed all users to access the bot.")
    else:
        bot.reply_to(message, "The bot is now available only to authorized users.")
        logging.info("Restricted bot access to allowed users only.")


@bot.message_handler(commands=['groupmode'])
def handle_group_mode_command(message):
    global group_mode, config
    if message.from_user.id != ADMIN_USER_ID:
        bot.reply_to(message, "You don't have permission to use this command.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for mode, description in GROUP_MODES.items():
        markup.add(types.InlineKeyboardButton(description, callback_data=f"set_group_mode_{mode}"))

    bot.send_message(message.chat.id, "Choose group mode:", reply_markup=markup)

@bot.message_handler(commands=['contextlimit'])
def handle_context_limit_command(message):
    global max_context_tokens, config
    if message.from_user.id != ADMIN_USER_ID:
        bot.reply_to(message, "You don't have permission to use this command.")
        return

    bot.reply_to(message, "Enter the desired context size limit in tokens:")
    bot.register_next_step_handler(message, get_context_limit)

def get_context_limit(message):
    global max_context_tokens, config
    try:
        new_limit = int(message.text)
        if new_limit > 0:
            max_context_tokens = new_limit
            config["max_context_tokens"] = max_context_tokens
            save_data(CONFIG_DATA_FILE, config)
            bot.reply_to(message, f"Context size limit set to {max_context_tokens} tokens.")
        else:
            bot.reply_to(message, "Context size limit must be a positive integer.")
    except ValueError:
        bot.reply_to(message, "Invalid context size limit. Please enter an integer.")


@bot.message_handler(commands=['timeout'])
def handle_timeout_command(message):
    global api_request_timeout
    if message.from_user.id != ADMIN_USER_ID:
        bot.reply_to(message, "You don't have permission to use this command.")
        return

    bot.reply_to(message, "Please enter the new timeout value in seconds (0 for infinite):")
    bot.register_next_step_handler(message, get_timeout_value)


@bot.message_handler(commands=['myid'])
def handle_my_id_command(message):
    user_id = message.from_user.id
    bot.reply_to(message, f"Your ID is: `{user_id}`", parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data.startswith(
    ('setapi_', 'sethost_', 'setapikey_', 'remove_system_prompt', 'show_system_prompt',
     'set_system_prompt', 'setmodel_', 'set_parse_mode_')))
def handle_setup_callback(call):
    global global_api_type, global_host, global_api_key, config, global_model, global_system_prompt, global_parse_mode
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if call.data.startswith('setapi_'):
        api_type = call.data.split('_')[1]
        global_api_type = api_type
        config["api_type"] = global_api_type
        save_data(CONFIG_DATA_FILE, config)
        bot.answer_callback_query(call.id, "API type saved.")
        ask_api_host(chat_id)
    elif call.data.startswith('sethost_'):
        choice = call.data.split('_', 1)[1]
        if choice == "new":
            bot.send_message(chat_id, "Please enter a new host:")
            bot.register_next_step_handler(call.message, get_new_host_from_user)
        else:
            global_host = choice
            config["host"] = global_host
            save_data(CONFIG_DATA_FILE, config)
            bot.answer_callback_query(call.id, "API host saved.")
            ask_api_key(chat_id)
    elif call.data.startswith('setapikey_'):
        choice = call.data.split('_')[1]
        if choice == "yes":
            bot.send_message(chat_id, f"Please enter the API key for {global_api_type}:")
            bot.register_next_step_handler(call.message, get_api_key_from_user)
        elif choice == "no":
            global_api_key = None
            config["api_key"] = global_api_key
            save_data(CONFIG_DATA_FILE, config)
            bot.answer_callback_query(call.id, "API key not used.")
            ask_api_model(chat_id)
    elif call.data == 'remove_system_prompt':
        global_system_prompt = None
        config["system_prompt"] = None
        save_data(CONFIG_DATA_FILE, config)
        bot.answer_callback_query(call.id, "System prompt removed.")
        logging.info("System prompt removed.")
        for chat_id in chat_contexts:
            chat_contexts[chat_id][0] = {"role": "system", "content": global_system_prompt}
    elif call.data == 'show_system_prompt':
        if global_system_prompt:
            bot.answer_callback_query(call.id, f"Current system prompt:\n\n{global_system_prompt}", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "System prompt is not set.", show_alert=True)
    elif call.data == 'set_system_prompt':
        bot.send_message(call.message.chat.id, "Please enter the new system prompt:")
        bot.register_next_step_handler(call.message, get_system_prompt_from_user)
    elif call.data.startswith('setmodel_'):
        model_name = call.data.split('_')[1]
        global_model = model_name
        config["model"] = global_model
        save_data(CONFIG_DATA_FILE, config)
        bot.answer_callback_query(call.id, f"Model set to: {global_model}")
        settings_text = " *Bot setup completed!*\n\n"
        settings_text += f"**API Type:** `{global_api_type}`\n"
        settings_text += f"**API Host:** `{global_host}`\n"
        if global_api_key:
            settings_text += f"**API Key:** `{'***'}`\n"
        settings_text += f"**API Model:** `{global_model}`\n"

        bot.send_message(chat_id, settings_text, parse_mode='Markdown')
        logging.info(f"Model set to: {global_model}")
    elif call.data.startswith('set_parse_mode_'):
        parse_mode = call.data.split('_')[1]
        global_parse_mode = parse_mode
        config["parse_mode"] = global_parse_mode
        save_data(CONFIG_DATA_FILE, config)
        bot.answer_callback_query(call.id, f"Parse mode set to: {global_parse_mode}")
        bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                              text=f"Message parsing mode set to: {global_parse_mode}")

    try:
        bot.delete_message(chat_id=chat_id, message_id=message_id)
    except telebot.apihelper.ApiTelegramException as e:
        logging.error(f"Error deleting message: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("set_group_mode_"))
def handle_set_group_mode_callback(call):
    global group_mode, config
    chat_id = call.message.chat.id
    selected_mode = call.data.replace("set_group_mode_", "")

    config["group_mode"] = selected_mode
    save_data(CONFIG_DATA_FILE, config)

    group_mode = selected_mode

    bot.answer_callback_query(call.id, f"Group mode set to: {GROUP_MODES[selected_mode]}")
    bot.edit_message_text(chat_id, call.message.message_id, f"Group mode set to: {GROUP_MODES[selected_mode]}")


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    global global_host, global_model, global_api_type, chat_contexts, group_mode, global_api_key, global_parse_mode, max_context_tokens
    chat_id = message.chat.id
    user_id = message.from_user.id
    message_id = message.message_id

    logging.info(f"Received message from user {user_id} in chat {chat_id}: {message.text}")

    if message.chat.type != 'private':
        if group_mode == "respond_to_mentions_only":
            if not (message.text.startswith(f'@{BOT_USERNAME}') or
                    (message.reply_to_message and
                     message.reply_to_message.from_user.id == bot.get_me().id)):
                logging.debug("Ignoring message as it is not a private chat or a direct mention.")
                return
        elif group_mode == "respond_to_allowed_users":
            if not global_allow_all_users and str(user_id) not in allowed_users:
                logging.debug("Ignoring message as user is not authorized.")
                return
    else:
        if not global_allow_all_users and str(user_id) not in allowed_users:
            bot.send_message(chat_id, "Sorry, you do not have access to this bot.")
            logging.warning(f"User {user_id} is not allowed to use the bot.")
            return

    if not check_config(chat_id):
        return

    user_message = message.text.replace(f'@{BOT_USERNAME}', '').strip()

    if chat_id not in chat_contexts:
        chat_contexts[chat_id] = [{"role": "system", "content": global_system_prompt}]

    chat_contexts[chat_id].append({"role": "user", "content": user_message})

    send_api_request(
        chat_id=chat_id,
        reply_to_message_id=message_id,
        api_type=global_api_type,
        host=global_host,
        model=global_model,
        api_key=global_api_key,
        system_prompt=global_system_prompt,
        parse_mode=global_parse_mode,
        bot=bot,
        typing_active=typing_active,
        api_request_timeout=api_request_timeout,
        max_context_tokens=max_context_tokens
    )


def start_setup_admin(chat_id):
    global chat_contexts
    chat_contexts[chat_id] = [{"role": "system", "content": global_system_prompt}]
    markup = telebot.types.InlineKeyboardMarkup()
    for api_type in lexi_ai_api.SUPPORTED_API_TYPES:
        markup.add(telebot.types.InlineKeyboardButton(api_type, callback_data=f"setapi_{api_type}"))
    bot.send_message(chat_id,
                     " *Starting bot setup. Please follow the instructions.*\n\n"
                     "Select API type:",
                     reply_markup=markup,
                     parse_mode='Markdown')


def ask_api_host(chat_id):
    global global_api_type
    markup = telebot.types.InlineKeyboardMarkup()

    default_host = getattr(lexi_ai_api.SUPPORTED_API_TYPES[global_api_type], "default_host", None)
    if default_host:
        markup.add(
            telebot.types.InlineKeyboardButton(f"Default: {default_host}", callback_data=f"sethost_{default_host}")
        )

    last_used_host = config.get("host")
    if last_used_host and last_used_host != default_host:
        markup.add(telebot.types.InlineKeyboardButton(f"Last used: {last_used_host}",
                                                       callback_data=f"sethost_{last_used_host}"))

    markup.add(telebot.types.InlineKeyboardButton("Enter New Host", callback_data=f"sethost_new"))

    bot.send_message(chat_id, "Select API host:", reply_markup=markup)


def ask_api_key(chat_id):
    global global_api_type
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("Yes", callback_data="setapikey_yes"))
    markup.add(telebot.types.InlineKeyboardButton("No", callback_data="setapikey_no"))
    bot.send_message(chat_id,
                     f"Do you want to use an API key for {global_api_type}?",
                     reply_markup=markup)


def ask_api_model(chat_id):
    global global_api_type, global_api_key
    if global_api_type:
        show_available_models_for_api(chat_id, global_api_key)
    else:
        settings_text = "*Bot setup completed!*\n\n"
        settings_text += f"**API Type:** `{global_api_type}`\n"
        settings_text += f"**API Host:** `{global_host}`\n"
        if global_api_key:
            settings_text += f"**API Key:** `{'***'}`\n"
        settings_text += f"**API Model:** `{global_model}`\n"
        bot.send_message(chat_id, settings_text, parse_mode='Markdown')


def show_available_models_for_api(chat_id, api_key=None):
    global global_api_type, global_host
    logging.info(f"Showing available models for {global_api_type} API to chat {chat_id}")
    available_models = lexi_ai_api.get_available_models(global_host, api_type=global_api_type, api_key=api_key)
    if available_models:
        markup = telebot.types.InlineKeyboardMarkup()
        for model in available_models:
            markup.add(telebot.types.InlineKeyboardButton(model, callback_data=f"setmodel_{model}"))
        bot.send_message(chat_id, "Select model:", reply_markup=markup)
    else:
        bot.send_message(chat_id,
                         f"No models found for {global_api_type} on the server. "
                         f"Make sure that the server is available and has models.")


def get_new_host_from_user(message):
    global global_host, config
    chat_id = message.chat.id
    new_host = message.text.strip()
    if lexi_ai_api.is_host_available(new_host, global_api_type):
        global_host = new_host
        config["host"] = global_host
        save_data(CONFIG_DATA_FILE, config)
        bot.reply_to(message, f"API host saved.")
        ask_api_key(chat_id)
    else:
        bot.reply_to(message, f"The specified host is unavailable for {global_api_type}. Please enter a valid host.")
        bot.register_next_step_handler(message, get_new_host_from_user)


def get_api_key_from_user(message):
    global global_api_key, config
    chat_id = message.chat.id
    api_key = message.text.strip()
    global_api_key = api_key
    config["api_key"] = global_api_key
    save_data(CONFIG_DATA_FILE, config)
    bot.reply_to(message, f"API key saved.")
    ask_api_model(chat_id)


def get_user_id_to_add(message):
    global allowed_users
    try:
        user_id_to_add = int(message.text)
        if str(user_id_to_add) in allowed_users:
            bot.reply_to(message, f"User with ID {user_id_to_add} is already allowed.")
        else:
            allowed_users[str(user_id_to_add)] = user_id_to_add
            save_data(USER_DATA_FILE, allowed_users)
            bot.reply_to(message, f"User with ID {user_id_to_add} successfully added.")
            logging.info(f"User {user_id_to_add} added to allowed users.")
    except (ValueError, telebot.apihelper.ApiTelegramException) as e:
        bot.reply_to(message, f"Invalid user ID or an error occurred: {e}")


def get_user_id_to_delete(message):
    global allowed_users
    try:
        user_id_to_delete = int(message.text)
        if str(user_id_to_delete) in allowed_users:
            del allowed_users[str(user_id_to_delete)]
            save_data(USER_DATA_FILE, allowed_users)
            bot.reply_to(message, f"User with ID {user_id_to_delete} successfully deleted.")
            logging.info(f"User {user_id_to_delete} removed from allowed users.")
        else:
            bot.reply_to(message, f"User with ID {user_id_to_delete} not found in the allowed list.")
    except ValueError:
        bot.reply_to(message, "Invalid user ID.")


def get_timeout_value(message):
    global api_request_timeout
    try:
        new_timeout = int(message.text)
        if new_timeout >= 0:
            api_request_timeout = new_timeout
            bot.reply_to(message, f"API request timeout set to {api_request_timeout} seconds.")
        else:
            bot.reply_to(message, "Timeout value must be greater than or equal to zero.")
    except ValueError:
        bot.reply_to(message, "Invalid timeout value.")


def get_system_prompt_from_user(message):
    global global_system_prompt, config, chat_contexts
    global_system_prompt = message.text
    config["system_prompt"] = global_system_prompt
    save_data(CONFIG_DATA_FILE, config)
    bot.reply_to(message, f"System prompt set to:\n\n{global_system_prompt}")
    logging.info(f"System prompt set to: {global_system_prompt}")
    for chat_id in chat_contexts:
        chat_contexts[chat_id][0] = {"role": "system", "content": global_system_prompt}


load_data()

logging.info("Bot started and listening for messages.")
bot.polling(none_stop=True)