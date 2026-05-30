"""FraudShield — Input Validators"""

VALID_CATEGORIES = [
    "entertainment", "food_dining", "gas_transport", "grocery_net",
    "grocery_pos", "health_fitness", "home", "kids_pets",
    "misc_net", "misc_pos", "personal_care", "shopping_net",
    "shopping_pos", "travel",
]

VALID_STATUSES = {"SAFE", "REVIEW", "FRAUD"}
VALID_ROLES = {"admin", "analyst", "viewer"}


def validate_category(cat: str) -> bool:
    return cat.lower().replace(" ", "_") in VALID_CATEGORIES


def validate_status(status: str) -> bool:
    return status.upper() in VALID_STATUSES


def validate_role(role: str) -> bool:
    return role.lower() in VALID_ROLES


def validate_amount(amt: float) -> bool:
    return isinstance(amt, (int, float)) and amt > 0 and amt == amt  # not NaN
