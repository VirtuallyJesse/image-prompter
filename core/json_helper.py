# core/json_helper.py
import json
import re
from typing import Dict, Any

class JsonHelper:
    """Robust JSON extractor to capture badly formatted JSON outputs from lesser intelligent models."""

    @staticmethod
    def extract_and_parse_json(text: str) -> Dict[str, Any]:
        """
        Attempts to extract a JSON object from text and parse it.
        Handles missing closing braces, trailing commas, and escaped characters.
        """
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx == -1:
            return {}
            
        # If no closing brace, assume it goes to the end
        if end_idx == -1 or end_idx < start_idx:
            json_str = text[start_idx:] + '}'
        else:
            json_str = text[start_idx:end_idx+1]
            
        # Fix trailing commas before closing braces/brackets
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback to an aggressive regex-based key-value extraction for broken JSON
            return JsonHelper._parse_bad_json(json_str)

    @staticmethod
    def _parse_bad_json(json_str: str) -> Dict[str, Any]:
        """Aggressive fallback to extract key-value pairs when standard parsing fails."""
        result = {}
        # Matches "key": "value" or "key": boolean/number/null
        # Allows for possible missing quotes around simple values, though standard JSON requires it
        pattern = r'(?:"([^"]+)"|([a-zA-Z0-9_]+))\s*:\s*(?:"((?:[^"\\]|\\.)*)"|([^,}\n]+))'
        matches = re.finditer(pattern, json_str)
        
        for match in matches:
            key = match.group(1) or match.group(2)
            val_str = match.group(3)
            val_other = match.group(4)
            
            if not key:
                continue
                
            if val_str is not None:
                # Handle basic escaped sequences
                val = val_str.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                result[key] = val
            elif val_other is not None:
                val_other = val_other.strip()
                if val_other.lower() == 'true': 
                    result[key] = True
                elif val_other.lower() == 'false': 
                    result[key] = False
                elif val_other.lower() == 'null': 
                    result[key] = None
                else:
                    try:
                        if '.' in val_other:
                            result[key] = float(val_other)
                        else:
                            result[key] = int(val_other)
                    except ValueError:
                        # Fallback to saving it as a string
                        result[key] = val_other
                        
        return result
