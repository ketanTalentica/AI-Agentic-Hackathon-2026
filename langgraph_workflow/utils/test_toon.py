from utils.toon_converter import JsonToToonConverter

sample = {
    "primary_intent": "technical_issue",
    "confidence_score": 0.92,
    "urgency_level": "high",
    "details": {
        "error": "500 internal server error",
        "occurrences": 5
    },
    "items": ["a", "b", "c"]
}

mapping = {
    "primary_intent": "pi",
    "confidence_score": "cs",
    "urgency_level": "ul",
    "details": "dt",
    "items": "it"
}

toon = JsonToToonConverter.encode(sample, mapping=mapping)
print("TOON:\n", toon)

decoded = JsonToToonConverter.decode(toon, mapping=mapping)
print("DECODED:\n", decoded)

assert decoded["primary_intent"] == sample["primary_intent"]
assert decoded["details"]["error"] == sample["details"]["error"]
print("Roundtrip OK")
