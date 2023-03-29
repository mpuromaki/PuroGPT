# Chatbot I call PuroGPT

This is discord chatbot that uses OpenAI API to participate in conversations.

This project is in constant state of flux, while this public repository is older snapshot.
As you might know, in March 2023 the state of "AI" is very rapidly changing.
When I get something substantial finished, I'll update this repository to reflect the changes. Everything will change. Stay tuned.

## So, What's the plan?

The first version of this chatbot was very simple, basically just plumbed-together Discord API, OpenAI text completion API and sqlite + In-memory data structure working as persistent long-term memory (vector embeddings of previous conversations).
Since then I've studied this field a lot more and agree a lot with David Shapiros reasons on why "AI" needs proper cognitive architecture.
At first I was designing my own text-template based architecture, but now it's clear that LangChain is the way to go forward.

Thus, at high level, following software will be needed:

- Discord integration
- OpenAI LLM integration
- LangChain
- PostgreSQL pgvector extension

Those are in the works as soon as I'm able to. Idea is to spin up "pet" VM just for this project, which will automatically update from this repository. I am going to keep the update strategy simple: pull & update on startup. Some kind of ```Creator Commands``` might be good idea, so that I can command restart over Discord directly.

On the "AI" architecture I'm working on following things:

- LangChain
  - Template ```Core Objective Functions```, ```Personality```.
  - Template ```Dynamic Information```, eq. date and time and such.
  - LLM classify is this new message completely new conversation, part of current conversation, or part of some earlier conversation?
  - Template ```chat history``` of the selected conversation.
  - Template relevant ```long-term memories```, based on vector search.
  - Template relevant ```sentiment```, based on vector search.
  - LLM rewrite the new message into fully self-contained ```independent message```.
  - LLM anticipate users actual information needs, generate couple additional ```enriching questions``` of the same topic.
  - LLM replace ```long-term memories``` and ```sentiments``` with relevant ones based on ```independent message``` and ```enriching questions```.
  - ```Agent ReAct loop``` with this rich context, chat history and independent message.
  - Finally generate ```single reply``` to the user.
- PostgreSQL database & pgvector
  - Even the ongoing chat histories have to be in DB, as multiple conversations can be going on at the same time in the same room.
  - Nightly (during ```sleep```), process these conversations in to executively summarized, salient, long-term memories. 
  - Nightly (during ```sleep```), generate sentiment labels from long-term memories.
  - Nightly (during ```sleep```), take random sampling of current sentiments and update them based on latest long-term memories about that topic.
  
### Order of importance

Clearly when using chat logs, long-term memories and sentiments in the same place, there must be some kind of ```order of importance```.
While chat logs are always inlcuded for context, they might not be the most important part.

I'm thinking: ```Sentiment > Chat History > Long-term memory```

There might be need to do some kind of prioritizing recursive summary function to fit all this context into the token limit of selected LLM. This order of importance might play as a factor in choosing what to summarize and how much.

### Open questions

- How to generate quality sentiment over time? There has to be some kind of trustworthiness metric based on the source. Somehow known users are more trustworthy, Creator is more trustworthy, results of fact queries (ReAct loop) should be trustworthy-ish?
- Is there a need for some kind of knowledge-base or semantic web for data structuring?
- Some kind of system for ```Creator Commands``` is needed.
- Some kind of debug system is needed. I'm thinking that creator could start the message with ```--debug``` and response would be processing steps in separate message and then normal actual response from the chat bot.
- Maybe ```Knowledge Base``` is not from the chat messages, but separate database with preprocessed data from files and/or internet sources? Maybe "AI" could be instructed to load some source, preprocess it and then reply to message with that source available.
- There are multiple sources of context for each message. Token limit might be very easily reached, so some kind of prioritized recursive summarization might be needed. 


## Installing

1. Install latest Python 3.
2. Install Discord python library: pip install -U discord.py
3. Install OpenAI python library: pip install -U openai
4. Install Numpy python library: pip install -U numpy
5. Fill the configuration files and enjoy!

## How this works? (NOTE: Old information, to be changed)

### Short-term memory

Short term memory is just global python list of latest _n_ messages. These are not persisted anywhere. This allows the chatbot to get context, limited to the chatroom it's configured to be part of, even from messages that are not directly mentioning it.

```python 
MEMORY_SHORT_TERM = list() # Global
def add_to_memory(text):
    MEMORY_SHORT_TERM.append(text)
    # Length of short term memory must be limited
    if len(MEMORY_SHORT_TERM) > 20:
        MEMORY_SHORT_TERM.pop(0)
```

### Long-term memory

Long term memory is now internal list of messages from others. This list is loaded from sqlite db on startup and any new messages are written to the in-memory list as well as to the sqlite db. For each long-term memory message something called ```embedding``` is calculated by OpenAI. These embeddings work as a semantic ID, which can be used to search for "closeness". 

When responding to a new message, the chatbot will calculate embedding for that new message. This embedding is then compared to the embeddings in long-term memory using numpy dot-product for scoring. Highest _n_ scoring messages are included in the prompt as semantically nearest long term memories. This functionality definitely can be improved, but even this simple implementation is pretty cool!

```python
def append_ltm(msg):
    global MEMORY_LONG_TERM
    id = random.getrandbits(63)
    vector = json.dumps(get_vector_embedding(fmt_row(msg)))
    data = (id, vector, msg['datetime'], msg['name'], msg['content'])
    
    # Save to db
    c = DB_CONNECTION.cursor()
    c.execute("INSERT INTO "+ DB_TABLE +" VALUES(?, ?, ?, ?, ?)", data)
    DB_CONNECTION.commit()

    # Save to in-memory
    MEMORY_LONG_TERM.append(data)
```

```python
def ltm_top_3(msg):
    global MEMORY_LONG_TERM
    msg_vec = get_vector_embedding(fmt_row(msg))
    top_3 = list()
    
    for row in MEMORY_LONG_TERM:
        distance = numpy.dot(msg_vec, json.loads(row[1]))
        if len(top_3) < 3:
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
            top_3.pop(0)

    rtnlist = list()
    for row in top_3:
        rtnlist.append(row[1])
    return rtnlist
```
