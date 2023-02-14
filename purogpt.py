import os
from pathlib import Path
from datetime import datetime
import random
import asyncio
import discord
import openai
import emoji
import sqlite3
import json
import numpy

DEBUG = True
LOGFILE = Path(f'logs/{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

DISCORD_API_KEY = Path('.discord_api_key').read_text()
DISCORD_CHANNEL_IDS = Path('discord_channel_ids.list').read_text().splitlines()
DISCORD_RESPOND_IDS = Path('discord_respond_ids.list').read_text().splitlines()

OPENAI_API_KEY = Path('.openai_api_key').read_text()
OPENAI_MODEL = "text-davinci-003"

# --- SHORT TERM MEMORY FUNCTIONS ---

MEMORY_SHORT_TERM = list()
def add_to_memory(text):
    if DEBUG:
        print(f"[d] Add to memory: {text}")
    MEMORY_SHORT_TERM.append(text)
    # Length of short term memory must be limited
    if len(MEMORY_SHORT_TERM) > 20:
        if DEBUG:
            print(f"[d] MEMORY_SHORT_TERM: {MEMORY_SHORT_TERM}")
            print(f"[d] Removing from memory: {MEMORY_SHORT_TERM[0]}")
        MEMORY_SHORT_TERM.pop(0)

# --- LONG TERM MEMORY FUNCTIONS ---

MEMORY_LONG_TERM = list()
DB_NAME = "memory.sqlite"
DB_TABLE = "long_term_memories"
DB_CONNECTION = sqlite3.connect(DB_NAME)

def init_ltm():
    global MEMORY_LONG_TERM
    
    # Create table if it's missing
    c = DB_CONNECTION.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS "+ DB_TABLE + "( id INTEGER NOT NULL PRIMARY KEY, vector JSON NOT NULL, timestamp TEXT NOT NULL, creator TEXT NOT NULL, content TEXT NOT NULL )")
    DB_CONNECTION.commit()
    MEMORY_LONG_TERM = load_ltm()
    
def load_ltm():
    # Load all long term memories
    c = DB_CONNECTION.cursor()
    c.execute("SELECT * FROM "+ DB_TABLE)
    # (id, vector, timestamp, creator, content)
    values = c.fetchall()
    return values

def append_ltm(msg):
    global MEMORY_LONG_TERM
    
    # Add single row to long term memories
    id = random.getrandbits(63)
    vector = json.dumps(get_vector_embedding(fmt_row(msg)))
    # (id, vector, timestamp, creator, content)
    data = (id, vector, msg['datetime'], msg['name'], msg['content'])

    if DEBUG:
        print(f"[d] Add to ltm: {msg['name']}: {msg['content']}")

    # Save to db
    c = DB_CONNECTION.cursor()
    c.execute("INSERT INTO "+ DB_TABLE +" VALUES(?, ?, ?, ?, ?)", data)
    DB_CONNECTION.commit()

    # Save to in-memory
    MEMORY_LONG_TERM.append(data)
    
def ltm_top_3(msg):
    global MEMORY_LONG_TERM
    
    if DEBUG:
        print(f"[d] Fetch memories from ltm for: {msg}")

    msg_vec = get_vector_embedding(fmt_row(msg))
    top_3 = list()
    for row in MEMORY_LONG_TERM:
        # Decode JSON vector to list
        distance = numpy.dot(msg_vec, json.loads(row[1]))

        #if DEBUG:
        #    print(f"[d] LTM search: {distance} for {row[4]}")
        
        if len(top_3) < 3:
            # First score.
            msg = dict()
            msg['datetime'] = row[2]
            msg['name'] = row[3]
            msg['content'] = row[4]
            top_3.append( (distance, fmt_row(msg)) )
            top_3.sort()
        elif distance > top_3[len(top_3)-1][0]:
            # New best score, append.
            msg = dict()
            msg['datetime'] = row[2]
            msg['name'] = row[3]
            msg['content'] = row[4]
            top_3.append( (distance, fmt_row(msg)) )
            if len(top_3) > 3:
                top_3.pop(0)

    if DEBUG:
        print(f"[d] Top 3 ltm: {repr(top_3)}")

    rtnlist = list()
    for row in top_3:
        rtnlist.append(row[1])
    return rtnlist
    
    

# --- TEXT FUNCTIONS ---

def fmt_row(msg):
    # Dict of (datetime, name, content) -> string "[time] user: text"
    return f"[{msg['datetime']}] {msg['name']}: {msg['content']}"

def append_text(path, text, encoding=None, errors=None):
    # De-emojize
    text = emoji.demojize(text)
    # Write to file
    with path.open("a", encoding=encoding, errors=errors) as f:
       f.write(text)

def load_kv(filepath):
    static_conf = dict()
    for line in filepath.read_text().splitlines():
        kv = line.split('=', 1)
        static_conf[kv[0]] = kv[1]
    return static_conf

STATIC_CONF = load_kv(Path('static.kv'))

def replace_all(source_text, msg):
    source_text = replace_static(source_text, STATIC_CONF)
    source_text = replace_dynamic(source_text, fmt_row(msg))
    source_text = replace_blocks(source_text, msg)
    return source_text

def replace_static(text, static_kv):
    for k, v in static_kv.items():
        text = text.replace(k, v)
    return text

def replace_dynamic(text, latest_msg):
    now = datetime.now()
    
    # Current date and time
    text = text.replace('<VAR-DATETIME>', now.strftime("%A, %Y-%m-%d %H:%M:%S"))

    # Latest message i.e. question from user
    text = text.replace('<VAR-LATEST-MESSAGE>', latest_msg)
    
    return text

def replace_blocks(text, msg):
    # Recent messages from short term memory
    text = text.replace('<BLOCK-RECENT-MESSAGES>', '\n'.join(MEMORY_SHORT_TERM))

    # Related memories from long term memory
    text = text.replace('<BLOCK-RELATED-MEMORIES>', '\n'.join(ltm_top_3(msg)))

    # Related facts from external sources
    text = text.replace('<BLOCK-RELATED-FACTS>', '')
    
    return text

# --- OPENAI ---

def get_vector_embedding(text):
    text = text.replace("\n", " ")
    # TODO: error handling
    return openai.Embedding.create(input = [text], model="text-embedding-ada-002")['data'][0]['embedding']

def ask_openai(prompt, temperature=0.8):
    return_dict = dict()

    # De-emojize prompts to OpenAI.
    prompt = emoji.demojize(prompt)

    done = False
    retries = 0
    retry_limit = 3
    while not done:
        try:
            response = openai.Completion.create(
                model=OPENAI_MODEL,
                prompt=prompt,
                temperature=temperature,
                max_tokens=2000,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            done = True
        except openai.error.RateLimitError:
            if retries > retry_limit:
                pass
            # Rate limiting error. Sleep and try again.
            print(f"[i] Rate limit {retries}/{retry_limit}, sleeping.")
            sleep(2)
            retries += 1

        except Exception as e:
            # Something failed?
            if DEBUG:
                return_dict["response"] = f"OpenAI request failed: {repr(e)}"
            else:
                return_dict["response"] = "Something went wrong in the OpenAI request. sorry."
            return return_dict

        if retries > retry_limit:
            # Can not get an answer, bail.
            return_dict["response"] = "I can not get response due to OpenAI timing out. Sorry about that."
            return return_dict

    # But we of course want to re-emojize OpenAI answers.
    response.choices[0].text = emoji.emojize(response.choices[0].text)
        
    # We have proper answer from OpenAI
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
        retdict["content"] = retdict["content"].replace(_id, f"@{STATIC_CONF['<VAR-CHATBOT-NAME>']}")
            
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

    msg = parse_discord_message(message)
    if not any(_id in message.content for _id in DISCORD_RESPOND_IDS):
        # Record to memory and skip
        add_to_memory(f"[{msg['datetime']}] {msg['name']}: {msg['content']}")
        return

    # Start the response generation
    async with message.channel.typing():
        # Search long term memory for related messages

        # Get facts from external sources

        if DEBUG:
            print(f"[d] >> {msg}")

        # Create the prompt
        prompt = replace_all(Path('templates/chat.template').read_text(), msg)

        if DEBUG:
            append_text(LOGFILE, '\n' + prompt + '\n')

        # Send prompt to openai
        loop = asyncio.get_running_loop()
        openai_response = await loop.run_in_executor(None, ask_openai, prompt)
        print(f"<< {repr(openai_response)}")

    # Save last message to memory
    add_to_memory(f"[{msg['datetime']}] {msg['name']}: {msg['content']}")
    append_ltm(msg)
    
    # Save our reponse to memory
    now = datetime.now()
    add_to_memory(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {STATIC_CONF['<VAR-CHATBOT-NAME>']}: {openai_response['response']}")

    if DEBUG:
        append_text(LOGFILE, '-'*80 + '\n' + 'OpenAI Response:\n' + openai_response['response'] + '\n' + '-'*80 + '\n\n')

    # Send response to discord
    await message.channel.send(openai_response["response"])


# --- MAIN LOOP ---

if __name__ == "__main__":
    print("=== Starting Chatbot ===")
    print(f"[i] Discord API-KEY: {DISCORD_API_KEY}")
    print(f"[i] OpenAI API-KEY: {OPENAI_API_KEY}")
    print(f"[i] Static configuration: {repr(STATIC_CONF)}")

    # Load long term memories
    init_ltm()

    if DEBUG:
        print(f"[d] Memories in ltm: {len(MEMORY_LONG_TERM)}")

    # Setup OpenAI
    openai.api_key = OPENAI_API_KEY

    # Setup Discord
    discord_client.run(DISCORD_API_KEY)

    # Cleanup
    DB_CONNECTION.close()
    
    print("=== SHUTDOWN ===")
