import os
from pathlib import Path
from datetime import datetime
import discord
import openai

DEBUG = True
LOGFILE = Path(f'logs/{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

DISCORD_API_KEY = Path('.discord_api_key').read_text()
DISCORD_CHANNEL_IDS = Path('discord_channel_ids.list').read_text().splitlines()
DISCORD_RESPOND_IDS = Path('discord_respond_ids.list').read_text().splitlines()

OPENAI_API_KEY = Path('.openai_api_key').read_text()
OPENAI_MODEL = "text-davinci-003"

# --- MEMORY FUNCTIONS ---

MEMORY_SHORT_TERM = list()
def add_to_memory(text):
    if DEBUG:
        print(f"[d] Add to memory: {text}")
    MEMORY_SHORT_TERM.append(text)
    # Length of short term memory must be limited
    if len(MEMORY_SHORT_TERM) > 15:
        if DEBUG:
            print(f"[d] MEMORY_SHORT_TERM: {MEMORY_SHORT_TERM}")
            print(f"[d] Removing from memory: {MEMORY_SHORT_TERM[0]}")
        MEMORY_SHORT_TERM.pop(0)


# --- TEXT FUNCTIONS ---

def append_text(path, text, encoding=None, errors=None):
   with path.open("a", encoding=encoding, errors=errors) as f:
       f.write(text)

def load_kv(filepath):
    static_conf = dict()
    for line in filepath.read_text().splitlines():
        print(line)
        kv = line.split('=', 1)
        print(kv)
        static_conf[kv[0]] = kv[1]
    return static_conf

STATIC_CONF = load_kv(Path('static.kv'))

def replace_all(source_text):
    source_text = replace_static(source_text, STATIC_CONF)
    source_text = replace_dynamic(source_text)
    source_text = replace_blocks(source_text)
    return source_text

def replace_static(text, static_kv):
    for k, v in static_kv.items():
        text = text.replace(k, v)
    return text

def replace_dynamic(text):
    now = datetime.now()
    text = text.replace('<DYN-DATETIME>', now.strftime("%A, %Y-%m-%d %H:%M:%S"))
    return text

def replace_blocks(text):
    # Recent messages from short term memory
    text = text.replace('<BLOCK-RECENT-MESSAGES>', '\n'.join(MEMORY_SHORT_TERM))
    return text

# --- OPENAI ---

def ask_openai(prompt, temperature=0.8):
    response = openai.Completion.create(
        model=OPENAI_MODEL,
        prompt=prompt,
        temperature=temperature,
        max_tokens=128,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0
    )
    return_dict = dict()
    return_dict["response"] = response.choices[0].text.strip()
    return return_dict

# --- DISCORD ---

discord_intents = discord.Intents.none()
discord_intents.messages = True
discord_intents.message_content = True

discord_client = discord.Client(intents=discord_intents)

def parse_discord_message(message):
    now = datetime.now()
    retdict = dict()
    retdict["datetime"] = now.strftime("%Y-%m-%d %H:%M:%S")
    retdict["name"] = message.author.name.strip()
    retdict["content"] = message.content.strip()
    
    # Replace Discord user id for our bot with proper name
    for _id in DISCORD_RESPOND_IDS:
        retdict["content"] = retdict["content"].replace(_id, STATIC_CONF['<VAR-CHATBOT-NAME>'])
            
    return retdict
    
@discord_client.event
async def on_ready():
    print(f'{discord_client.user} has connected to Discord!')

@discord_client.event
async def on_message(message):
    # Skip messages in other channels
    if not any(_id in str(message.channel.id) for _id in DISCORD_CHANNEL_IDS):
        return
    
    # Skip messages created by me
    if message.author == discord_client.user:
        return

    #if DEBUG:
    #    print(f"[d] Received message: {message}")

    if any(_id in message.content for _id in DISCORD_RESPOND_IDS):
        # Record to memory and continue
        msg = parse_discord_message(message)
        add_to_memory(f"[{msg['datetime']}] {msg['name']}: {msg['content']}")
    else:
        # Record to memory and skip
        msg = parse_discord_message(message)
        add_to_memory(f"[{msg['datetime']}] {msg['name']}: {msg['content']}")
        return

    # Start the response generation
    async with message.channel.typing():
        # Search long term memory for related messages

        # Get facts from external sources

        if DEBUG:
            print(f"[d] >> {msg}")

        # Create the prompt
        prompt = replace_all(Path('templates/chat.template').read_text())

        if DEBUG:
            append_text(LOGFILE, '\n' + prompt + '\n')

        # Send prompt to openai
        openai_response = ask_openai(prompt)
        print(f"<< {repr(openai_response)}")

        if DEBUG:
            append_text(LOGFILE, '\n' + repr(openai_response) + '\n')


    # Send response to discord
    await message.channel.send(openai_response["response"])


# --- MAIN LOOP ---

if __name__ == "__main__":
    print("=== Starting PuroGPT ===")
    print(f"[i] Discord API-KEY: {DISCORD_API_KEY}")
    print(f"[i] OpenAI API-KEY: {OPENAI_API_KEY}")
    print(f"[i] Static configuration: {repr(STATIC_CONF)}")

    # Setup OpenAI
    openai.api_key = OPENAI_API_KEY

    # Setup Discord
    discord_client.run(DISCORD_API_KEY)

    
    print("=== SHUTDOWN ===")
