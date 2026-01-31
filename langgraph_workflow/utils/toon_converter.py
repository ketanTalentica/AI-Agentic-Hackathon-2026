import re
import json
from typing import Any, Dict, Optional

class JsonToToonConverter:
    """
    Simple, reversible JSON <-> TOON converter.
    Includes auto-generation of mapping if none provided.
    """
    
    @staticmethod
    def _generate_auto_mapping(obj: Any) -> Dict[str, str]:
        """Scan keys recursively and generate mapping."""
        keys = set()
        def _scan(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    keys.add(k)
                    _scan(v)
            elif isinstance(o, list):
                for i in o:
                    _scan(i)
        _scan(obj)
        
        # Simple generation strategy: 
        # "primary_intent" -> "pi"
        # "user_input" -> "ui"
        mapping = {}
        used_values = set()
        
        for key in sorted(keys):
            if len(key) <= 2:
                mapping[key] = key
                used_values.add(key)
                continue
                
            parts = key.split('_')
            base = "".join(p[0] for p in parts if p).lower()
            
            candidate = base
            counter = 1
            while candidate in used_values:
                candidate = f"{base}{counter}"
                counter += 1
            
            mapping[key] = candidate
            used_values.add(candidate)
            
        return mapping

    @staticmethod
    def _escape_str(s: str) -> str:
        return s.replace('\\', '\\\\').replace('"', '\\"')

    @staticmethod
    def _unescape_str(s: str) -> str:
        return s.replace('\\"', '"').replace('\\\\', '\\')

    @classmethod
    def encode(cls, obj: Any, mapping: Optional[Dict[str, str]] = None) -> str:
        # If no mapping provided, generate one on the fly (NOTE: Decoder needs same mapping!)
        # In practice, either pass a shared mapping or include mapping in payload (overhead).
        # For now, we assume user provides mapping or we generate one but warn it's not stateless.
        mapping = mapping or cls._generate_auto_mapping(obj)

        def _enc(x):
            if isinstance(x, dict):
                parts = []
                for k, v in x.items():
                    shortk = mapping.get(k, k)
                    parts.append(f"{shortk}={_enc(v)}")
                return f"({';'.join(parts)})"
            elif isinstance(x, list):
                return "[" + ",".join(_enc(i) for i in x) + "]"
            elif isinstance(x, str):
                return '"' + cls._escape_str(x) + '"'
            elif isinstance(x, bool):
                return "true" if x else "false"
            elif x is None:
                return "null"
            else:
                return str(x)

        return _enc(obj)

    @classmethod
    def decode(cls, toon: str, mapping: Optional[Dict[str, str]] = None) -> Any:
        mapping = mapping or {}
        # build reverse mapping
        rev_map = {v: k for k, v in mapping.items()}

        s = toon.strip()
        idx = 0
        length = len(s)

        def _peek():
            return s[idx] if idx < length else None

        def _consume_whitespace():
            nonlocal idx
            while idx < length and s[idx].isspace():
                idx += 1

        def _parse_value():
            nonlocal idx
            _consume_whitespace()
            if idx >= length:
                return None
            ch = s[idx]
            if ch == '(':
                return _parse_object()
            if ch == '[':
                return _parse_array()
            if ch == '"':
                return _parse_string()
            # parse true/false/null or number
            match = re.match(r"(true|false|null|-?\d+(?:\.\d+)?)", s[idx:])
            if match:
                token = match.group(1)
                idx += len(token)
                if token == 'true':
                    return True
                if token == 'false':
                    return False
                if token == 'null':
                    return None
                if '.' in token:
                    return float(token)
                return int(token)
            # fallback: try to consume until delimiter
            m = re.match(r"[^,;\)\]]+", s[idx:])
            if m:
                token = m.group(0).strip()
                idx += len(m.group(0))
                return token
            return None

        def _parse_string():
            nonlocal idx
            assert s[idx] == '"'
            idx += 1
            buf = []
            while idx < length:
                ch = s[idx]
                if ch == '\\':
                    if idx + 1 < length:
                        nxt = s[idx + 1]
                        buf.append(nxt)
                        idx += 2
                        continue
                if ch == '"':
                    idx += 1
                    break
                buf.append(ch)
                idx += 1
            return cls._unescape_str(''.join(buf))

        def _parse_array():
            nonlocal idx
            assert s[idx] == '['
            idx += 1
            arr = []
            while idx < length:
                _consume_whitespace()
                if idx < length and s[idx] == ']':
                    idx += 1
                    break
                val = _parse_value()
                arr.append(val)
                _consume_whitespace()
                if idx < length and s[idx] == ',':
                    idx += 1
                    continue
            return arr

        def _parse_object():
            nonlocal idx
            assert s[idx] == '('
            idx += 1
            obj = {}
            while idx < length:
                _consume_whitespace()
                # read key
                m = re.match(r"([A-Za-z0-9_\-]+)=", s[idx:])
                if not m:
                    # no key found, skip
                    break
                key = m.group(1)
                idx += len(m.group(0))
                val = _parse_value()
                long_key = rev_map.get(key, key)
                obj[long_key] = val
                _consume_whitespace()
                if idx < length and s[idx] == ';':
                    idx += 1
                    continue
                if idx < length and s[idx] == ')':
                    idx += 1
                    break
            return obj

        # Attempt to parse top-level
        try:
            val = _parse_value()
            return val
        except Exception:
            # fallback: try JSON
            try:
                return json.loads(toon)
            except Exception:
                return None
