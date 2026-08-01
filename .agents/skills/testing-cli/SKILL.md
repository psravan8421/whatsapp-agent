---
name: testing-cli
description: How to run and end-to-end test the WhatsApp Intelligent Notification Router CLI (main.py) locally, including LLM, offline and failure paths.
---

# Testing the notification router CLI

## Environment
- Python 3.10+, only `pandas` and `requests` are needed (`pip install -r requirements.txt`); on the
  standard Devin box these are already installed system-wide, so no venv is usually required.
- No services, no DB, no UI — everything is a shell run, so do NOT screen-record; collect stdout/stderr
  and the produced CSVs as evidence instead.

## Running
```bash
python3 main.py input.json -o /tmp/out.csv     # LLM path (needs an API key env var)
python3 main.py input.json --no-llm            # offline heuristic
python3 main.py                                # defaults: input.json -> output.csv (dirties the repo; back it up)
```

## Providers / env vars (llm_client.py)
Provider is chosen by key precedence: `OPENAI_API_KEY` > `GROQ_API_KEY` > `ANTHROPIC_API_KEY`;
`LLM_PROVIDER=groq|openai|anthropic` forces one. Other tunables: `LLM_MAX_ATTEMPTS` (default 3),
`LLM_RETRY_BACKOFF` (default 2s — set to `0` so failure tests finish fast), `LLM_TIMEOUT`,
`GROQ_MODEL`/`OPENAI_MODEL`/`ANTHROPIC_MODEL`, `LOG_LEVEL`.
Never write API keys into repo files; pass them inline as `GROQ_API_KEY=... python3 main.py ...`.

## Devin Secrets Needed
- `GROQ_API_KEY` (or `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) for the real-LLM path. Without any key the
  CLI still works via the heuristic, so offline coverage is possible with no secrets.

## What to assert
- CSV header exactly and in order: `message_id,action,message_type,reason,confidence,evidence_message_ids`.
- Row count == number of input messages; `action` ∈ {notify,digest,mute}; `confidence` numeric in [0,1].
- LLM path really used the LLM: logs must NOT contain "No API key found" or "using heuristic fallback",
  and reason strings should differ from a `--no-llm` run of the same input.
- Failure path: bogus key + `LLM_RETRY_BACKOFF=0` should log `LLM attempt N/3 failed` 3× per message,
  then `using heuristic fallback`, exit 0, and produce a CSV identical to the `--no-llm` output.
- Error cases must exit 1 with a single log line and no traceback: missing file, malformed JSON,
  JSON without a messages list, empty messages list (the last one errors in main.py with
  "No messages found", the others in utils.load_json_file / processor.extract_messages).
- Accepted input shapes: `{"messages": [...]}` (also `data`/`items`/`inbox`), a bare list of messages,
  or a single message object containing `message_id`.
- LLM classifications are non-deterministic (temperature 0.3); only assert on unambiguous cases
  (obvious scam/spam → mute, family emergency → notify) and re-run to check stability rather than
  pinning every row.
