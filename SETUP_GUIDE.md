# 🚀 Real-World Deployment Guide for Your Discord Bot

Since the code is already written, you now need to configure the **Discord Developer Portal** to make the bot "real" and functional in your server.

## Step 1: Create Your Bot Application
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **"New Application"** at the top right.
3. Give your bot a name (e.g., "My Awesome Bot") and agree to the terms.
4. In the left sidebar, click on **"Bot"**.

## Step 2: Enable Privileged Gateway Intents (CRITICAL)
The bot uses `discord.Intents.all()`, which means it needs permission to see members and messages. **If you skip this, the bot will not work.**
1. On the **"Bot"** page, scroll down to the **"Privileged Gateway Intents"** section.
2. Toggle **ON** the following:
   - **Presence Intent** (Needed for member status)
   - **Server Members Intent** (Needed for `!dmall` and member lookups)
   - **Message Content Intent** (Needed for the bot to read `!say`, `!bj`, etc.)
3. Click **"Save Changes"**.

## Step 3: Get Your Bot Token
1. Still on the **"Bot"** page, look for the **"Token"** section.
2. Click **"Reset Token"** (or "Copy") to get your unique bot token.
3. **Keep this secret!** Copy it and paste it into your `.env` file:
   ```env
   DISCORD_TOKEN=your_copied_token_here
   ```

## Step 4: Invite the Bot to Your Server
1. In the left sidebar, go to **"OAuth2"** $\rightarrow$ **"URL Generator"**.
2. Under **"Scopes"**, check:
   - `bot`
   - `applications.commands`
3. Under **"Bot Permissions"**, check:
   - `Administrator` (Since this is a management bot with ticket/log features, Admin is the easiest way to ensure it works, but you can select specific permissions like `Manage Channels`, `Send Messages`, `Read Message History`, etc.)
4. **Copy the URL** generated at the bottom.
5. Paste that URL into your browser, select your server, and authorize the bot.

## Step 5: Configure Server IDs
The bot needs to know *where* to send logs and *who* the staff are.
1. **Enable Developer Mode in Discord**:
   - Open Discord $\rightarrow$ User Settings $\rightarrow$ Advanced $\rightarrow$ Enable **Developer Mode**.
2. **Get IDs**:
   - **Log Channel**: Right-click the channel you want as your log channel $\rightarrow$ **Copy Channel ID**. Paste it in `.env` as `LOG_CHANNEL_ID`.
   - **Staff Role**: Go to Server Settings $\rightarrow$ Roles $\rightarrow$ Right-click your Staff role $\rightarrow$ **Copy Role ID**. Paste it in `.env` as `STAFF_ROLE_ID`.
   - **Ticket Category**: Right-click the category where tickets should open $\rightarrow$ **Copy Category ID**. Paste it in `.env` as `TICKET_CATEGORY_ID`.

## Step 6: Run the Bot
1. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the bot:
   ```bash
   python3 bot.py
   ```

## 🛠️ Quick Command Reference
- **Admin**: `!say Hello World`, `!dmall Welcome to the server!`
- **Tickets**: `!setup_tickets` (then click the button).
- **Applications**: `!apply` (check your DMs).
- **Games**: `!balance`, `!spin`, `!bj`, `!ttt @user`.
