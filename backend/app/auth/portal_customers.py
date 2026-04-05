import re

PORTAL_CUSTOMER_USER_ID_PREFIX = "portal_customer_"
PORTAL_CUSTOMER_ORG_ID_PREFIX = "portal_customer_org_"

_INN_RE = re.compile(r"\d+")


def normalize_buyer_inn(value: str | None) -> str:
    if not value:
        return ""
    return "".join(_INN_RE.findall(value))


def build_portal_customer_user_id(buyer_inn: str) -> str:
    normalized = normalize_buyer_inn(buyer_inn)
    return f"{PORTAL_CUSTOMER_USER_ID_PREFIX}{normalized}"


def build_portal_customer_org_id(buyer_inn: str) -> str:
    normalized = normalize_buyer_inn(buyer_inn)
    return f"{PORTAL_CUSTOMER_ORG_ID_PREFIX}{normalized}"


def extract_buyer_inn_from_user_id(user_id: str) -> str | None:
    if not user_id.startswith(PORTAL_CUSTOMER_USER_ID_PREFIX):
        return None
    buyer_inn = user_id.removeprefix(PORTAL_CUSTOMER_USER_ID_PREFIX)
    return buyer_inn or None
