"""
Alab-Mart Intent & Entity Parser
Extracts action intents, quantities, and target products from user queries using context.

NOTE: Product dicts (see backend/products.py) use the key "name" for the
product title - NOT "title". Every lookup in this file must use "name".
"""

import re
from typing import Dict, Any, Optional, List

CATEGORY_CODE_TO_LABEL = {
    "books": "AI Books",
    "hardware": "AI Hardware Devices",
    "assistants": "AI Smart Assistants",
}

STOPWORDS = {
    "a", "an", "and", "the", "to", "for", "with", "of", "i", "please",
    "book", "books", "assistant", "assistants", "device", "devices",
    "hardware", "item", "items", "add", "buy", "want", "need", "purchase",
    "get", "order", "put", "one", "more", "okay", "ok",
}


class IntentParser:
    def __init__(self):
        self.categories = list(CATEGORY_CODE_TO_LABEL.keys())

    def parse(self, text: str, context: Dict[str, Any], products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Parses raw query text with conversational memory support.
        """
        text_lower = text.lower().strip()

        # 1. Check End Conversation
        if any(w in text_lower for w in [
            "goodbye",
            "bye assistant",
            "stop assistant",
            "exit assistant",
            "close assistant",
            "end conversation"
        ]):
            return {
                "intent": "STOP",
                "items": [],
                "product": None,
                "quantity": 1,
                "category": None,
                "raw_text": text,
                "should_close": True
            }

        # 2. Extract Default Quantity
        quantity = self._extract_quantity(text_lower, default=context.get("last_quantity", 1))

        # 3. Detect Cart Operations & Product Targets
        intent = self._detect_intent(text_lower)

        # 4. Resolve Product Targets & Quantities using Segment-Based Extraction
        items = self._extract_products_with_quantities(text_lower, products)
        target_product = items[0]["product"] if items else None
        quantity = items[0]["quantity"] if items else quantity

        category = self._extract_category(text_lower)

        # Handle follow-up contextual phrases like "add one more" or "remove one"
        if intent == "ADD_TO_CART" and not target_product:
            target_product = context.get("last_product")
            if target_product:
                if "one more" in text_lower or "add another" in text_lower:
                    quantity = 1
                items = [{"product": target_product, "quantity": quantity}]

        if intent == "REMOVE_FROM_CART" and not target_product:
            target_product = context.get("last_product")

        return {
            "intent": intent,
            "items": items,
            "product": target_product,
            "quantity": quantity,
            "category": category,
            "raw_text": text,
            "should_close": False
        }

    def _extract_products_with_quantities(self, text: str, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Splits multi-item queries into independent segments, cleans filler spoken words,
        and matches each segment to its highest-scoring product and specific quantity.
        """
        items = []
        text_lower = text.lower()

        number_words = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
        }

        # Step 1: Split the sentence into independent segments
        raw_segments = re.split(r"\s+(?:and|,|&)\s+", text_lower)

        print("\nSegments:")
        for s in raw_segments:
            print("-", s)

        # Step 2: Process each segment independently
        for raw_segment in raw_segments:
            # Preprocess segment to remove common spoken/conversational filler words
            segment = raw_segment.strip()
            segment = re.sub(
                r"\b(add|get|buy|want|need|please|okay|ok)\b",
                "",
                segment
            ).strip()

            if not segment:
                continue

            scored_tuples = [(self._score_product(segment, p), p) for p in products]

            if not scored_tuples:
                continue

            # Step 3: Choose only the single best product for this segment
            best_score, best_product = max(scored_tuples, key=lambda x: x[0])

            if best_score < 15:
                continue

            sig_words = self._significant_words(best_product["name"])

            # Build deduplicated aliases
            aliases_set = {best_product["name"].lower()}
            for word in sig_words:
                aliases_set.add(word)

            for size in (2, 3):
                for i in range(len(sig_words) - size + 1):
                    aliases_set.add(" ".join(sig_words[i:i + size]))

            aliases = sorted(aliases_set, key=len, reverse=True)

            # Confirm alias presence using word boundaries within the raw/cleaned segment
            if not any(re.search(rf'\b{re.escape(alias)}\b', raw_segment) for alias in aliases):
                continue

            # Step 4: Extract quantity directly from the segment
            quantity = 1
            found_qty = False

            for alias in aliases:
                if not re.search(rf'\b{re.escape(alias)}\b', raw_segment):
                    continue

                # Check quantity preceding alias (e.g., "two Designing Machine Learning Systems")
                m_num_before = re.search(rf'\b(\d+)\s+{re.escape(alias)}\b', raw_segment)
                if m_num_before:
                    quantity = int(m_num_before.group(1))
                    found_qty = True
                    break

                for w_word, val in number_words.items():
                    m_word_before = re.search(rf'\b{w_word}\s+{re.escape(alias)}\b', raw_segment)
                    if m_word_before:
                        quantity = val
                        found_qty = True
                        break

                if found_qty:
                    break

                # Check quantity following alias (e.g., "Artificial Intelligence 2")
                m_num_after = re.search(rf'\b{re.escape(alias)}\s+(\d+)\b', raw_segment)
                if m_num_after:
                    quantity = int(m_num_after.group(1))
                    found_qty = True
                    break

                for w_word, val in number_words.items():
                    m_word_after = re.search(rf'\b{re.escape(alias)}\s+{w_word}\b', raw_segment)
                    if m_word_after:
                        quantity = val
                        found_qty = True
                        break

                if found_qty:
                    break

            print(f"Matched: {best_product['name']} | Qty: {quantity}")

            items.append({
                "product": best_product,
                "quantity": quantity
            })

        return items

    def _detect_intent(self, text: str) -> str:
        if any(k in text for k in ["checkout", "buy this", "buy now", "place order", "pay"]):
            return "CHECKOUT"

        if any(k in text for k in ["what's in my cart", "show cart", "view cart", "check cart"]):
            return "VIEW_CART"

        if any(k in text for k in ["remove", "delete", "take out"]):
            return "REMOVE_FROM_CART"

        if any(k in text for k in ["add", "put", "need", "get", "buy", "want", "one more", "another", "purchase"]):
            return "ADD_TO_CART"

        if any(k in text for k in ["cheaper", "under", "below", "search", "show", "find", "looking for"]):
            return "SEARCH_FILTER"

        return "UNKNOWN"

    def _extract_quantity(self, text: str, default: int = 1) -> int:
        numbers_map = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
        }
        for word, val in numbers_map.items():
            if re.search(r'\b' + word + r'\b', text):
                return val

        match = re.search(r'\b(\d+)\b', text)
        if match:
            return int(match.group(1))
        return default

    def _normalize(self, text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    def _significant_words(self, text: str) -> List[str]:
        return [w for w in self._normalize(text).split() if w not in STOPWORDS and not w.isdigit()]

    def _score_product(self, query: str, product: Dict[str, Any]) -> int:
        """Fuzzy relevance score between free-text query and a product record."""
        query_norm = self._normalize(query)
        query_words = self._significant_words(query)
        name = self._normalize(product["name"])
        brand = self._normalize(product.get("brand", ""))
        category = self._normalize(product.get("category", ""))
        name_words = name.split()
        brand_words = brand.split()

        score = sum(5 for w in query_words if w in name_words)
        score += sum(2 for w in query_words if w in brand_words)
        score += sum(1 for w in query_words if w in category)

        # Reward contiguous phrase overlap (e.g. "deep learning")
        for size in range(min(5, len(query_words)), 1, -1):
            for i in range(0, len(query_words) - size + 1):
                phrase = " ".join(query_words[i:i + size])
                if phrase in name:
                    score += size * 6

        if name and name in query_norm:
            score += 25
        if brand and brand in query_norm:
            score += 5
        return score

    def _extract_category(self, text: str) -> Optional[str]:
        if "book" in text:
            return "books"
        if "hardware" in text or "device" in text or "board" in text or "jetson" in text or "laptop" in text:
            return "hardware"
        if "assistant" in text or "speaker" in text or "alexa" in text or "echo" in text:
            return "assistants"
        return None