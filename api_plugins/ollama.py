import requests
import logging

PLUGIN_NAME = "Ollama"
default_host = "http://localhost:11434"
api_key_required = False 

def is_host_available(host, api_key=None):
    url = f"{host}/api/tags"
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking host availability: {e}")
        return False


def get_available_models(host, api_key=None):
    url = f"{host}/api/tags"
    models = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        models = [model.get("name") for model in data.get("models", [])]
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching models: {e}")
    return models


def send_api_request(host, model, api_key, messages, system_prompt=None, api_request_timeout=120):
    url = f"{host}/api/chat"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}" if api_key else ""
    }
    data = {
        "model": model,
        "messages": messages,
        "stream": False
    }
    try:
        if api_request_timeout == 0:
            response = requests.post(url, headers=headers, json=data)
        else:
            response = requests.post(url, headers=headers, json=data, timeout=api_request_timeout)
        response.raise_for_status()
        response_json = response.json()
        return response_json["message"]["content"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Error during API request: {e}")
        raise