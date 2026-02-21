---
trigger: always_on
---

# Rules for LLM Agents - Image Assistant

Image Assistant is a PyQt6 desktop application that transforms user ideas into detailed, optimized image generation prompts using AI models. The application supports multiple AI services (Gemini, NVIDIA NIM) for prompt generation and provides direct image generation through integrated APIs (Pollinations, Airforce, Perchance) via the Media Panel.

## 0. Critical Context Pollution Rule

**NEVER attempt to read the files `celia_text.md`, `celia_vision.md`, `prompts.json`, `prompts_build.py`, or `prompts_preamble.py` in the project root.** These files are LARGE and will pollute your context memory, severely degrading performance. These files contain system prompts and configuration data that are loaded programmatically by the application - they do not need to be read by LLM agents.

## 1. Project-Specific Coding Standards

- Use Python 3.x with type hints where appropriate
- Follow PEP 8 style guidelines for code formatting
- Use 4 spaces for indentation (no tabs)
- Use descriptive variable and function names in snake_case
- Limit lines to 100 characters maximum
- Use docstrings for classes and functions
- Implement error handling with try/except blocks and meaningful error messages
- Use threading for background operations to prevent UI blocking

## 2. File Naming and Directory Structure

- Python files: Use snake_case (.py)
- Configuration files: Use snake_case with .json extension
- Documentation files: Use UPPERCASE with .md extension
- Data files: Use descriptive names with appropriate extensions
- Directory structure must follow the established project organization:
  - `app/` - Application layer (controller, main entry point)
  - `core/` - Core framework components (config, services, prompt_manager)
  - `gui/` - GUI layer (main window, views, widgets)
  - `utils/` - Utility modules (reserved for future use)
  - `docs/` - Documentation files
  - `assets/` - Static assets (icons)
- Root-level data files:
  - `prompts.json` - System prompts for each service/model (DO NOT READ - large file)
  - `celia.json` - Additional prompt configuration (DO NOT READ - large file)
  - `gui_config.json` - User preferences and settings

## 3. Key Architectural Patterns

- **Layered Architecture**: Maintain strict separation between application layers (app/, core/, gui/, utils/)
- **Application Layer (app/)**: Orchestrates components and manages application lifecycle with template methods for custom integration
- **Core Layer (core/)**: Contains framework configuration, data definitions, prompt management, and extensible structures for GUI components
- **Service Layer (core/services/)**: Dedicated services for file handling, Gemini/NVIDIA NIM API integration, chat history management, and image generation APIs (Pollinations, Airforce, Perchance) to separate business logic from GUI
- **Prompt Management (core/prompt_manager.py)**: Centralized system for managing system prompts per service/model with text/vision modality support
- **GUI Layer (gui/)**: Handles user interface with PyQt6 signal/slot architecture, including modular widgets and view components
- **Utility Layer (utils/)**: Reserved for general-purpose utilities (currently minimal; threading is handled via QThread in core/services/base_service.py)
- Implement threaded operations for background operations to prevent UI blocking
- Use configuration-driven features rather than hardcoded values
- Implement proper state management for UI elements and application data
- Use Qt's event system and event filters for complex UI interactions
- **Template Method Pattern**: Use extensible controller design for easy integration of custom business logic

## 4. Technology-Specific Constraints

- Use PyQt6 for all GUI components with proper signal/slot connections
- Use Pillow (PIL) for all image processing operations
- Store configuration in JSON format in gui_config.json
- Use base64 encoding/decoding for image data handling
- Use QTimer for UI updates and delayed operations
- Use QThread or threading for background operations
- Use JSON module for configuration and data serialization
- Use webbrowser module for opening URLs
- Use os and pathlib modules for file system operations

## 4.1 API Integration Guidelines

- Use google-genai SDK (not deprecated google-generativeai) for Gemini API access
- Use OpenAI SDK for NVIDIA NIM API access (OpenAI-compatible endpoint)
- Store API keys in environment variables for security:
  - `GEMINI_API_KEY` - Single Gemini API key (backward compatible)
  - `GEMINI_ROTATE_API_KEY` - Comma-separated Gemini API keys for rate limit rotation
  - `NVIDIA_NIM_API_KEY` - NVIDIA NIM API key
  - `POLLINATIONS_API_KEY` - Required for Pollinations image generation
  - `AIRFORCE_API_KEY` - Required for Airforce image generation
