# LLM Discord Bot


This project implements a custom **Discord Bot** with integrated **LLM Backend** and optional **MCP Integration**.

## ⚙️ Installation

1. 📦 Clone Repository
   ```
   git clone https://github.com/mathisxy/emanuel.git
   cd emanuel
   ```
2. 🧰 Install Dependencies
   ```
   pip install -r requirements.txt
   ```   


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
   (for example, `Name`, `Minecraft`, or `Email`).

4. The final member list will include **all Discord users and all CSV entries**, even if one source is missing data for some users.  
   Overlapping fields from Discord take priority over CSV data.

### 📄 Example CSV

```csv
Discord ID,Name,Discord,Minecraft
1388538139261538364,Emanuel,@emanuel,ManuCraft
1423487340843761777,Helper,@help_woman,HelpMaster
1584829348201934847,Luna,@luna,LunaMC
```
