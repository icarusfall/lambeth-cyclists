"""How we call Claude, in one place.

Every rule here is a correctness requirement on current models rather than a
preference, and each was learned by something breaking:

- Sampling parameters (temperature/top_p/top_k) are gone from the SDK 1.x
  signatures and rejected by Sonnet 5.
- Adaptive thinking is on by default, so a response leads with a thinking
  block. Never index content[0]; select text blocks by type.
- Server-side tools (web_search, web_fetch) can end a turn with
  stop_reason "pause_turn". Parsing that yields a schema-valid object full of
  stub text, which looks like an answer. Resume until the turn really ends.
"""

MODEL = "claude-sonnet-5"

# What the model fills fields with when it has not actually finished. Treated
# as failure rather than content: a stub that reaches Notion looks filed.
STUB_VALUES = frozenset({"placeholder", "todo", "n/a", "none", "unknown", "tbc", ""})


def response_text_of(message) -> str:
    """Concatenate the text blocks of a response, skipping thinking blocks."""
    return "".join(b.text for b in message.content if b.type == "text").strip()


def looks_like_stub(*values: str) -> bool:
    """True if any value is the model's way of saying it did not finish."""
    return any((v or "").strip().lower() in STUB_VALUES for v in values)


def parse_resuming(client, **kwargs):
    """messages.parse(), resumed across pause_turn.

    `client` is an anthropic.Anthropic. Pass `timeout` to override the
    client's default for this call; everything else goes to messages.parse.
    """
    convo = list(kwargs.pop("messages"))
    timeout = kwargs.pop("timeout", None)
    api = client.with_options(timeout=timeout) if timeout else client
    response = None
    for _ in range(5):
        response = api.messages.parse(messages=convo, **kwargs)
        if response.stop_reason != "pause_turn":
            return response
        convo = convo + [{"role": "assistant", "content": response.content}]
    return response