- Implement proper error handling for API rate limits, authentication failures, and network issues
- Use background threading for all API calls to prevent UI blocking
- Encode files to base64 for API transmission but do not store them permanently
- Implement conversation context management for multi-turn chat sessions
- Provide clear user feedback for API status (loading, success, error states)
- Handle different models across Gemini and NVIDIA NIM services:
  - Gemini: `gemini-2.5-flash` (Flash), `gemini-2.5-pro` (Pro) - supports file attachments
  - NVIDIA NIM: `deepseek-ai/deepseek-v3.2` (DeepSeek V3.2), `moonshotai/kimi-k2-thinking` (Kimi K2) - text only, no file support
- Support service switching between Gemini and NVIDIA NIM with per-service model preferences
- **Streaming Implementation**: Use streaming APIs (`generate_content_stream` for Gemini, `stream=True` for OpenAI SDK) for all responses to ensure real-time user feedback
- **Reasoning/Thinking**:
  - Gemini: Use `ThinkingConfig(include_thoughts=True, thinking_budget=8192)`
  - NVIDIA NIM: Use `extra_body={"chat_template_kwargs": {"thinking": True}}`
  - Display thinking tokens in Teal (`#4ECDC4`) to distinguish from final output
  - Save chat history only after the full stream (including thoughts) is complete
- **API Key Rotation**: Gemini service supports automatic key rotation on 429 rate limit errors when multiple keys are configured via `GEMINI_ROTATE_API_KEY`

## 4.2 Image Generation API Integration

The Media Panel provides direct image generation through three external APIs:

### Pollinations Service
- **API**: Text-to-image API via URL-based requests
- **Endpoint**: `https://gen.pollinations.ai/image`
- **Authentication**: Required `POLLINATIONS_API_KEY` environment variable
- **Models**: `flux`, `zimage`, `klein`, `klein-large`, `gptimage`
- **Sizes**: `1024x1024`, `1344x768`, `768x1344`
- **Features**: Negative prompts, seed control
- **Implementation**: [`core/services/pollinations_service.py`](core/services/pollinations_service.py)

### Airforce Service
- **API**: OpenAI-compatible image generation API with SSE streaming
- **Endpoint**: `https://api.airforce/v1/images/generations`
- **Authentication**: Required `AIRFORCE_API_KEY` environment variable
- **Models**: `grok-imagine`, `imagen-4`
- **Sizes**: `1024x1024`, `1344x768`, `768x1344`
- **Features**: SSE streaming responses, negative prompts, seed control, base64 response format
- **Implementation**: [`core/services/airforce_service.py`](core/services/airforce_service.py)

### Perchance Service
- **Integration**: Embedded WebEngine view of Perchance image generator
- **URL**: Configurable via `perchance_url` in config (default: `https://perchance.org/a1481832-0a06-414f-baa6-616052e5f61d`)
- **Authentication**: Uses persistent WebEngine profile for cookie-based login
- **Features**: 
  - Two-layer ad blocking (network request interception + DOM element hiding)
  - Persistent cookies and login state across sessions
  - Automatic image download handling with EXIF metadata embedding
  - Lazy URL loading on first tab view
- **Dependencies**: Requires `PyQt6-WebEngine` (optional dependency)
- **Implementation**: [`core/services/perchance_service.py`](core/services/perchance_service.py)

### Image Generation Common Components
- **ImageDisplay**: Custom QLabel widget for displaying generated images with click-to-reveal functionality
- **Shared Styles**: Consistent styling constants for input fields, buttons, and dropdowns
- **Dropdown Factory**: Hover-activated dropdown widgets for model/size selection
- **Implementation**: [`gui/widgets/image_gen_common.py`](gui/widgets/image_gen_common.py)

## 5. Testing and Quality Requirements

- Ensure all GUI operations remain responsive with no freezing
- Validate user inputs before processing with appropriate checks
- Test drag-and-drop functionality for files and images
- Test clipboard image paste (Ctrl+V) functionality
- Test configuration loading and saving with various states including API keys
- Test background operation handling for API calls (QThread-based workers in services)
- Test widget interactions and signal/slot connections
- Test layout management and responsive design
- Test chat history saving, loading, and navigation
- Test file upload validation and base64 encoding/decoding
- Test Gemini API integration with mock responses for different scenarios
- Test conversation context preservation across messages
- Test system-model tethering functionality when switching between services with incompatible models
- Test API key rotation with multiple Gemini keys
- **Prompt Management Testing**:
  - Test PromptManager loads prompts from prompts.json correctly
  - Test fallback to default prompts when model-specific prompt not found
  - Test text vs vision prompt selection based on image attachment
- **Display Field Filtering Testing**:
  - Test Display button dropdown shows all field toggles
  - Test toggling fields updates visual display in response panel
  - Test display field preferences persist in gui_config.json
  - Test raw chat history saves complete output regardless of display filters
