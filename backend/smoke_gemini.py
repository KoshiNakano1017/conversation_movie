"""動作確認: Gemini API 直接呼び出しでエラー内容を取得"""
import sys
sys.path.insert(0, ".")

import google.generativeai as genai
from app.config import settings

print(f"GEMINI_API_KEY: {'SET (' + settings.GEMINI_API_KEY[:10] + '...)' if settings.GEMINI_API_KEY else 'NOT SET'}")
print(f"key length: {len(settings.GEMINI_API_KEY)}")

genai.configure(api_key=settings.GEMINI_API_KEY)

print("\n--- list models ---")
try:
    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            print(f"  {m.name}")
except Exception as e:
    print(f"list_models error: {type(e).__name__}: {e}")

print("\n--- test generate_content ---")
try:
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content("Say 'hello' in Japanese.")
    print("SUCCESS:")
    print(response.text)
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
