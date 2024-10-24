# MonitorMate
# Telegram File Monitoring Bot

## Description

This project is a Telegram bot that monitors a specified directory for new files. When a new file is created, the bot sends a message to a designated Telegram chat, notifying the user of the new file. Additionally, the bot can capture screenshots on command and send them as attachments. This script uses the `watchdog` library to monitor the directory and the `python-telegram-bot` library to interact with the Telegram API.

## Features

- Monitors a specified directory for new files.
- Sends notifications to a Telegram chat when a new file is created.
- Takes screenshots on command and sends them as attachments.
- Configurable settings through a text file.

## command
type
/screen 
to your bot to get an screenshot of your desktop

## Prerequisites

Before running the script, ensure you have the following installed:

- Python 3.x
- Required Python libraries:
  - `python-telegram-bot`
  - `watchdog`
  - `Pillow`
  - `mss`

You can install the required libraries using pip:

```bash
pip install python-telegram-bot watchdog Pillow mss

