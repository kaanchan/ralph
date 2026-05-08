from dotenv import load_dotenv
load_dotenv()
import litellm, os
litellm.set_verbose = False
r = litellm.completion(
    model="gemini/gemini-2.0-flash",
    messages=[{"role": "user", "content": "Reply with just: OK"}],
)
print("Gemini:", r.choices[0].message.content.strip())
