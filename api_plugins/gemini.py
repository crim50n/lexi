import requests
import logging

PLUGIN_NAME = "Gemini"
default_host = "https://generativelanguage.googleapis.com"
api_key_required = True


def is_host_available(host, api_key=None):
    url = f"{host}/v1beta/models/?key={api_key}"
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking host availability: {e}")
        return False


def get_available_models(host, api_key=None):
    url = f"{host}/v1beta/models/?key={api_key}"
    models = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        for model_data in data.get("models", []):
            model_name = model_data.get("name")
            if model_name:
                models.append(model_name.split("/")[-1]) # отсекаем префикс models/
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching models: {e}")
    return models


def send_api_request(host, model, api_key, messages, system_prompt=None, api_request_timeout=120):
    url = f"{host}/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"{system_prompt}\n{messages}"
                    }
                ]
            }
        ]
    }
    try:
        if api_request_timeout == 0:
            response = requests.post(url, headers=headers, json=data)
        else:
            response = requests.post(url, headers=headers, json=data, timeout=api_request_timeout)
        response.raise_for_status()
        response_json = response.json()
        return response_json["candidates"][0]["content"]["parts"][0]["text"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Error during API request: {e}")
        raise