import json
import os

try:
    from prompts_preamble import PREAMBLES
except ImportError:
    print("Error: Could not find prompts_preamble.py")
    PREAMBLES = None

def read_markdown_file(filepath):
    if not os.path.exists(filepath):
        return ""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read().strip()

def main():
    if PREAMBLES is None:
        return

    celia_text = read_markdown_file("celia_text.md")
    celia_vision = read_markdown_file("celia_vision.md")

    # Initialize dictionary without brackets
    final_prompts = dict()
    final_prompts.update({"default": {"text": celia_text, "vision": celia_vision}})

    separator = "\n\n"

    for model_name, config in PREAMBLES.items():
        # Create the nested dictionary for this model
        final_prompts.update({model_name: dict()})
        current_model = final_prompts.get(model_name)
        
        if "text" in config:
            text_val = config.get("text", "")
            raw_preamble = str(text_val).strip()
            if raw_preamble:
                current_model.update({"text": f"{raw_preamble}{separator}{celia_text}"})
            else:
                current_model.update({"text": celia_text})
                
        if "vision" in config:
            vision_val = config.get("vision", "")
            raw_preamble_vision = str(vision_val).strip()
            if raw_preamble_vision:
                current_model.update({"vision": f"{raw_preamble_vision}{separator}{celia_vision}"})
            else:
                current_model.update({"vision": celia_vision})

    output_filepath = "prompts.json"
    with open(output_filepath, "w", encoding="utf-8") as f:
        json.dump(final_prompts, f, indent=4, ensure_ascii=False)
        
    print(f"Successfully generated {output_filepath}")

if __name__ == "__main__":
    main()