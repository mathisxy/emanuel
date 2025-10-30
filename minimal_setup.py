
import re
from pathlib import Path

EXAMPLE_FILE = ".env.example"

def prompt_default(prompt, default=""):
    if default:
        return input(f"{prompt} [{default}]: ") or default
    return input(f"{prompt}: ")

def replace_line(lines, key, value):
    """
    Ersetzt die Zeile in lines, die mit key= beginnt, durch key=value.
    Wenn key nicht existiert, fügt sie am Ende hinzu.
    """
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    replaced = False
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = f"{key}={value}\n"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}\n")
    return lines

def main():
    if not Path(EXAMPLE_FILE).exists():
        print(f"❌ {EXAMPLE_FILE} not found in current directory.")
        return

    # Read example file
    with open(EXAMPLE_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    print("=== Minimal Setup for Discord Bot ===\n")

    # General settings
    bot_name = prompt_default("Enter bot name", "Emanuel")
    discord_token = prompt_default("Enter Discord Token")
    discord_id = prompt_default("Enter Discord Bot ID")
    language = prompt_default("Interface language (en/de)", "en")

    lines = replace_line(lines, "NAME", bot_name)
    lines = replace_line(lines, "DISCORD_TOKEN", discord_token)
    lines = replace_line(lines, "DISCORD_ID", discord_id)
    lines = replace_line(lines, "LANGUAGE", language)
    lines = replace_line(lines, "COMMAND_NAME", bot_name.lower())

    # AI Provider choice
    print("\nChoose AI Provider:")
    print("1) Ollama")
    print("2) Mistral")
    ai_choice = ""
    while ai_choice not in ["1", "2"]:
        ai_choice = input("Enter 1 or 2: ")

    if ai_choice == "1":
        lines = replace_line(lines, "AI", "ollama")
        ollama_url = prompt_default("Enter Ollama Server URL", "http://localhost:11434")
        lines = replace_line(lines, "OLLAMA_URL", ollama_url)
        ollama_model = prompt_default("Enter Ollama Model", "gemma3:12b")
        lines = replace_line(lines, "OLLAMA_MODEL", ollama_model)
    else:
        lines = replace_line(lines, "AI", "mistral")
        mistral_api_key = prompt_default("Enter Mistral API Key")
        lines = replace_line(lines, "MISTRAL_API_KEY", mistral_api_key)
        mistral_model = prompt_default("Enter Mistral Model", "mistral-medium-latest")
        lines = replace_line(lines, "MISTRAL_MODEL", mistral_model)

    # Save new env file
    output_file = f".env.{bot_name}"
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"\n✅ Configuration saved to {output_file}")

if __name__ == "__main__":
    main()
