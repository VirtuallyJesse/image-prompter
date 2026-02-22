---
trigger: always_on
---

# Rules for LLM Agents - Image Assistant

Image Assistant is a PyQt6 desktop application that transforms user ideas into detailed, optimized image generation prompts using AI models. The application supports multiple AI services (Gemini, NVIDIA NIM) for prompt generation and provides direct image generation through integrated APIs via the Media Panel.

## 0. Critical Context Pollution Rule

**NEVER read these files - they are LARGE and will severely degrade LLM performance:**
- `celia_text.md`, `celia_vision.md` - System prompts
- `prompts.json`, `prompts_build.py`, `prompts_preamble.py` - System prompts + prompt configuration

## 1. Project Structure

```
app/           - Application layer (controller, main entry point)
core/          - Core framework (config, services, prompt_manager)
core/services/ - Business logic services (API integrations, file handling)
gui/           - GUI layer (main window, widgets)
gui/widgets/   - UI components (panels, pages)
docs/          - Documentation
assets/        - Static assets (icons)
```

**Configuration:** `gui_config.json` - User preferences, API keys, model selections
**Chat History:** `chats/` directory - JSON files with message arrays
**Generated Images:** `images/` directory - JPG files with EXIF metadata

## 2. Coding Standards

- Python 3.x with type hints, PEP 8 style, 4-space indentation
- Snake_case for files/variables, docstrings for classes/functions
- 100 character line limit, meaningful error handling
- Use QThread for background operations, never block UI thread
- Use signals to update GUI from background threads

## 3. Architecture Patterns

- **Layered Architecture:** Strict separation (app/ → core/ → gui/)
- **Service Layer:** Business logic in `core/services/` separate from GUI
- **Signal/Slot:** PyQt6 event-driven communication between components
- **Template Method:** Extensible controller design for custom logic integration

## 4. API Integration

### AI Services (Prompt Generation)
| Service | Models | File Support | Auth Env Var |
|---------|--------|--------------|--------------|
| Gemini | `gemini-2.5-flash`, `gemini-2.5-pro` | Yes | `GEMINI_API_KEY` or `GEMINI_ROTATE_API_KEY` |
| NVIDIA NIM | `deepseek-ai/deepseek-v3.2`, `moonshotai/kimi-k2-thinking` | No | `NVIDIA_NIM_API_KEY` |

- Use `google-genai` SDK for Gemini, `openai` SDK for NVIDIA NIM
- Streaming required for all responses (real-time feedback)
- Gemini supports API key rotation on 429 errors with multiple keys

### Image Generation Services
| Service | Auth | Models | Implementation |
|---------|------|--------|----------------|
| Pollinations | `POLLINATIONS_API_KEY` | flux, zimage, klein, klein-large, gptimage | [`pollinations_service.py`](core/services/pollinations_service.py) |
| Airforce | `AIRFORCE_API_KEY` | grok-imagine, imagen-4 | [`airforce_service.py`](core/services/airforce_service.py) |
| Perchance | Cookie-based | External site | [`perchance_service.py`](core/services/perchance_service.py) |

**Common sizes:** `1024x1024`, `1344x768`, `768x1344`
**Image storage:** `images/` directory with timestamp filenames and EXIF metadata

## 5. Media Panel

The Media Panel provides a secondary pane with four tabs:

| Tab | Index | Purpose |
|-----|-------|---------|
| Gallery | 0 | View generated images in paginated grid |
| Pollinations | 1 | Text-to-image generation |
| Airforce | 2 | Premium image generation |
| Perchance | 3 | Embedded WebEngine view |

### Gallery Page
- **Grid:** 4x3 layout (12 items per page) with pagination
- **Filtering:** By service (All, Pollinations, Airforce, Perchance)
- **Features:** Click image to reveal in explorer, click prompt to copy
- **Config:** `gallery_page` (current page), `gallery_filter` (active filter)
- **Implementation:** [`gallery_page.py`](gui/widgets/gallery_page.py), [`gallery_service.py`](core/services/gallery_service.py)

### Image Generation Pages
Shared UI components: positive/negative prompts, model dropdown, size dropdown, seed input, generate/cancel button, image display with click-to-reveal.

## 6. Configuration Keys

Key configuration values stored in `gui_config.json`:

| Key | Purpose |
|-----|---------|
| `media_active_tab` | Current Media Panel tab (0-3) |
| `gallery_page` | Gallery current page number |
| `gallery_filter` | Gallery filter selection |
| `pollinations_*` | Pollinations settings (model, size, seed, prompts, last_image) |
| `airforce_*` | Airforce settings (model, size, seed, prompts, last_image) |
| `perchance_url` | Custom Perchance generator URL |
| `adblocker` | Perchance ad blocking (blocked_domains, hidden_selectors) |
| `display_fields` | Toggle which JSON output fields to display |

## 7. JSON Output Fields

The AI returns structured JSON with these displayable fields:
- `core`, `composition`, `lighting`, `style`, `technical`
- `post_processing`, `special_elements`, `detailed_prompt`
- `grok_imagine_optimized`, `gemini_optimized`, `flux_optimized`
- `stable_diffusion_optimized`, `video_optimized`, `ooc_note`

