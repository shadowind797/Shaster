import google.generativeai as genai

# Configure your API key (replace with your actual API key)
genai.configure(api_key="AIzaSyBzVy4mva2mc5CkA6oCMcxeULtLNRzDGk4")

# List available models
models = genai.list_models()

for model in models:
    print(model)