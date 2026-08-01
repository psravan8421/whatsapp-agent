# WhatsApp Intelligent Notification Router

A pure-Python AI agent that reads incoming WhatsApp messages from a JSON file,
classifies each one with an LLM (OpenAI GPT, Groq, or Anthropic Claude), decides
`notify` / `digest` / `mute`, and writes the results to a CSV.

## Project structure

```
project/
├── main.py            # CLI: load JSON -> process -> save CSV
├── processor.py       # message loop, prompt building, heuristic fallback
├── llm_client.py      # OpenAI/Groq/Claude API calls, retries, JSON validation
├── utils.py           # JSON parsing + logging helpers
├── requirements.txt
├── README.md
├── input.json         # sample input
└── output.csv         # sample output
```

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Set an API key (any one of the three):

```bash
export OPENAI_API_KEY="sk-..."          # OpenAI
export GROQ_API_KEY="gsk_..."           # Groq (OpenAI-compatible, free tier)
export ANTHROPIC_API_KEY="sk-ant-..."   # Claude
```

When several keys are present the order of preference is OpenAI -> Groq ->
Anthropic; override it with `LLM_PROVIDER=groq`.

## Run

```bash
python main.py input.json                    # writes output.csv
python main.py input.json -o results.csv     # custom output path
python main.py input.json --no-llm           # offline heuristic classifier only
```

If no API key is configured (or the LLM fails after all retries), the pipeline
falls back to a built-in rule-based classifier so it always produces a CSV.

## Input format

`input.json` is either a list of messages or an object with a `messages` list
plus an optional shared `user_profile`. Each message may contain:

| Field | Description |
| --- | --- |
| `message_id` | Unique message identifier (required) |
| `content` | `{type, text \| caption \| transcript, ...}` – text/image/audio metadata |
| `sender` | `{sender_id, name, is_contact, trust_level}` |
| `user_profile` | Per-message override of the shared user profile |
| `group_info` | Optional group metadata |
| `business_info` | Optional business metadata |
| `forwarded_count` | Number of times the message was forwarded |
| `history` | Past messages `[{message_id, text, timestamp}, ...]` |

## Output format

`output.csv` columns (the committed sample was generated with Groq
`llama-3.3-70b-versatile`):

`message_id, action, message_type, reason, confidence, evidence_message_ids`

`evidence_message_ids` is a comma-separated list of the history message IDs that
supported the decision.

## LLM integration

`llm_client.call_llm(prompt: str) -> dict`

- Temperature `0.3`
- OpenAI/Groq calls use `response_format={"type": "json_object"}` for strict JSON
- Responses are parsed defensively (code fences, surrounding prose, trailing commas)
- Fields are validated and normalised: `action` is forced into
  `notify|digest|mute`, `confidence` is clamped to `[0, 1]`,
  `evidence_message_ids` is coerced to a list of strings
- Retries up to 3 attempts with linear backoff on network, HTTP, or JSON errors

The exact router prompt lives in `processor.ROUTER_PROMPT` and is sent together
with the message JSON as `INPUT`.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | – | OpenAI credentials |
| `GROQ_API_KEY` | – | Groq credentials |
| `ANTHROPIC_API_KEY` | – | Claude credentials |
| `LLM_PROVIDER` | auto | Force `openai`, `groq`, or `anthropic` |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model name |
| `ANTHROPIC_MODEL` | `claude-3-5-sonnet-latest` | Claude model name |
| `LLM_MAX_ATTEMPTS` | `3` | Retry attempts |
| `LLM_RETRY_BACKOFF` | `2` | Backoff seconds (linear) |
| `LLM_TIMEOUT` | `60` | Request timeout in seconds |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Decision rules

- **notify** – urgent, important, from a trusted sender
- **digest** – useful but not urgent
- **mute** – spam, scam, repetitive, heavily forwarded, suspicious links
