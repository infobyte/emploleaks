"""
AI-powered employee role classifier.

Uses an OpenAI-compatible API (works with OpenAI, Ollama, etc.)
to classify employee titles into organizational departments/sectors.
"""

import json
import logging
import requests

log = logging.getLogger('emploleaks')

CLASSIFICATION_PROMPT_TEMPLATE = (
    'You are an organizational analyst. Given a list of employee job titles '
    'from a company, classify each one into a department/sector.\n\n'
    'Use concise department names like: Engineering, Security, Sales, Marketing, '
    'Human Resources, Finance, Operations, Legal, Design, Product, Management, '
    'IT, Data, Support, Research, Other.\n\n'
    'Respond ONLY with a valid JSON object where keys are the exact original '
    'titles and values are the department name. Do not include any explanation '
    'or markdown formatting.\n\n'
    'Example input:\n'
    '["Software Engineer", "Head of Sales", "CISO"]\n\n'
    'Example output:\n'
    '{"Software Engineer": "Engineering", "Head of Sales": "Sales", "CISO": "Security"}\n\n'
    'Here are the titles to classify:\n'
)


def classify_roles(titles, api_endpoint, api_key, model):
    """
    Classify a list of job titles into departments using an LLM.

    Args:
        titles: list of job title strings
        api_endpoint: OpenAI-compatible API base URL (e.g. http://localhost:11434/v1 for Ollama)
        api_key: API key (use 'ollama' for local Ollama)
        model: model name (e.g. 'gpt-4o-mini', 'llama3', etc.)

    Returns:
        dict mapping title -> department, or None on failure
    """
    unique_titles = list(set(t for t in titles if t and t.strip()))
    if not unique_titles:
        return None

    prompt = CLASSIFICATION_PROMPT_TEMPLATE + json.dumps(unique_titles, ensure_ascii=False)

    url = api_endpoint.rstrip('/') + '/chat/completions'

    headers = {
        'Content-Type': 'application/json',
    }
    if api_key and api_key.lower() != 'ollama':
        headers['Authorization'] = f'Bearer {api_key}'

    payload = {
        'model': model,
        'messages': [
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.1,
    }

    try:
        log.info(f"Classifying {len(unique_titles)} roles using AI model '{model}'...")
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()

        data = resp.json()
        content = data['choices'][0]['message']['content'].strip()

        if content.startswith('```'):
            content = content.split('\n', 1)[1] if '\n' in content else content[3:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()

        mapping = json.loads(content)

        if not isinstance(mapping, dict):
            log.error("AI returned non-dict response, skipping classification.")
            return None

        log.info(f"AI classified roles into {len(set(mapping.values()))} departments.")
        return mapping

    except requests.exceptions.ConnectionError:
        log.error(f"Cannot connect to AI endpoint: {url}")
        log.error("Make sure the AI service is running. For Ollama: 'ollama serve'")
        return None
    except requests.exceptions.Timeout:
        log.error("AI request timed out (120s). Try a smaller dataset or faster model.")
        return None
    except requests.exceptions.HTTPError as e:
        log.error(f"AI API error: {e}")
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        log.error(f"Failed to parse AI response: {e}")
        log.debug(f"Raw AI response content: {content if 'content' in dir() else 'N/A'}")
        return None
    except Exception as e:
        log.error(f"Unexpected error during AI classification: {e}")
        return None
