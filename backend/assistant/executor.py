"""
Alab-Mart Execution Engine
Executes backend store actions (cart modifications, query filters) and constructs natural spoken replies.
"""

from typing import Dict, Any, List, Tuple, Optional

CATEGORY_CODE_TO_LABEL = {
    "books": "AI Books",
    "hardware": "AI Hardware Devices",
    "assistants": "AI Smart Assistants",
}


class StoreExecutor:
    def __init__(self, products: List[Dict[str, Any]]):
        self.products = products

    def execute(self, parsed_intent: Dict[str, Any], session_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        Executes intent against shopping cart state.
        Returns: (Assistant Spoken Reply, Updated Session Data, Executed Action Payload)
        """
        intent = parsed_intent["intent"]
        product = parsed_intent["product"]
        quantity = parsed_intent["quantity"]
        category = parsed_intent["category"]
        cart = session_data.get("cart", [])

        # Temporary debugging trace
        print("\n==============================")
        print("INTENT :", intent)
        print("PRODUCT:", product["name"] if product else None)
        print("CART BEFORE:", [i["name"] for i in cart])
        print("==============================")

        action_executed = None
        reply = ""

        # 1. ADD TO CART
        if intent == "ADD_TO_CART":
            print("\nPARSED ITEMS:")
            for item in parsed_intent.get("items", []):
                print(item["product"]["name"], "Qty:", item["quantity"])
            items = parsed_intent.get("items", [])

            if not items:
                if not product:
                    reply = "I couldn't find that AI product. Could you name it a little more clearly?"
                else:
                    items = [
                        {
                            "product": product,
                            "quantity": quantity
                        }
                    ]

            if items:
                added_products = []

                for item in items:
                    prod = item["product"]
                    qty = item["quantity"]

                    existing = next(
                        (c for c in cart if c["id"] == prod["id"]),
                        None
                    )

                    if existing:
                        existing["quantity"] += qty
                    else:
                        cart.append({**prod, "quantity": qty})

                    added_products.append(f"{qty} × {prod['name']}")

                session_data["last_product"] = items[-1]["product"]
                session_data["last_quantity"] = items[-1]["quantity"]

                reply = "Added " + ", ".join(added_products) + " to your cart."
                action_executed = {
                    "type": "ADD_TO_CART",
                    "cart": cart
                }

        # 2. REMOVE FROM CART
        elif intent == "REMOVE_FROM_CART":
            target = product or session_data.get("last_product")
            if not target:
                if cart:
                    removed = cart.pop()
                    reply = f"Removed {removed['name']} from your cart."
                    action_executed = {"type": "REMOVE_FROM_CART", "cart": cart}
                else:
                    reply = "Your cart is currently empty."
            else:
                cart = [item for item in cart if item["id"] != target["id"]]
                reply = f"Removed {target['name']} from your cart."
                action_executed = {"type": "REMOVE_FROM_CART", "cart": cart}

        # 3. SEARCH AND FILTER
        elif intent == "SEARCH_FILTER":
            max_price = self._extract_price(parsed_intent["raw_text"])
            matches = self.products

            if category:
                matches = [p for p in matches if p["category"].lower() == category.lower()]
            if max_price:
                matches = [p for p in matches if p["price"] <= max_price]

            if matches:
                top_match = matches[0]
                session_data["last_product"] = top_match
                label = CATEGORY_CODE_TO_LABEL.get(category, "products")
                reply = f"I found {len(matches)} {label} for you. For example, {top_match['name']} priced at Rs.{top_match['price']}."
                action_executed = {"type": "SEARCH", "category": category, "results": matches}
            else:
                reply = "I couldn't find any products matching those criteria."

        # 4. VIEW CART
        elif intent == "VIEW_CART":
            if not cart:
                reply = "Your cart is currently empty."
            else:
                summary = ", ".join([f"{i['quantity']} {i['name']}" for i in cart])
                total = sum(i["price"] * i["quantity"] for i in cart)
                reply = f"You have {summary} in your cart. Total is Rs.{total}."

        # 5. CHECKOUT
        elif intent == "CHECKOUT":
            if not cart:
                reply = "Your cart is empty. Add some AI items before checking out."
            else:
                reply = "Proceeding to checkout now."
                action_executed = {"type": "CHECKOUT"}

        # 6. STOP / EXIT
        elif intent == "STOP":
            reply = "Thank you for shopping with Alab-Mart. Goodbye!"

        # 7. UNKNOWN / FALLBACK
        elif intent == "UNKNOWN":
            reply = ""

        else:
            reply = ""

        session_data["cart"] = cart

        # Temporary debugging trace
        print("CART AFTER :", [i["name"] for i in session_data["cart"]])
        print("==============================\n")

        return reply, session_data, action_executed

    def _extract_price(self, text: str) -> Optional[int]:
        import re
        match = re.search(r'(?:under|below|less than)\s*(?:rs\.?|₹)?\s*(\d+)', text.lower())
        if match:
            return int(match.group(1))
        return None