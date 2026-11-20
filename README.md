# tacit-voice

A voice AI agent built with [LiveKit Agents](https://docs.livekit.io/agents/) running on [LiveKit Cloud](https://cloud.livekit.io/) (Frankfurt region). The pipeline uses three LiveKit Inference models with no extra API keys:

| Stage | Model |
|-------|-------|
| STT | AssemblyAI `assemblyai-stt-3-7-realtime-agent` |
| LLM | Google `gemma-4-31b-it` |
| TTS | Fish Audio `s2.1-pro` |

## Latency measurement

Every agent turn appends one JSON line to `metrics/turns.jsonl` with five latency fields (all in seconds):

| Field | What it measures |
|-------|-----------------|
| `end_of_utterance_delay_s` | VAD end-of-speech → turn decision |
| `transcription_delay_s` | VAD end-of-speech → final STT transcript |
| `llm_ttft_s` | LLM request sent → first output token |
| `tts_ttfb_s` | First LLM token → first TTS audio chunk |
| `e2e_latency_s` | User stops speaking → agent first audio |

Data comes from `ChatMessage.metrics` via the `conversation_item_added` event (SDK-native, no instrumentation in the pipeline). The `RUN_LABEL` env var (default `"A"`) tags each session so runs can be compared.

```bash
# collect a session
RUN_LABEL=A lk agent console

# print p50/p95 per metric, grouped by run label
uv run python scripts/report.py
```

## Run A vs Run B results

Both runs: same models, same region, ~12 turns each. Samples are small so treat these as directional, not statistically conclusive.

**Run A** — baseline (`max_endpointing_delay` at streaming default of 2.5 s)

| Metric | n | p50 ms | p95 ms |
|--------|---|-------:|-------:|
| EOU delay | 12 | 389 | 2503 |
| STT / transcription delay | 12 | 371 | 1294 |
| LLM time-to-first-token | 15 | 290 | 773 |
| TTS time-to-first-byte | 15 | 215 | 320 |
| **Total response latency** | **12** | **1400** | **3093** |

**Run B** — after change (`max_delay: 1.0` s in `endpointing`)

| Metric | n | p50 ms | p95 ms |
|--------|---|-------:|-------:|
| EOU delay | 11 | 483 | 628 |
| STT / transcription delay | 11 | 477 | 618 |
| LLM time-to-first-token | 12 | 226 | 620 |
| TTS time-to-first-byte | 12 | 213 | 305 |
| **Total response latency** | **11** | **1082** | **2193** |

**What changed and why.** Run A's EOU p95 of 2503 ms was at the streaming-default `max_delay` ceiling — turns where the LiveKit TurnDetector never reached confidence before the timeout. Run B adds one key to `TurnHandlingOptions` in `src/agent.py`:

```python
endpointing={"max_delay": 1.0},
```

This caps the worst-case end-of-turn wait to 1 s. The turn detector still fires early on clean utterances (EOU p50 barely moved), so normal turns are unaffected. The tail drops: EOU p95 −75 %, total p95 −29 %. The tradeoff is that very long pauses are now cut off sooner; adjust upward if the agent interrupts mid-thought.

> **Note on sample size.** ~12 turns per run is enough to see the tail effect clearly (p95 at the ceiling is unambiguous) but too few for stable p50s. Collect 100+ turns before drawing conclusions about median latency.

## Running the agent

```bash
# talk to it locally (mic + speaker)
lk agent console

# connect to LiveKit Cloud for a frontend or phone call
lk agent dev

# deploy to LiveKit Cloud
lk agent deploy
```

## Project layout

```
src/agent.py          # agent definition + per-turn metrics hook
scripts/report.py     # print p50/p95 from metrics/turns.jsonl
metrics/turns.jsonl   # raw per-turn JSONL (committed as evidence)
scenarios.yaml        # simulation scenarios
```

## License

MIT
