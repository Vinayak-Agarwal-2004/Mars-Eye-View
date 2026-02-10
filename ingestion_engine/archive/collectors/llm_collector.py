import json
import os
import sys
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(".env.local", override=False)
    load_dotenv(".env", override=False)
except Exception:
    pass

OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / 'data'
OUTPUT_FILE = DATA_DIR / 'interactions' / 'raw_llm_events.json'
RSS_INPUT_FILE = DATA_DIR / 'interactions' / 'raw_rss_events.json'

PROMPT_TEMPLATE = """
Analyze the following news text and extract international interactions between nations.
Focus on: Territorial disputes, diplomatic meetings, trade agreements, military exercises, humanitarian aid, etc.

Return a JSON object with an 'events' array containing objects with:
- name: Short title of interaction
- type: Category for this interaction.
- subtype: Specific subtype (e.g. summit, tariff, border_crisis)
- participants: Array of country names involved (use common country names)
- description: Brief summary
- date: Date of event (YYYY-MM-DD) if available
- topology: mesh | star | chain (optional)
- hub: ISO3 country code if topology is star (optional)
- confidence: 0.0 to 1.0
- visualization_type: "geodesic" (arc between countries) or "dot" (single location marker)
- arc_style: "dashed" | "solid" | "dotted" (for geodesic; use solid for ongoing, dashed for tentative)
- location: For "dot" only: {"lat": number, "lon": number} or {"iso": "USA"}; omit for geodesic
- toast_message: One-line short message for user notification
- toast_type: "info" | "success" | "warning" | "error"

Rules:
- Prefer these base categories when they fit: disputes, meetings, agreements, sports, trade, military, humanitarian, cultural, other.
- You MAY introduce new categories when clearly useful (e.g. space, cyber, climate, sanctions_regime). Keep new category names short (snake_case or single words).
- Avoid using "other" unless none of the categories fit; when you do, include an additional field: other_reason (short string, <= 12 words).

Text to analyze:
{text}
"""

def _call_openrouter(text):
    if not OPENROUTER_API_KEY:
        return None, None
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a geopolitical analyst extracting structured data."},
            {"role": "user", "content": PROMPT_TEMPLATE.format(text=text)}
        ],
        "response_format": {"type": "json_object"}
    }
    try:
        r = requests.post(OPENROUTER_URL, headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}, json=payload, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            return None, r.status_code
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content'], None
    except Exception as e:
        print(f"OpenRouter: {e}")
        return None, getattr(getattr(e, "response", None), "status_code", None)


def _call_groq(text):
    if not GROQ_API_KEY:
        return None
    try:
        r = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}, json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "You are a geopolitical analyst extracting structured data."},
                {"role": "user", "content": PROMPT_TEMPLATE.format(text=text)}
            ],
            "response_format": {"type": "json_object"}
        }, timeout=60)
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"Groq: {e}")
        return None


def query_llm(text):
    if not OPENROUTER_API_KEY and not GROQ_API_KEY:
        print("Error: Set OPENROUTER_API_KEY or GROQ_API_KEY.")
        return None
    content, status = _call_openrouter(text)
    if content:
        return content
    if status == 429:
        print("OpenRouter rate limited, trying Groq...")
    if GROQ_API_KEY:
        return _call_groq(text)
    return None

def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="LLM Collector for Interactions")
    parser.add_argument("--from-rss", action="store_true", help="Process raw_rss_events.json")
    parser.add_argument("--limit", type=int, default=5, help="Limit number of RSS items to process")
    parser.add_argument("--output", type=str, default=str(OUTPUT_FILE), help="Output JSON path")
    parser.add_argument("text", nargs="*", help="Raw text to analyze (if not using --from-rss)")
    return parser.parse_args()


def main():
    print("LLM Collector initialized.")
    args = parse_args()

    if not OPENROUTER_API_KEY and not GROQ_API_KEY:
        print("\n⚠️  MISSING API KEY ⚠️")
        print("Set OPENROUTER_API_KEY and/or GROQ_API_KEY in .env or .env.local")
        sys.exit(1)

    output_path = Path(args.output)

    if args.from_rss:
        if not RSS_INPUT_FILE.exists():
            print(f"RSS input not found: {RSS_INPUT_FILE}")
            sys.exit(1)
        with open(RSS_INPUT_FILE, 'r') as f:
            rss_events = json.load(f)

        results = []
        for item in rss_events[: args.limit]:
            text = item.get('raw_text') or f"{item.get('title','')} {item.get('description','')}"
            llm_resp = query_llm(text)
            if not llm_resp:
                continue
            try:
                parsed = json.loads(llm_resp)
                for ev in parsed.get('events', []):
                    ev['source_url'] = item.get('url')
                    ev['source_type'] = item.get('source')
                    results.append(ev)
            except Exception as e:
                print(f"Failed to parse LLM response: {e}")

        output = {"events": results}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"Saved {len(results)} events to {output_path}")
        return

    if args.text:
        text = " ".join(args.text)
        result = query_llm(text)
        print("\n--- LLM Result ---\n")
        print(result)
        return

    print("No input provided. Use --from-rss or pass text.")

if __name__ == '__main__':
    main()
