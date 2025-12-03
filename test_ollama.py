"""
Test Ollama connection before running the full pipeline
"""

import requests
import yaml

def test_ollama_connection():
    """Test if Ollama is running and accessible."""
    
    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    base_url = config['ollama']['base_url']
    model = config['ollama']['summarizer_model']
    
    print(f"Testing Ollama connection...")
    print(f"Base URL: {base_url}")
    print(f"Model: {model}")
    
    # Test 1: Check if Ollama is running
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        if response.status_code == 200:
            print("✓ Ollama is running")
            models = response.json().get('models', [])
            print(f"  Available models: {[m['name'] for m in models]}")
        else:
            print(f"✗ Ollama returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to Ollama at {base_url}")
        print("  Make sure Ollama is running: ollama serve")
        return False
    except Exception as e:
        print(f"✗ Error connecting to Ollama: {e}")
        return False
    
    # Test 2: Check if model exists
    model_exists = any(m['name'] == model or m['name'].startswith(model.split(':')[0]) 
                      for m in models)
    
    if not model_exists:
        print(f"✗ Model '{model}' not found")
        print(f"  Available models: {[m['name'] for m in models]}")
        print(f"  Try: ollama pull {model}")
        return False
    else:
        print(f"✓ Model '{model}' is available")
    
    # Test 3: Try a simple generation
    print("\nTesting model generation...")
    try:
        response = requests.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": "Say 'test successful' and nothing else.",
                "stream": False,
                "options": {"num_predict": 10}
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Model generation works")
            print(f"  Response: {result.get('response', '')[:100]}")
        else:
            print(f"✗ Generation failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Error during generation: {e}")
        return False
    
    print("\n" + "="*60)
    print("✓ All tests passed! Ollama is ready.")
    print("="*60)
    return True

if __name__ == "__main__":
    success = test_ollama_connection()
    exit(0 if success else 1)
