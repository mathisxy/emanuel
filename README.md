# LLM Discord Bot


This project implements a custom **Discord Bot** with integrated **LLM Backend** and optional **MCP Integration**.


## 👥 User Synchronization Logic

The bot automatically builds a combined list of user data from Discord and an optional CSV file.

### 🔧 How It Works

The bot collects all members who are currently online or idle on Discord.
Each Discord user contributes at least these two fields:

Discord → their display name

Discord ID → their unique Discord user ID

If a CSV file path is defined in .env under USERNAMES_PATH,
the bot also loads that file and merges the entries using the Discord ID field as the key.

The CSV file must include a column named Discord ID.
All other columns are optional and will be integrated automatically if present
(for example, Name, Minecraft, or Email).

The final member list will include all Discord users and all CSV entries, even if one source is missing data for some users.
Overlapping fields from Discord take priority over CSV data.

### 📄 Example CSV

```
Discord ID,Name,Discord,Minecraft
1388538139261538364,Emanuel,emanuel,ManuCraft
1423487340843761777,Helper,help_woman,HelpMaster
1584829348201934847,Luna,luna,LunaMC
```
