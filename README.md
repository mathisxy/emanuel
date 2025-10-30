# LLM Discord Bot


This project implements a custom **Discord Bot** with integrated **LLM Backend** and optional **MCP Integration**.

<br>

## ⚙️ Installation

1. 📦 Clone Repository:
   ```bash
   git clone https://github.com/mathisxy/emanuel.git
   cd emanuel
   ```
2. 🧰 Install Dependencies\
   Make sure that **Python 3.12+** is installed\
   Create and activate a Python Virtual Environment:

   **Linux / macOS**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

   **Windows (PowerShell)**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
   
   Afterwards install the requirements:
   ```bash
   pip install -r requirements.txt
   ```
   
4. 🔑 Setup Environment Variables
   ```bash
   cp .env.example .env
   ```
   Afterwards open the .env file and fill in your Environment Variables
   ```bash
   nano .env
   ```
   
6. ▶️ Start Bot
   ```bash
   python main.py
   ```

<br>

## 💬 Usage

After starting the bot, you can add it to your **Discord server** and interact with it.

### 🚀 Adding the Bot to Your Server

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
1388538139261538364,Emanuel,@emanuel,ManuCraft
1423487340843761777,Helper,@help_woman,HelpMaster
1584829348201934847,Luna,@luna,LunaMC
```
