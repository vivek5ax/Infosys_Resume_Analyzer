import subprocess
import sys

def ensure_model(model_name="en_core_web_sm"):
    try:
        import importlib
        importlib.import_module("spacy")
        import spacy
        spacy.load(model_name)
        print(f"spaCy model '{model_name}' already available.")
        return
    except Exception:
        print(f"spaCy model '{model_name}' not found — downloading...")
        subprocess.check_call([sys.executable, "-m", "spacy", "download", model_name])

if __name__ == "__main__":
    ensure_model()
