import requests
import logging

PLUGIN_NAME = "OpenAI"
default_host = "https://api.openai.com"
api_key_required = False

def is_host_available(host, api_key=None):
    url = f"{host}/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking host availability: {e}")
        return False


def get_available_models(host, api_key=None):
    url = f"{host}/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    models = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        models = [model.get("id") for model in data.get("data", [])]
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching models: {e}")
    return models


def send_api_request(host, model, api_key, messages, system_prompt=None, api_request_timeout=120):
    url = f"{host}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": model,
        "messages": messages
    }
    try:
        if api_request_timeout == 0:
            response = requests.post(url, headers=headers, json=data)
        else:
            response = requests.post(url, headers=headers, json=data, timeout=api_request_timeout)
        response.raise_for_status()
        response_json = response.json()
        return response_json["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Error during API request: {e}")
        raise