"""
Test connectivity to the TACC OpenAI-compatible inference endpoint.
Checks the endpoint is reachable, the configured models are listed,
and each can complete a trivial chat request.
"""

import os
import sys
import yaml
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def test_tacc_connection(config_path: str = "config.yaml") -> bool:
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    tacc_config = config["tacc"]
    base_url = tacc_config["base_url"]
    models = tacc_config["models"]
    api_key_env = tacc_config["api_key_env"]

    api_key = os.environ.get(api_key_env)
    if not api_key:
        print(f"✗ Environment variable {api_key_env} is not set")
        return False

    client = OpenAI(base_url=f"{base_url}/v1", api_key=api_key)

    print(f"Testing TACC endpoint: {base_url}")

    # Test 1: list models
    try:
        available = {m.id for m in client.models.list().data}
        print(f"✓ Endpoint reachable, {len(available)} models listed")
    except Exception as e:
        print(f"✗ Could not list models: {e}")
        return False

    missing = [m for m in models if m not in available]
    if missing:
        print(f"✗ Configured models not found on endpoint: {missing}")
        print(f"  Available: {sorted(available)}")
        return False
    print(f"✓ All configured models present: {models}")

    # Test 2: trivial completion per model
    all_ok = True
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say 'test successful' and nothing else."}],
                max_tokens=10,
            )
            text = response.choices[0].message.content.strip()
            print(f"✓ {model}: {text!r}")
        except Exception as e:
            print(f"✗ {model} failed: {e}")
            all_ok = False

    return all_ok


if __name__ == "__main__":
    success = test_tacc_connection()
    sys.exit(0 if success else 1)