Display toggling is visual-only; chat history saves complete output.

## 8. Dependencies

**Required:** PyQt6, Pillow, google-genai, openai, markdown, Pygments, PyPDF2
**Optional:** PyQt6-WebEngine (for Perchance embedded browser)

## 9. LLM Agent Warnings

- **Token-Heavy Files:** Only read when directly related to task:
  - `app/controller.py`, `gui/widgets/action_buttons_panel.py`
  - `gui/widgets/response_panel.py`, `core/services/gemini_service.py`
  - `core/services/perchance_service.py`
- **Testing:** Launch with `python -m app.main`

## 10. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+F | Open search in response panel |
| Ctrl+Left/Right | Navigate chat history |
| Ctrl+D | Delete all chats |
| Ctrl+V | Paste image from clipboard |
| Enter | Send message |

## 11. Perchance Integration - Agent Guidelines

Perchance requires a unique approach compared to other image generation services. It embeds an external website via Qt WebEngine rather than using a REST API.

### Architecture Overview

Perchance uses a **nested iframe structure**:
1. **Top frame** (`perchance.org`) - Main page container
2. **Generator frame** (`<hash>.perchance.org`) - Generator logic, has `#promptInput`
3. **Image frames** (`image-generation.perchance.org`) - Actual image generation

**Critical:** Cross-Origin Resource Sharing (CORS) prevents direct access between frames. Data must be passed via `postMessage()`.

### Script Injection Strategy

**Always inject at the PROFILE level, not the PAGE level:**

```python
# CORRECT: Profile-level injection with DocumentCreation timing
script = QWebEngineScript()
script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
script.setRunsOnSubFrames(True)
profile.scripts().insert(script)

# WRONG: Page-level injection misses dynamically created iframes
page.scripts().insert(script)  # Will NOT work for Perchance
```

**Why:** Perchance dynamically creates image-generation iframes after the main page loads. `DocumentCreation` timing ensures the script is injected before any JavaScript executes in any frame.

### Metadata Extraction

Perchance stores generation metadata in **iframe URL hash fragments**, not in JavaScript variables:

```javascript
// Metadata is URL-encoded JSON in the iframe src hash
// iframe.src = "https://image-generation.perchance.org/embed#%7B%22prompt%22%3A%22...%22%7D"
var hashStr = iframe.src.split('#')[1];
var meta = JSON.parse(decodeURIComponent(hashStr));
// meta = { prompt: "...", negativePrompt: "...", seed: ..., guidanceScale: ... }
```

**Available fields:** `prompt`, `negativePrompt`, `resolution`, `guidanceScale`, `seedUsed`

### Auto-Download Pipeline

1. **JavaScript** intercepts `postMessage` events with `type: 'finished'`
2. **JavaScript** extracts metadata from iframe URL hash
3. **JavaScript** forwards data to top frame via `window.top.postMessage()`
4. **Python** polls `window._perchanceImageQueue` via `runJavaScript()` every 1 second
5. **Python** decodes base64 image data, embeds EXIF metadata, saves to `images/`

### PyQt6 WebEngine Quirks

**`javaScriptConsoleMessage` cannot be monkey-patched:**

```python
# WRONG: This does NOT work - C++ virtual method
page.javaScriptConsoleMessage = my_handler  # No effect

# CORRECT: Must subclass QWebEnginePage
class MyPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        # Handle console messages here
        pass
```

### Ad Blocking Layers

Perchance uses **two-layer ad blocking**:

1. **Network-level:** `QWebEngineUrlRequestInterceptor` blocks requests to ad domains
2. **DOM-level:** JavaScript hides ad elements via CSS injection + MutationObserver

**Menu bar hiding** requires CSS variable override:
```javascript
document.documentElement.style.setProperty('--menu-bar-height', '0px');
```

### Configuration

| Key | Purpose |
|-----|---------|
| `perchance_url` | Custom generator URL (default: AI image generator) |
| `adblocker.blocked_domains` | Network-level blocked domains |
| `adblocker.hidden_selectors` | CSS selectors for DOM-level hiding |

### Debugging Tips

1. **Check frame injection:** Look for `[Perchance-AD] INJECTED` and `DIAG from sub-frame` logs
2. **Verify iframe URLs:** Should show `image-generation.perchance.org/embed#%7B...%7D`
3. **Monitor queue:** `[Perchance-AD] TOP: Queued image #N` indicates successful capture
4. **Poll timer:** Must start after `loadFinished` signal, not in constructor

### Common Pitfalls

| Issue | Cause | Solution |
|-------|-------|----------|
| Script not in sub-frames | Page-level injection | Use profile-level injection |
| Missing metadata | Wrong timing | Use `DocumentCreation` injection point |
| CORS errors | Direct frame access | Use `postMessage()` for cross-frame communication |
| Console messages not captured | Monkey-patch attempt | Subclass `QWebEnginePage` |
| Menu bar still visible | CSS only | Also set `--menu-bar-height: 0px` |
