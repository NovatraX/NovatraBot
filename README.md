# 🚀 NovatraBot

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/Discord.py-2.6.1+-blue.svg)](https://discordpy.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Issues](https://img.shields.io/github/issues/NovatraX/NovatraBot)](https://github.com/NovatraX/NovatraBot/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/NovatraX/NovatraBot)](https://github.com/NovatraX/NovatraBot/pulls)

A powerful Discord bot designed to enhance community management and personal accountability. Built with Python and powered by cutting-edge AI for moderation and user engagement.

## ✨ Features

### 🤖 Core Functionality

- **Ping & Uptime Monitoring**: Check bot latency and operational status
- **Bot Information**: Get detailed info about the bot and its capabilities
- **Developer Tools**: Access to special assets and commands

### 🛡️ Moderation System

- **Automatic Profanity Detection**: Real-time content filtering using advanced AI
- **Warning System**: Tracks user violations with persistent database storage
- **Smart Moderation**: Intelligent scoring system for content severity

### 📊 Accountability Tracker

- **Daily Task Logging**: Log and track personal goals and achievements
- **Statistics Dashboard**: View personal and community progress
- **Leaderboard System**: Competitive ranking for motivation
- **History Tracking**: Comprehensive activity logs
- **Automated Reminders**: Stay on track with scheduled notifications

### 🎯 Additional Features

- **Interactive Help System**: Comprehensive command guidance
- **Feedback Collection**: User feedback integration
- **Status Monitoring**: Real-time bot health checks
- **Reaction Handling**: Custom reaction management

## 🛠️ Installation

### Prerequisites

- Python 3.12 or higher
- A Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))

### Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/NovatraX/NovatraBot.git
   cd NovatraBot
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   Or if using uv

    ```bash
    uv sync
    ```

3. **Environment Configuration**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your Discord bot token:

   ```bash
   TOKEN=your_discord_bot_token_here
   ```

4. **Run the bot**

   ```bash
   python bot.py
   ```

   Or if using uv

    ```bash
    uv run bot.py
    ```

## 📖 Usage

### Basic Commands

- `/ping` - Check bot latency and uptime
- `/info` - Get bot information
- `/help` - Interactive help system

### Accountability Commands

- `/log add <task>` - Log a daily task
- `/log delete <task_number>` - Remove a logged task
- `/log stats [user]` - View accountability statistics
- `/log history` - Check your activity history
- `/log leaderboard` - See community rankings

### Moderation

The bot automatically monitors messages for inappropriate content and handles warnings internally. Moderators can review logs in designated channels.

## 🔧 Configuration

### Database Setup

The bot uses SQLite databases for data persistence:

- `moderation.db` - Stores warning data and user violations
- `accountability.db` - Tracks user tasks and progress
- `tasks.db` - Stores AI-generated todo tasks

### Linear Integration

Run `python3 get_linear_ids.py` to list IDs, then set these in `.env` to enable uploads:

- `LINEAR_API_KEY`
- `LINEAR_TEAM_ID`
- `LINEAR_PROJECT_ID` (optional)
- `LINEAR_STATE_TODO_ID`
- `LINEAR_STATE_BACKLOG_ID`
- `LINEAR_LABEL_URGENT_ID` (optional)
- `LINEAR_LABEL_HIGH_PRIORITY_ID` (optional)
- `LINEAR_LABEL_MEDIUM_PRIORITY_ID` (optional)
- `LINEAR_LABEL_LOW_PRIORITY_ID` (optional)

Ensure your bot has the following permissions:

- Read Messages
- Send Messages
- Embed Links
- Delete Messages
- Read Message History
- Mention Everyone (optional)

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built With [py-cord](https://github.com/Pycord-Development/pycord)
- AI-powered Moderation By [Profanity API](https://vector.profanity.dev)

## 📞 Support

- **Website**: [novatra.in](https://novatra.in)
- **Issues**: [GitHub Issues](https://github.com/NovatraX/NovatraBot/issues)
- **Discord**: [Discord Invite](https://discord.gg/hQ3APfbf6e)

---

Made wWth ❤️ By [Novatra](https://novatra.in)
