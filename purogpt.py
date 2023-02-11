import os
from pathlib import Path
import discord
import openai

CHATBOT_NAME = "PuroGPT"

DISCORD_API_KEY = Path('.discord_api_key').read_text()
DISCORD_CHANNEL_IDS = Path('discord_channel_ids.list').read_text().splitlines()
DISCORD_RESPOND_IDS = Path('discord_respond_ids.list').read_text().splitlines()

OPENAI_API_KEY = Path('.openai_api_key').read_text()
OPENAI_MODEL = "text-davinci-003"

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

    # Skip messages not meant to me
    if not any(_id in message.content for _id in DISCORD_RESPOND_IDS):
        return

    # Start the response generation
    async with message.channel.typing():
        msg_from = message.author.name
        msg_content = message.content
        for _id in DISCORD_RESPOND_IDS:
            msg_content = msg_content.replace(_id, CHATBOT_NAME)
        msg_content = msg_content.strip()
        print(f">> {msg_from}: {msg_content}")

        # Send prompt to openai
        openai_response = ask_openai(msg_content)
        print(f"<< {repr(openai_response)}")

    # Send response to discord
    await message.channel.send(openai_response["response"])


# --- MAIN LOOP ---

if __name__ == "__main__":
    print("=== Starting PuroGPT ===")
    print(f"[i] Discord API-KEY: {DISCORD_API_KEY}")
    print(f"[i] OpenAI API-KEY: {OPENAI_API_KEY}")

    # Setup OpenAI
    openai.api_key = OPENAI_API_KEY

    # Setup Discord
    discord_client.run(DISCORD_API_KEY)
    
    print("=== SHUTDOWN ===")
