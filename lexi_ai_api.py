import json
import logging
import requests
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from importlib import import_module

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

API_PLUGINS_DIR = "api_plugins"

adapter = HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]))
session = requests.Session()
session.mount('https://', adapter)
session.mount('http://', adapter)

SUPPORTED_API_TYPES = {}


def load_api_plugins(plugin_dir=API_PLUGINS_DIR):
    logging.debug(f"Loading API plugins from directory: {plugin_dir}")
    plugins = {}
    for filename in os.listdir(plugin_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = filename[:-3]
            logging.debug(f"Loading plugin module: {module_name}")
            try:
                module = import_module(f"{plugin_dir}.{module_name}")
                plugin_name = getattr(module, "PLUGIN_NAME", None)
                if plugin_name:
                    plugins[plugin_name] = module
                    logging.debug(f"Plugin '{plugin_name}' loaded successfully.")
                else:
                    logging.warning(f"Plugin in file {filename} skipped: PLUGIN_NAME not found.")
            except ImportError as e:
                logging.error(f"Error importing plugin {filename}: {e}")
            except AttributeError as e:
                logging.error(f"Error loading plugin from {filename}: {e}")
            except Exception as e:
                logging.error(f"Error loading plugin {filename}: {e}")
    logging.debug(f"Loaded plugins: {plugins}")
    return plugins


def is_host_available(host, api_type, api_key=None):
    logging.info(f"Checking availability of host {host} for {api_type} API...")

    plugin = SUPPORTED_API_TYPES.get(api_type)
    if not plugin:
        logging.error(f"API '{api_type}' is not supported.")
        return False

    try:
        is_available = plugin.is_host_available(host=host, api_key=api_key)
        logging.debug(f"Host availability result: {is_available}")
        return is_available
    except Exception as e:
        logging.error(f"Error checking host availability: {e}")
        return False


def get_available_models(host, api_type, api_key=None):
    logging.info(f"Getting available models from host {host} for {api_type} API...")
    models = []

    plugin = SUPPORTED_API_TYPES.get(api_type)
    if not plugin:
        logging.error(f"API '{api_type}' is not supported.")
        return models

    try:
        models = plugin.get_available_models(host=host, api_key=api_key)
        logging.info(f"Available models: {models}")
        return models
    except Exception as e:
        logging.error(f"Error fetching models: {e}")
        return models


def send_api_request(api_type, host, model, api_key, messages, system_prompt=None, api_request_timeout=120):
    logging.info(f"Sending API request to {api_type}...")

    plugin = SUPPORTED_API_TYPES.get(api_type)
    if not plugin:
        raise ValueError(f"Error: API '{api_type}' is not supported.")

    try:
        response = plugin.send_api_request(
            host=host,
            model=model,
            api_key=api_key,
            messages=messages,
            system_prompt=system_prompt,
            api_request_timeout=api_request_timeout
        )
        logging.debug(f"API response: {response}")
        return response
    except Exception as e:
        logging.error(f"Error during API request: {e}")
        raise

SUPPORTED_API_TYPES = load_api_plugins()