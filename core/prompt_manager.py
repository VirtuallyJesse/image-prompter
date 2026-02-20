# core/prompt_manager.py
import json
import os

class PromptManager:
    """Manages system prompts for different models and modalities."""
    
    def __init__(self, filepath: str = "prompts.json"):
        self.filepath = filepath
        self.prompts = {
            "default": {
                "text": "You are Image Assistant. Transform the user's idea into a detailed JSON prompt containing the mandated fields.",
                "vision": "You are Image Assistant. Analyze the attached image and the user's idea to generate a detailed JSON prompt containing the mandated fields."
            }
        }
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.prompts.update(data)
            except Exception:
                pass
        else:
            self.save()

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.prompts, f, indent=4)
        except Exception:
            pass

    def get_prompt(self, service: str, model: str, has_image: bool) -> str:
        """Fetch the correct system prompt for the service/model and modality context."""
        key = f"{service}:{model}"
        ptype = "vision" if has_image else "text"
        
        if key in self.prompts and ptype in self.prompts[key]:
            return self.prompts[key][ptype]
        
        return self.prompts["default"].get(ptype, "")
