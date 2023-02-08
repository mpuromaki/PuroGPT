# PuroGPT

Idea is to use OpenAI text completion models for complex "AI". It should be possible to utilise python
scripting and prompt templating to create these additional functions on top of Davinci text completion:

* Multi-step processing. PuroGPT should recognize the need to process the request in multiple steps.
* Internal reasoning. PuroGPT should use "message-to-self" type information to help guide itself
  in the multi-step process of generating an response.
* External requests. PuroGPT should recognize the need for external resources for facts. The python
  script then can process these requests for facts, use third parties as necessary, and help the
  text completion model step-by-step to create the required complex response.

## Installing

1. Install latest Python 3.
2. Install Discord python library: pip install -U discord.py
3. Install OpenAI python library: pip install -U openai

