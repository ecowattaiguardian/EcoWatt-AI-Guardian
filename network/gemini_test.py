import os
from dotenv import load_dotenv
from google import genai

# Explicitly target the .env file in the root directory (D:\EcoWatt_AI_PROJECT\.env)
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
env_path = os.path.join(root_dir, ".env")

load_dotenv(dotenv_path=env_path, override=True)

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print(f"❌ ERROR: GEMINI_API_KEY not found at path: {env_path}")
else:
    print(f"Loaded API Key: {api_key[:6]}... (Length: {len(api_key)})")
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say 'API Key is working successfully!' if you can read this.",
        )
        print("✅ SUCCESS! Gemini Response:")
        print(response.text.strip())
    except Exception as e:
        print(f"❌ API CONNECTION FAILED: {e}")