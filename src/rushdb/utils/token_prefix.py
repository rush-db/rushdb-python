import re
from typing import Dict, Optional, Tuple

PlanPrefix = {
    "initial": "in",
    "extended": "ex",
    "fullFeatured": "ff",
}


def extract_mixed_properties_from_token(
    prefixed_token: str,
) -> Tuple[Optional[Dict[str, bool]], str]:
    matched = re.match(r"^([a-z]{2})_([01]{4}\d*)_(.+)$", prefixed_token)
    if not matched:
        return None, prefixed_token

    prefix, bits, raw = matched.groups()
    plan = next((p for p, plan in PlanPrefix.items() if plan == prefix), None)
    if plan is None:
        return None, prefixed_token

    b_custom, b_managed, b_self = tuple(bits[:3])
    settings = {
        "planType": plan,
        "customDB": b_custom == "1",
        "managedDB": b_managed == "1",
        "selfHosted": b_self == "1",
    }
    return settings, raw
