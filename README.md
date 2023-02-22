# Chatbot I call PuroGPT

This is discord chatbot that use OpenAI API for generating responses.

Idea is to use OpenAI text completion models for complex "AI". It should be possible to utilise python
scripting and prompt templating to create these additional functions on top of Davinci text completion:

* Multi-step processing. Chatbot should recognize the need to process the request in multiple steps.
* Internal reasoning. Chatbot should use "message-to-self" type information to help guide itself
  in the multi-step process of generating an response.
* External requests. Chatbot should recognize the need for external resources for facts. The python
  script then can process these requests for facts, use third parties as necessary, and help the
  text completion model step-by-step to create the required complex response.

## TODO:

- [X] Short term chatroom-wide memory.
- [X] Long term context aware memory.
- [ ] The concept of conversations.
- [ ] Context aware wikipedia facts.
- [ ] Context aware wolfram-alpha facts.

## Installing

1. Install latest Python 3.
2. Install Discord python library: pip install -U discord.py
3. Install OpenAI python library: pip install -U openai
4. Install Numpy python library: pip install -U numpy
5. Fill the configuration files and enjoy!

## How this works?

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
