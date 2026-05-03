import os
import json
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

# Load variables from .env file
load_dotenv()

# We get these values from the .env file
API_ID = int(os.getenv('TELEGRAM_API_ID', 0))
API_HASH = os.getenv('TELEGRAM_API_HASH', '')
PHONE_NUMBER = os.getenv('TELEGRAM_PHONE_NUMBER', '')

# The chat you want to scrape
TARGET_CHAT = os.getenv('TELEGRAM_TARGET_CHAT', 'me')

# This will create a session file named 'scraper_session.session' in the same folder.
client = TelegramClient('scraper_session', API_ID, API_HASH)

async def main():
    # Ensure you're authorized
    await client.start(phone=PHONE_NUMBER)
    print("Client Created and Authenticated!")

    # Ensure the target chat is valid
    try:
        entity = await client.get_entity(TARGET_CHAT)
        
        # Determine the name of the entity for printing
        if hasattr(entity, 'title'):
            chat_name = entity.title
        elif hasattr(entity, 'username') and entity.username:
            chat_name = f"@{entity.username}"
        elif hasattr(entity, 'first_name'):
            chat_name = entity.first_name
        else:
            chat_name = str(entity.id)
            
        print(f"Found entity: {chat_name}")
    except ValueError:
        print(f"Could not find chat '{TARGET_CHAT}'. Make sure the username or ID is correct.")
        return
    except Exception as e:
        print(f"An error occurred while finding the chat: {e}")
        return

    all_messages = []
    
    print(f"Scraping messages from {TARGET_CHAT}...")
    
    # Iterate through the messages in the target chat.
    # The limit is set to 100 for testing. To scrape all messages, remove `limit=100`, 
    # e.g., `async for message in client.iter_messages(entity):`
    async for message in client.iter_messages(entity, limit=100):
        # We extract basic metadata. You can add more fields if needed.
        msg_dict = {
            'id': message.id,
            'date': message.date.isoformat() if message.date else None,
            'sender_id': message.sender_id,
            'text': message.text,
            'reply_to_msg_id': message.reply_to_msg_id
        }
        all_messages.append(msg_dict)
        
    # Save the messages to a JSON file
    safe_target_name = str(TARGET_CHAT).replace("@", "").replace("/", "_")
    output_filename = f'chat_data_{safe_target_name}.json'
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(all_messages, f, indent=4, ensure_ascii=False)
        
    print(f"Successfully saved {len(all_messages)} messages to {output_filename}")

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())
