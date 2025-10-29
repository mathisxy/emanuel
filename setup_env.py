import os
import re

def ask(prompt, default=None, required=False):
    """Prompt user with optional default and required fields, always one colon."""
    while True:
        if default:
            value = input(f"{prompt} [{default}]: ").strip()
        else:
            value = input(f"{prompt}: ").strip()

        if not value and default:
            return default
        if not value and required:
            print("⚠️  This field is required.")
        else:
            return value


def load_env_template(path=".env.example"):
    """Read the .env.example file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Template file '{path}' not found.")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def replace_vars(content, updates):
    """Replace environment variable values line by line."""
    for key, value in updates.items():
        pattern = rf"^({key}\s*=\s*)(.*)$"
        content = re.sub(pattern, rf"\1{value}", content, flags=re.MULTILINE)
    return content

def main():
    print("===========================================")
    print("🧩 Interactive .env Setup")
    print("===========================================\n")

    content = load_env_template(".env.example")

    # Basic info
    name = ask("Bot name (e.g. emanuel)", required=True)
    discord_token = ask("Discord Bot Token", required=True)
    discord_id = ask("Discord Bot ID", required=True)
    help_discord_id = ask("Discord Help ID (optional)", default="#123456789123456788")

    # Choose AI provider
    print("\nChoose AI Provider:")
    print("1️⃣  Ollama")
    print("2️⃣  Mistral")
    ai_choice = ask("Select [1 or 2]", default="1")
    ai = "ollama" if ai_choice == "1" else "mistral"

    # Ask only relevant values
    if ai == "ollama":
        ollama_url = ask("Ollama URL", default="http://localhost:11434")
        ollama_model = ask("Ollama Model", default="gemma3:12b")
        ollama_temp = ask("Ollama Model Temperature", default="1")
        ollama_image = ask("Enable Ollama Image Model? (true/false)", default="true")
        updates = {
            "AI": ai,
            "OLLAMA_URL": ollama_url,
            "OLLAMA_MODEL": ollama_model,
            "OLLAMA_MODEL_TEMPERATURE": ollama_temp,
            "OLLAMA_IMAGE_MODEL": ollama_image,
        }
    else:
        mistral_key = ask("Mistral API Key", required=True)
        mistral_model = ask("Mistral Model", default="mistral-medium-latest")
        updates = {
            "AI": ai,
            "MISTRAL_API_KEY": mistral_key,
            "MISTRAL_MODEL": mistral_model,
        }

    # General replacements
    updates.update({
        "NAME": name,
        "DISCORD_TOKEN": discord_token,
        "DISCORD_ID": discord_id,
        "HELP_DISCORD_ID": help_discord_id,
        "COMMAND_NAME": name,
    })

    # Apply replacements and write to new file
    updated = replace_vars(content, updates)
    filename = f".env.{name}"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"\n✅ Successfully created: {filename}")
    print(f"📄 Based on: .env.example")
    print(f"🤖 AI Provider: {ai.capitalize()}")

if __name__ == "__main__":
    main()
