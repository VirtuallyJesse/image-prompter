# Rules for LLM Agents - PyQt6 Chat Framework

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
  - `core/` - Core framework components (config, services)
  - `gui/` - GUI layer (main window, views, widgets)
  - `utils/` - Utility modules (threading, text processing)
  - `docs/` - Documentation files
  - `assets/` - Static assets (icons)

## 3. Key Architectural Patterns

- **Layered Architecture**: Maintain strict separation between application layers (app/, core/, gui/, utils/)
- **Application Layer (app/)**: Orchestrates components and manages application lifecycle with template methods for custom integration
- **Core Layer (core/)**: Contains framework configuration, data definitions, and extensible structures for GUI components
- **Service Layer (core/services/)**: Dedicated services for file handling, Gemini/NVIDIA NIM API integration, chat history management, and dynamic prompt generation to separate business logic from GUI
- **GUI Layer (gui/)**: Handles user interface with PyQt6 signal/slot architecture, including modular widgets and view components
- **Utility Layer (utils/)**: Provides general-purpose utilities for threading and text processing
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

## 5. Testing and Quality Requirements

- Ensure all GUI operations remain responsive with no freezing
- Validate user inputs before processing with appropriate checks
- Test drag-and-drop functionality for files and images
- Test clipboard image paste (Ctrl+V) functionality
- Test configuration loading and saving with various states including API keys
- Test threading utilities and background operation handling for API calls
- Test widget interactions and signal/slot connections
- Test layout management and responsive design
- Test chat history saving, loading, and navigation
- Test file upload validation and base64 encoding/decoding
- Test Gemini API integration with mock responses for different scenarios
- Test conversation context preservation across messages
- Test system-model tethering functionality when switching between services with incompatible models
- Test API key rotation with multiple Gemini keys

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

- Configuration is stored in gui_config.json with GUI settings like window geometry, theme preferences, API keys, and default model selections
- Chat history is stored as JSON files in a 'chats' directory with message arrays, timestamps, and metadata (text data only, no file attachments)
- System prompts are generated dynamically via `core/services/prompt_service.py` based on action type and file context (replaces static prompts from deprecated `core/system_prompts.json`)
- Use the dynamic prompt generation system for new features requiring context-aware prompts
- Implement proper state management for UI elements, application data, and conversation context
- Handle file data as base64 encoded strings for API transmission (temporary processing, not permanent storage) with size validation (15MB limit)
- FileService supports multiple file uploads with list-based storage (`files_b64`, `filenames`)
- Chat messages support `filenames` field (list) for multi-file attachment tracking
- Template methods in controller provide extension points for custom business logic integration
- Gemini API integration requires environment variable GEMINI_API_KEY or GEMINI_ROTATE_API_KEY for authentication
- NVIDIA NIM API integration requires environment variable NVIDIA_NIM_API_KEY for authentication

## 8. Critical Dependencies

- **PyQt6** for GUI implementation with signal/slot architecture
- **Pillow (PIL)** for image processing with format detection
- **google-genai** for Gemini API integration and AI-powered chat
- **openai** for NVIDIA NIM API integration (OpenAI-compatible endpoint)
- **markdown** for CommonMark markdown rendering in response window
- **Pygments** for syntax highlighting in markdown code blocks
- **PyPDF2** for PDF file processing
- **Threading module** for background operations with daemon threads
- **JSON module** for configuration management and chat history storage
- **base64 module** for file encoding for API transmission
- **webbrowser module** for opening URLs
- **os and pathlib modules** for file system operations

## 9. Configuration Management

- **GUI Settings**: Store window geometry, theme preferences, and basic UI settings
- **State Persistence**: Save configuration on application exit and restore on startup
- **Default Values**: Provide sensible defaults for all GUI configuration options

## 10. Error Handling and Resilience

- **User Feedback**: Provide clear error messages and status updates for all operations
- **Fallback Behavior**: Implement graceful degradation when optional features fail

## 11. LLM Agent Specific Warnings

- **Token-Heavy Files**: The following files contain large data structures and are token-intensive for LLM processing:
  - `app/controller.py` - Application orchestration with signal connections and business logic
  - `gui/widgets/action_buttons_panel.py` - Contains service/model selection UI and button components
  - `gui/widgets/response_panel.py` - Contains streaming display logic and search functionality
  - `core/services/gemini_service.py` - Contains API integration with key rotation and streaming
- **Caution**: Only read these files if directly related to your task. Avoid unnecessary processing to conserve tokens and maintain efficiency.
- **Testing Launch**: LLM agents can launch the program while testing with 'python -m app.main'.

## 12. Keyboard Shortcuts

- `Ctrl+F` - Open search in response panel
- `Ctrl+Left` - Navigate to previous chat
- `Ctrl+Right` - Navigate to next chat (or create new chat if at end)
- `Ctrl+D` - Delete all chats (with confirmation)
- `Ctrl+V` - Paste image from clipboard (auto-attaches as file)
- `Enter` - Send message (from input field)