import zlib
import base64

class ToonMappingGenerator:
    """
    Auto-generates deterministic short keys for TOON serialization.
    Strategy: 
    1. Acronym (first letter of each word) + length checksum to avoid collision.
       e.g., "primary_intent" -> "pi" + suffix
    2. Fallback: hash-based if simple acronym is ambiguous (not implemented here, sticking to readable).
    """
    
    @staticmethod
    def generate_mapping(keys_to_map: list[str]) -> dict[str, str]:
        mapping = {}
        # sort to ensure deterministic processing order
        for key in sorted(keys_to_map):
            if len(key) <= 2: 
                mapping[key] = key
                continue
                
            # Create base acronym: "primary_intent" -> "pi"
            parts = key.split('_')
            base = "".join(p[0] for p in parts if p).lower()
            
            # If generated key exists, append suffix
            short_key = base
            counter = 1
            while short_key in mapping.values():
                short_key = f"{base}{counter}"
                counter += 1
            
            mapping[key] = short_key
        return mapping

    @staticmethod
    def hash_key(key: str) -> str:
        """Alternative: base62-ish hash of the key"""
        h = zlib.crc32(key.encode())
        # simple hex for now, could be base62
        return f"{h:x}"
