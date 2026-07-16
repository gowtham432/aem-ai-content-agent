from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("ALIBABA_API_KEY"),
    base_url=os.getenv("ALIBABA_BASE_URL")
)

response = client.chat.completions.create(
    model="qwen-plus",
    messages=[{"role": "user", "content": "Say hello"}]
)

print(response.choices[0].message.content)
print("Token usage:", response.usage)