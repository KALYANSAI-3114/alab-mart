import json
import os
import re
import urllib.error
import urllib.request
from typing import Dict, Iterable, List, Optional


AGENT_NAME = "Alab"
OLLAMA_URL = os.environ.get("ALAB_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.environ.get("ALAB_OLLAMA_MODEL", "qwen2.5:3b")

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

ADD_WORDS = {"add", "buy", "want", "need", "purchase", "get", "order"}
DELETE_WORDS = {"delete", "remove", "drop", "cancel"}
UPDATE_WORDS = {"update", "change", "set", "make", "increase", "decrease"}
CHECKOUT_WORDS = {"checkout", "bill", "billing", "pay", "payment", "show"}
FINISH_WORDS = {"no", "nope", "nothing", "done", "finish", "finished", "enough"}
FINISH_PHRASES = {
    "nothing else",
    "thats all",
    "that's all",
    "that is all",
    "no thanks",
    "no thank you",
    "i am done",
    "i m done",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "the",
    "to",
    "for",
    "with",
    "of",
    "i",
    "please",
    "book",
    "books",
    "assistant",
    "assistants",
    "device",
    "devices",
    "hardware",
    "item",
    "items",
    *ADD_WORDS,
    *DELETE_WORDS,
    *UPDATE_WORDS,
    *CHECKOUT_WORDS,
    *FINISH_WORDS,
}


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def significant_words(text: str) -> List[str]:
    return [word for word in normalize(text).split() if word not in STOPWORDS and not word.isdigit()]


def extract_quantity(text: str) -> int:
    match = re.search(r"\b(\d+)\b", text)
    if match:
        return max(1, min(10, int(match.group(1))))
    for word in normalize(text).split():
        if word in NUMBER_WORDS:
            return NUMBER_WORDS[word]
    return 1


def infer_action(text: str) -> str:
    words = set(normalize(text).split())
    if words & DELETE_WORDS:
        return "delete"
    if words & UPDATE_WORDS:
        return "update"
    return "add"


def is_finish_request(text: str) -> bool:
    normalized = normalize(text)
    if normalized in FINISH_WORDS:
        return True
    return any(normalize(phrase) in normalized for phrase in FINISH_PHRASES)


def score_product(query: str, product: Dict) -> int:
    query_norm = normalize(query)
    query_words = significant_words(query)
    name = normalize(product["name"])
    brand = normalize(product.get("brand", ""))
    category = normalize(product.get("category", ""))
    name_words = name.split()
    brand_words = brand.split()

    score = sum(5 for word in query_words if word in name_words)
    score += sum(2 for word in query_words if word in brand_words)
    score += sum(1 for word in query_words if word in category)
    score += sum(1 for word in query_words if word in name)

    for size in range(min(5, len(query_words)), 1, -1):
        for index in range(0, len(query_words) - size + 1):
            phrase = " ".join(query_words[index:index + size])
            if phrase in name:
                score += size * 6

    if name in query_norm:
        score += 25
    if brand and brand in query_norm:
        score += 5
    return score


def split_order_parts(text: str) -> List[str]:
    cleaned = text.lower().replace("&", " and ")
    return [part.strip() for part in re.split(r"\s+(?:and|then|also)\s+|,", cleaned) if part.strip()]


def best_product_match(query_part: str, products: Iterable[Dict]):
    candidates = sorted(products, key=lambda product: score_product(query_part, product), reverse=True)
    if not candidates:
        return None, 0
    return candidates[0], score_product(query_part, candidates[0])


def product_summary(products: List[Dict]) -> str:
    return "\n".join(f'{p["id"]}: {p["name"]} ({p.get("brand", "")}, {p.get("category", "")})' for p in products)


def extract_json_object(text: str) -> Optional[Dict]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def ollama_plan(text: str, products: List[Dict]) -> Optional[Dict]:
    if os.environ.get("ALAB_DISABLE_OLLAMA") == "1":
        return None
    if is_finish_request(text):
        return None

    prompt = f"""
You are Alab, a shopping voice agent. Convert the user request into cart actions.
Return strict JSON only:
{{
  "actions": [
    {{"action": "add|delete|update", "product_id": 1, "quantity": 1}}
  ],
  "checkout": true|false
}}

Rules:
- Use add for buy/want/need/add.
- Use delete for remove/delete/cancel.
- Use update for update/change/set quantity.
- product_id must come from the product list.
- quantity must be 1-10. For delete, quantity can be 0.
- If no confident product exists, actions must be [].

Products:
{product_summary(products)}

User request: {text}
"""
    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    parsed = extract_json_object(data.get("response", ""))
    if not parsed or not isinstance(parsed.get("actions"), list):
        return None
    return parsed


def rule_plan(text: str, products: List[Dict]) -> Dict:
    actions = []
    unmatched = []
    used_ids = set()

    for part in split_order_parts(text):
        part_words = set(normalize(part).split())
        if part_words and part_words <= CHECKOUT_WORDS:
            continue
        if not significant_words(part):
            continue
        product, score = best_product_match(part, products)
        if product and score > 1 and product["id"] not in used_ids:
            used_ids.add(product["id"])
            action = infer_action(part)
            actions.append(
                {
                    "action": action,
                    "product_id": product["id"],
                    "quantity": 0 if action == "delete" else extract_quantity(part),
                }
            )
        else:
            unmatched.append(part)

    lowered = text.lower()
    checkout = bool(set(normalize(lowered).split()) & CHECKOUT_WORDS)
    return {"actions": actions, "checkout": checkout and bool(actions), "unmatched": unmatched}


def product_by_id(products: List[Dict], product_id: int):
    return next((product for product in products if product["id"] == product_id), None)


def enrich_actions(plan: Dict, products: List[Dict]) -> List[Dict]:
    enriched = []
    source_text = plan.get("source_text", "")
    for raw in plan.get("actions", []):
        product = product_by_id(products, int(raw.get("product_id", 0)))
        action = raw.get("action", "add")
        if action not in {"add", "delete", "update"} or not product:
            continue
        if source_text and score_product(source_text, product) <= 1:
            continue

        item_quantity = max(0, min(10, int(raw.get("quantity", 1))))
        if item_quantity == 0 and action != "delete":
            item_quantity = 1

        action_type = "ADD_TO_CART" if action == "add" else ("REMOVE_FROM_CART" if action == "delete" else "UPDATE_QUANTITY")
        
        enriched.append({
            "type": action_type,
            "action": action,
            "product_id": product["id"],
            "quantity": item_quantity,
            "product": product
        })
    return enriched


def apply_cart_actions(cart: List[Dict], actions: List[Dict]) -> List[Dict]:
    """
    Cart Engine: Applies actions deterministically to modify current session cart.
    """
    updated_cart = [dict(item) for item in cart]

    for action_item in actions:
        action = action_item["action"]
        product = action_item["product"]
        qty = action_item["quantity"]
        p_id = product["id"]

        existing = next((x for x in updated_cart if x.get("id") == p_id or x.get("product_id") == p_id), None)

        if action == "add":
            if existing:
                existing["quantity"] += qty
            else:
                new_item = dict(product)
                new_item["quantity"] = qty
                updated_cart.append(new_item)

        elif action == "delete":
            updated_cart = [x for x in updated_cart if x.get("id") != p_id and x.get("product_id") != p_id]

        elif action == "update":
            if existing:
                if qty <= 0:
                    updated_cart = [x for x in updated_cart if x.get("id") != p_id and x.get("product_id") != p_id]
                else:
                    existing["quantity"] = qty

    return updated_cart


def generate_natural_voice_reply(user_text: str, actions: List[Dict], checkout: bool) -> str:
    """
    Generates a natural, friendly 1-sentence reply using Ollama based on cart modifications.
    """
    if not actions:
        return "I could not confidently find that product. Please say the product name once more."

    if os.environ.get("ALAB_DISABLE_OLLAMA") == "1":
        return default_reply(actions, checkout)

    summary_list = []
    for act in actions:
        p_name = act["product"]["name"]
        a_type = act["action"]
        qty = act["quantity"]
        if a_type == "add":
            summary_list.append(f"Added {qty} of {p_name}")
        elif a_type == "delete":
            summary_list.append(f"Removed {p_name}")
        elif a_type == "update":
            summary_list.append(f"Updated {p_name} quantity to {qty}")

    action_summary = "; ".join(summary_list)

    prompt = f"""
You are Alab, a friendly voice assistant for an e-commerce website.
Generate a concise, friendly 1-sentence response confirming the cart changes.

User said: "{user_text}"
Cart actions performed: {action_summary}
Checkout requested: {checkout}

Rules:
- Keep it to exactly 1 sentence.
- Sound natural and helpful for text-to-speech.
- End with a brief prompt asking if they need anything else (unless checking out).
"""
    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
            reply_text = data.get("response", "").strip()
            if reply_text:
                return reply_text
    except Exception:
        pass

    return default_reply(actions, checkout)


def default_reply(actions: List[Dict], checkout: bool) -> str:
    if not actions:
        return "I could not confidently find that product. Please say the product name once more."

    counts = {"add": 0, "delete": 0, "update": 0}
    for action in actions:
        counts[action["action"]] += 1

    parts = []
    if counts["add"]:
        parts.append("added products to your cart")
    if counts["delete"]:
        parts.append("removed products from your cart")
    if counts["update"]:
        parts.append("updated your cart")

    reply = f"Done, I {' and '.join(parts)}."
    if checkout:
        reply += " I will open the bill now."
    else:
        reply += " Anything else you would like?"
    return reply


def handle_voice_order(text: str, products: List[Dict], session: Optional[Dict] = None) -> Dict:
    """
    Main pipeline: Voice -> Intent -> Cart Engine -> Persistence -> Voice Reply
    """
    if session is None:
        session = {}

    # Initial session setup
    current_cart = session.get("cart", [])

    # First time greeting check
    if session.get("first_time", False):
        session["first_time"] = False
        return {
            "agent": AGENT_NAME,
            "intent": "greeting",
            "reply": "Hi, I'm Alab. What would you like to buy today?",
            "cart": current_cart,
            "listen_again": True
        }

    # Process finish request
    if is_finish_request(text):
        reply = "Sure, here is your final cart. Please review it, then you can continue to payment."
        return {
            "agent": AGENT_NAME,
            "intent": "finish",
            "reply": reply,
            "cart": current_cart,
            "actions": [],
            "checkout": False,
            "listen_again": False
        }

    # Intent planning
    plan = ollama_plan(text, products) or rule_plan(text, products)
    plan["source_text"] = text
    actions = enrich_actions(plan, products)
    checkout = bool(plan.get("checkout")) and bool(actions)

    # Modify cart using Cart Engine
    updated_cart = apply_cart_actions(current_cart, actions)

    # Persist updated cart in session
    session["cart"] = updated_cart

    # Generate LLM response after cart action completes
    reply = generate_natural_voice_reply(text, actions, checkout)

    return {
        "agent": AGENT_NAME,
        "intent": "cart_action" if actions else "unknown",
        "reply": reply,
        "cart": updated_cart,
        "actions": actions,
        "checkout": checkout,
        "listen_again": not checkout and bool(actions)
    }