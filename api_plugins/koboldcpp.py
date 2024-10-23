import requests
import logging

PLUGIN_NAME = "KoboldCpp"
default_host = "http://localhost:1551"
api_key_required = False

def is_host_available(host, api_key=None):
    url = f"{host}/api/v1/model"
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking host availability: {e}")
        return False


def get_available_models(host, api_key=None):
    url = f"{host}/api/v1/model"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("result")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching models: {e}")
        return []


def send_api_request(host, model, api_key, messages, system_prompt=None, api_request_timeout=120):
    url = f"{host}/api/v1/generate"
    headers = {"Content-Type": "application/json"}
    data = {
        "prompt": f"{system_prompt}\n{messages}",
        "max_context_length": 2048,
        "temperature": 0.7,
        "top_p": 0.92,
        "top_k": 100,
        "typical_p": 1,
        "repetition_penalty": 1.07,
        "repetition_penalty_range": 2048,
        "repetition_penalty_slope": 0.18,
        "encoder_repetition_penalty": 1,
        "no_repeat_ngram_size": 0,
        "min_length": 0,
        "do_sample": True,
        "early_stopping": False,
        "seed": -1,
        "num_beams": 1,
        "length_penalty": 1,
        "stopping_strings": []
    }
    try:
        if api_request_timeout == 0:
            response = requests.post(url, headers=headers, json=data)
        else:
            response = requests.post(url, headers=headers, json=data, timeout=api_request_timeout)
        response.raise_for_status()
        response_json = response.json()
        return response_json["results"][0]["text"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Error during API request: {e}")
        raise