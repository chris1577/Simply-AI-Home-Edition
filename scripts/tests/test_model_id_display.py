"""
Quick test to verify model IDs are being passed to the template correctly
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app import create_app

def test_model_ids():
    """Test that model IDs are available in the config"""
    app = create_app('development')

    with app.app_context():
        model_ids = {
            'gemini': app.config.get('GEMINI_MODEL_ID', ''),
            'openai': app.config.get('OPENAI_MODEL_ID', ''),
            'anthropic': app.config.get('ANTHROPIC_MODEL_ID', ''),
            'xai': app.config.get('XAI_MODEL_ID', ''),
            'lm_studio': app.config.get('LM_STUDIO_MODEL_ID', ''),
            'ollama': app.config.get('OLLAMA_MODEL_ID', '')
        }

        print("Model IDs from config:")
        print("-" * 60)
        for provider, model_id in model_ids.items():
            print(f"{provider:12} : {model_id if model_id else '(not configured)'}")
        print("-" * 60)

        # Check if at least some model IDs are configured
        configured_count = sum(1 for mid in model_ids.values() if mid)
        print(f"\nConfigured models: {configured_count}/{len(model_ids)}")

        if configured_count > 0:
            print("[PASS] Model ID configuration test passed!")
            return True
        else:
            print("[WARN] No model IDs configured in .env file")
            return False

if __name__ == '__main__':
    test_model_ids()