- **Image Generation Testing**:
  - Test Pollinations generation with various models and sizes
  - Test Airforce generation with valid API key
  - Test Perchance WebEngine loading and ad blocking
  - Test image download and save with EXIF metadata
  - Test click-to-reveal functionality in image display
  - Test generation cancellation during active generation
  - Test configuration persistence for each service's settings

## 6. Common Pitfalls to Avoid

- Do not block the main UI thread with heavy operations
- Do not modify the GUI directly from background threads (use signals)
- Do not ignore or bypass existing error handling patterns
- Do not add dependencies without checking existing imports
- Do not change file naming conventions without clear justification
- Do not directly manipulate Qt widgets from background threads
- Do not ignore proper resource cleanup (files, network connections, etc.)
- Do not bypass the existing configuration system

## 7. Data Models and Business Logic

- Configuration is stored in gui_config.json with GUI settings like window geometry, theme preferences, API keys, default model selections, and display field toggles
- Chat history is stored as JSON files in a 'chats' directory with message arrays, timestamps, and metadata (text data only, no file attachments)
- **Prompt Management**: System prompts are managed by `core/prompt_manager.py` (PromptManager class) which supports:
  - Per-service and per-model prompt customization via `prompts.json`
  - Separate prompts for text-only requests vs image-attached (vision) requests
  - Fallback to default prompts when no model-specific prompt is defined
  - Prompt format: `{"Service:Model": {"text": "...", "vision": "..."}, "default": {"text": "...", "vision": "..."}}`
- **Display Field Filtering**: The `display_fields` configuration in gui_config.json controls which JSON output fields are visually rendered in the response panel:
  - Fields include: `core`, `composition`, `lighting`, `style`, `technical`, `post_processing`, `special_elements`, `detailed_prompt`, `grok_imagine_optimized`, `gemini_optimized`, `flux_optimized`, `stable_diffusion_optimized`, `video_optimized`, `ooc_note`
  - Toggled via the Display button dropdown in the action buttons panel
  - Filtering is visual-only; raw chat history saves all output
- Implement proper state management for UI elements, application data, and conversation context
- Handle file data as base64 encoded strings for API transmission (temporary processing, not permanent storage) with size validation (15MB limit)
- FileService supports multiple file uploads with list-based storage (`files_b64`, `filenames`)
- Chat messages support `filenames` field (list) for multi-file attachment tracking
- Template methods in controller provide extension points for custom business logic integration
- Gemini API integration requires environment variable GEMINI_API_KEY or GEMINI_ROTATE_API_KEY for authentication
- NVIDIA NIM API integration requires environment variable NVIDIA_NIM_API_KEY for authentication
- **Image Generation Configuration**: Each service has dedicated configuration keys:
  - Pollinations: `pollinations_positive_prompt`, `pollinations_negative_prompt`, `pollinations_model`, `pollinations_size`, `pollinations_seed`, `pollinations_last_image`
  - Airforce: `airforce_positive_prompt`, `airforce_negative_prompt`, `airforce_model`, `airforce_size`, `airforce_seed`, `airforce_last_image`
  - Perchance: `perchance_url`, `adblocker` (blocked_domains, hidden_selectors)
- **Media Panel State**: `media_active_tab` stores the currently selected tab index (0=Gallery, 1=Pollinations, 2=Airforce, 3=Perchance)
- **Generated Images**: Saved to `images/` directory with timestamp-based filenames and embedded EXIF metadata (prompt, model, size, seed, service)

## 8. Critical Dependencies

- **PyQt6** for GUI implementation with signal/slot architecture
- **PyQt6-WebEngine** (optional) for Perchance embedded browser integration
- **Pillow (PIL)** for image processing with format detection and EXIF metadata embedding
- **google-genai** for Gemini API integration and AI-powered chat
- **openai** for NVIDIA NIM API integration (OpenAI-compatible endpoint)
- **markdown** for CommonMark markdown rendering in response window
- **Pygments** for syntax highlighting in markdown code blocks
- **PyPDF2** for PDF file processing
- **QThread (PyQt6)** for background operations via BaseAIWorker in core/services/base_service.py
- **JSON module** for configuration management and chat history storage
- **base64 module** for file encoding for API transmission
- **webbrowser module** for opening URLs
- **os and pathlib modules** for file system operations
- **urllib module** for Pollinations and Airforce HTTP requests

## 9. Configuration Management

- **GUI Settings**: Store window geometry, theme preferences, and basic UI settings
- **State Persistence**: Save configuration on application exit and restore on startup
- **Default Values**: Provide sensible defaults for all GUI configuration options
- **Display Fields**: User preferences for which JSON output fields to display are stored in `display_fields` dict within gui_config.json
- **Media Panel Settings**:
  - `media_active_tab`: Currently selected tab index (0-3)
  - `pollinations_*`: Pollinations service settings (prompts, model, size, seed, last image)
  - `airforce_*`: Airforce service settings (prompts, model, size, seed, last image)
  - `perchance_url`: Custom Perchance generator URL
  - `adblocker`: Dictionary with `blocked_domains` and `hidden_selectors` for Perchance ad blocking

