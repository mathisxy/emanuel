# Discord AI Bot

> Not in active development


This project implements a custom **Discord Bot** with integrated **AI Backend** and optional tool calling via **MCP Integration**.

<br>

## Features
 - Chat with AI over Discord
 - Customizability via `.env` file
 - Modular design
 - Tool calling via MCP
 - Custom MCP integrations
 - Vision support for images

<br>

### Supported API Integrations

[![Mistral](https://img.shields.io/badge/Mistral-Supported-brightgreen)](https://mistral.ai/)
[![Azure OpenAI](https://img.shields.io/badge/Azure_OpenAI-Supported-brightgreen)](https://ai.azure.com)
[![Gemini](https://img.shields.io/badge/Gemini-Supported-brightgreen)](https://ai.azure.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-Supported-brightgreen)](https://ai.azure.com)
[![Ollama](https://img.shields.io/badge/Ollama-Supported-brightgreen)](https://ollama.com/)

<br>

## ⚙️ Installation on Ubuntu

1. 📦 Clone Repository:
   ```bash
   git clone https://github.com/mathisxy/discord-ai.git
   cd discord-ai
   ```
2. 🧰 Install Dependencies\
   Make sure that **Python 3.12+** is installed.\
   Create and activate a Python Virtual Environment:

   ```bash
   sudo apt install python3.12-venv
   python3 -m venv venv
   source venv/bin/activate
   ```
   
   Afterwards install the requirements:
   ```bash
   pip install -r requirements.txt
   ```
   
4. 🔑 Setup Environment Variables\
   <br>
   **Option 1: Manual**  
   1. Copy the example file:  
      ```bash
      cp .env.example .env
      ```
   2. Open the `.env` file in your preferred editor and fill in the values:  
      ```bash
      nano .env
      ```

   **Option 2: Interactive**  
   1. Make sure `setup_env.py` is in your project directory.  
   2. Run the setup script:  
      ```bash
      python setup_env.py
      ```
   3. Follow the prompts.  

   4. For direct use via commandline rename the generated `.env.{botname}` to `.env`:
      ```bash
      cp .env.{botname} .env
      ```
   
   
6. ▶️ Start Bot

   **Option 1: In the commandline**
   ```bash
   python main.py
   ```
   **Option 2: As a systemd service**

    ```
    python setup_service.py
    ```
   
    - ✅ Create and activate:
    ```bash
    sudo cp {botname}.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl start {botname}
    sudo systemctl enable {botname}
    ```

    - Check for errors:
    ```
    journalctl -u {botname}.service
    ```

    - ❌ Stop and remove:
    ```bash
    sudo systemctl stop {botname}
    sudo systemctl disable {botname}
    sudo rm /etc/systemd/system/{botname}.service
    sudo systemctl daemon-reload
    sudo systemctl reset-failed
    ```

   >Tip: Creating a systemd service allows your bot to run in the background and start automatically on boot.



<br>

## 💬 Usage

After starting the bot, you can add it to your **Discord server** and interact with it.

### 🚀 Adding the Bot to Your Discord Server

1. Go to your bot’s **installation page** on the Discord Developer Portal:  
   [Discord Bot Installation](https://discord.com/developers/applications/1433566130965844120/installation)
2. Scroll down to the **“OAuth2 URL Generator / Bot”** section.
3. Under **Scopes**, make sure `bot` is selected.
4. Under **Bot Permissions**, choose the permissions your bot needs (Im currently not sure which are required)
5. Copy the generated **Invite Link**.
6. Open the link in your browser and select the server where you want to add the bot.

> Tip: You must have the **Manage Server** permission on the server to add the bot.

---

### 💡 Interacting with the Bot

- Mention the bot in any channel to chat with it:

   ```
   @Botname Hello!
   ```
- Slash commands are also available, e.g.:
  ```
  /botname ...
  ```

<br>


## 👥 User Info Synchronization Logic

The bot automatically builds a combined list of user data from **Discord** and an optional **CSV file**.

### 🔧 How It Works

1. The bot collects all members who are currently **online** or **idle** on Discord.  
   Each Discord user contributes at least these two fields:
   - `Discord` → their display name  
   - `Discord ID` → their unique Discord user ID

2. If a CSV file path is defined in `.env` under `USERNAMES_PATH`,  
   the bot also loads that file and merges the entries using the `Discord ID` field as the key.

3. The CSV file **must include** a column named `Discord ID`.  
   All other columns are **optional** and will be integrated automatically if present  
   (for example, `Discord`, `Name`, `Minecraft`, or `Email`).

4. The final member list will include **all Discord users and all CSV entries**, even if one source is missing data for some users.  
   Overlapping fields from Discord take priority over CSV data.

---

### 📄 Example CSV

```csv
Discord ID,Name,Discord,Minecraft
1388538139261538364,Emanuel,emanuel,ManuCraft
1423487340843761777,Helper,help_woman,HelpMaster
1584829348201934847,Luna,luna,LunaMC
```
