import time
import os
import sys
import requests
import threading
import asyncio  # Import asyncio for sleep functionality
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, CallbackContext, filters
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import mss  # Import mss for capturing screenshots
from PIL import Image

# Define states for the conversation
ASK_WORKER_NAME = 0

class NewFileHandler(FileSystemEventHandler):
    def __init__(self, excluded_files, bot_token, chat_id, worker):
        super().__init__()
        self.excluded_files = excluded_files
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.worker = worker

    def send_telegram_message(self, message):
        if self.bot_token and self.chat_id:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {'chat_id': self.chat_id, 'text': message}
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                print("Message sent successfully!")
            else:
                print(f"Failed to send message: {response.status_code} - {response.text}")

    def send_document(self, file_path):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        with open(file_path, 'rb') as file:
            files = {'document': file}
            payload = {'chat_id': self.chat_id}
            response = requests.post(url, data=payload, files=files)
            return response

    def take_screenshot(self):
        screenshots = []
        with mss.mss() as sct:
            for monitor in sct.monitors[1:]:  # Skip the first monitor (index 0)
                img = sct.grab(monitor)
                img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                screenshots.append(img)

        total_width = sum(img.width for img in screenshots)
        max_height = max(img.height for img in screenshots)
        combined_image = Image.new('RGB', (total_width, max_height))
        
        x_offset = 0
        for img in screenshots:
            combined_image.paste(img, (x_offset, 0))
            x_offset += img.width

        screenshot_path = f"screenshot_{self.worker}.png"
        combined_image.save(screenshot_path)
        return screenshot_path

    def on_created(self, event):
        if not event.is_directory:
            file_name = os.path.basename(event.src_path)
            if file_name in self.excluded_files:
                print(f"Excluded file created: {event.src_path}")
                return
            message = f"New file created: {file_name} by worker: {self.worker}"
            print(message)
            self.send_telegram_message(message)
            # Send the newly created file as an attachment
            response = self.send_document(event.src_path)
            if response.status_code == 200:
                print(f"File sent successfully: {file_name}")
            else:
                print(f"Failed to send file: {response.status_code} - {response.text}")

def send_monitoring_message(bot_token, chat_id, interval, worker):
    while True:
        time.sleep(interval)
        message = f"Monitoring is still active by worker: {worker}."
        print(message)
        if bot_token and chat_id:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {'chat_id': chat_id, 'text': message}
            requests.post(url, json=payload)

def read_config(file_path):
    config = {}
    try:
        with open(file_path, 'r') as file:
            for line in file:
                if ':' in line:
                    key, value = line.split(':', 1)
                    config[key.strip()] = value.strip()
        return (
            config.get('BotToken'),
            config.get('ChatID'),
            [file.strip() for file in config.get('ExcludedFiles', '').split(',') if file.strip()],
            config.get('Worker'),
            int(config.get('MonitoringStillActiveMsg', 10))
        )
    except Exception as e:
        print(f"Could not read config file: {e}")
        return None, None, [], None, 10

async def start_screen_command(update: Update, context: CallbackContext):
    context.user_data['file_handler'] = context.bot_data['file_handler']
    context.user_data['worker'] = context.bot_data['worker']
    context.user_data['screenshot_sent'] = False  # Reset flag when starting a new command
    await update.message.reply_text("Please provide the worker's name for the screenshot:")
    return ASK_WORKER_NAME

async def ask_worker_name(update: Update, context: CallbackContext):
    worker_name = update.message.text.strip()  # Trim whitespace
    stored_worker_name = context.user_data.get('worker', '').strip()  # Trim whitespace

    # Check if the screenshot was already sent
    if context.user_data.get('screenshot_sent', False):
        await update.message.reply_text("Screenshot has already been sent. Please start a new request.")
        return ConversationHandler.END

    if worker_name.lower() == stored_worker_name.lower():  # Normalize case
        file_handler = context.user_data.get('file_handler')
        if file_handler:
            screenshot_path = file_handler.take_screenshot()
            await asyncio.sleep(1)  # Wait for 1 second before sending the screenshot
            response = file_handler.send_document(screenshot_path)
            if response.status_code == 200:
                await update.message.reply_text("Screenshot taken and sent successfully!")
                context.user_data['screenshot_sent'] = True  # Set flag to indicate screenshot sent
                os.remove(screenshot_path)  # Delete the screenshot after sending
            else:
                await update.message.reply_text(f"Failed to send screenshot: {response.status_code}")
        else:
            await update.message.reply_text("File handler not found.")
    else:
        await update.message.reply_text("Worker name does not match. Please try again.")
    
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text("Cancelled the screenshot request.")
    return ConversationHandler.END

def monitor_directory(path, excluded_files, bot_token, chat_id, worker):
    event_handler = NewFileHandler(excluded_files, bot_token, chat_id, worker)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def main():
    directory_to_monitor = os.path.dirname(os.path.abspath(sys.argv[0]))
    config_file_path = os.path.join(directory_to_monitor, 'TelegramBotSettings.txt')
    BOT_TOKEN, CHAT_ID, EXCLUDED_FILES, WORKER, MONITORING_STILL_ACTIVE_MSG = read_config(config_file_path)

    if BOT_TOKEN and CHAT_ID:
        startup_message = f"Monitoring has started successfully by worker: {WORKER}. Monitoring Still Active Msg is set to: {MONITORING_STILL_ACTIVE_MSG}"
        print(startup_message)
        file_handler = NewFileHandler(EXCLUDED_FILES, BOT_TOKEN, CHAT_ID, WORKER)
        file_handler.send_telegram_message(startup_message)

        # Start a thread for sending periodic monitoring messages
        threading.Thread(target=send_monitoring_message, args=(BOT_TOKEN, CHAT_ID, MONITORING_STILL_ACTIVE_MSG, WORKER), daemon=True).start()

        # Set up the Telegram bot
        application = ApplicationBuilder().token(BOT_TOKEN).build()
        
        application.bot_data['file_handler'] = file_handler
        application.bot_data['worker'] = WORKER

        # Set up conversation handler
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('screen', start_screen_command)],
            states={
                ASK_WORKER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_worker_name)]
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )

        # Register the conversation handler
        application.add_handler(conv_handler)

        # Run the monitoring in a separate thread
        threading.Thread(target=monitor_directory, args=(directory_to_monitor, EXCLUDED_FILES, BOT_TOKEN, CHAT_ID, WORKER), daemon=True).start()

        # Start polling for commands
        application.run_polling()

if __name__ == "__main__":
    main()