## 9.1 Image Assistant Features

Image Assistant transforms user ideas into detailed, optimized image generation prompts through three core features:

### The Brain (Text-Only Prompts)
- System prompts that instruct AI models to generate detailed JSON image prompts from user text input
- Accessed via PromptManager with `has_image=False` parameter
- Prompts stored in prompts.json under the "text" key for each service:model pair

### The Eyes (Vision/Image-Attached Prompts)
- System prompts for when users attach images with their requests
- Instructs AI to analyze attached images and generate prompts describing or modifying them
- Accessed via PromptManager with `has_image=True` parameter
- Prompts stored in prompts.json under the "vision" key for each service:model pair

### The Mouth (JSON Output Fields)
The AI returns structured JSON with the following fields that can be toggled for display:
- `core`: Subject details (physique, clothing, posture, expression, environment)
- `composition`: Framing and layout (rule of thirds, layering, negative space)
- `lighting`: Light setup (source, direction, color temperature, shadows)
- `style`: Artistic direction (influences, color palette, texture)
- `technical`: Camera specs (focal length, aperture, shutter speed, DoF)
- `post_processing`: Editing effects (filters, color grading, sharpening)
- `special_elements`: Effects (particles, reflections, distortions)
- `detailed_prompt`: Full natural language description
- `grok_imagine_optimized`: 60-75 token version for Grok
- `gemini_optimized`: 90-105 token version for Gemini
- `flux_optimized`: 140-150 token version for Flux
- `stable_diffusion_optimized`: 150-200 token version for Stable Diffusion
- `video_optimized`: 70-80 token action-centric version for image-to-video
- `ooc_note`: Out-of-context notes or additional information

## 9.2 Media Panel Features

The Media Panel provides a secondary pane for direct image generation through integrated APIs:

### Tab Navigation
- **Gallery** (Tab 0): Placeholder for viewing generated images
- **Pollinations** (Tab 1): Text-to-image generation (requires API key)
- **Airforce** (Tab 2): Premium image generation with API key authentication
- **Perchance** (Tab 3): Embedded WebEngine view with ad blocking

### Common UI Components
Each image generation page shares:
- Positive/negative prompt input fields
- Model selection dropdown (service-specific models)
- Size selection dropdown (1024x1024, 1344x768, 768x1344)
- Seed input (-1 for random)
- Generate/Cancel button with state toggle
- Image display with click-to-reveal in file explorer

### Image Storage
- Generated images saved to `images/` directory
- Filename format: `YYYY-MM-DD_HH-MM-SS.jpg` (with counter for duplicates)
- EXIF metadata embedded: prompt, negative prompt, model, size, seed, service
- Click on displayed image opens file in system explorer

## 10. Error Handling and Resilience

- **User Feedback**: Provide clear error messages and status updates for all operations
- **Fallback Behavior**: Implement graceful degradation when optional features fail

## 11. LLM Agent Specific Warnings

- **CRITICAL - Context Pollution**: NEVER read `celia.json` or `prompts.json` from the project root. These files are LARGE (30KB+ and 67KB+ respectively) and will severely degrade LLM performance by consuming context window space.
- **Token-Heavy Files**: The following files contain large data structures and are token-intensive for LLM processing:
  - `app/controller.py` - Application orchestration with signal connections and business logic
  - `gui/widgets/action_buttons_panel.py` - Contains service/model selection UI, Display button, and dropdown components
  - `gui/widgets/response_panel.py` - Contains streaming display logic, search functionality, and display field filtering
  - `gui/widgets/pollinations_page.py` - Pollinations image generation UI with controls
  - `gui/widgets/airforce_page.py` - Airforce image generation UI with controls
  - `core/services/gemini_service.py` - Contains API integration with key rotation and streaming
  - `core/services/perchance_service.py` - WebEngine profile management and ad blocking logic
- **Caution**: Only read these files if directly related to your task. Avoid unnecessary processing to conserve tokens and maintain efficiency.
- **Testing Launch**: LLM agents can launch the program while testing with 'python -m app.main'.

## 12. Keyboard Shortcuts

- `Ctrl+F` - Open search in response panel
- `Ctrl+Left` - Navigate to previous chat
- `Ctrl+Right` - Navigate to next chat (or create new chat if at end)
- `Ctrl+D` - Delete all chats (with confirmation)
- `Ctrl+V` - Paste image from clipboard (auto-attaches as file)
- `Enter` - Send message (from input field)