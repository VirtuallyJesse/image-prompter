# nvidia_nim_service.py
import os
from openai import OpenAI
from core.services.base_service import BaseAIService, BaseAIWorker

class NvidiaNimWorker(BaseAIWorker):
    """
    Worker thread to handle streaming API calls to NVIDIA NIM via OpenAI SDK.
    """
    def __init__(self, client, model_name, messages, enable_thinking=True):
        super().__init__()
        self.client = client
        self.model_name = model_name
        self.messages = messages
        self.enable_thinking = enable_thinking

    def run(self):
        try:
            # Build request parameters
            request_params = {
                "model": self.model_name,
                "messages": self.messages,
                "stream": True
            }
            
            # Add thinking parameter for models that support it (DeepSeek, Kimi K2)
            # Per NVIDIA NIM docs: must be wrapped in chat_template_kwargs
            if self.enable_thinking:
                request_params["extra_body"] = {"chat_template_kwargs": {"thinking": True}}
            
            # Use streaming API
            response_stream = self.client.chat.completions.create(**request_params)
            
            full_response = ""
            full_thinking = ""
            
            for chunk in response_stream:
                if self._is_cancelled:
                    break
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    
                    # Check for reasoning content (DeepSeek, Kimi K2 format)
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        self.thinking_chunk.emit(delta.reasoning_content)
                        full_thinking += delta.reasoning_content
                    
                    # Regular content
                    if hasattr(delta, 'content') and delta.content:
                        self.chunk.emit(delta.content)
                        full_response += delta.content
            
            if self._is_cancelled:
                self.error.emit("Generation interrupted by user.")
                return

            self._emit_result(full_response, full_thinking)

        except Exception as e:
            self.error.emit(str(e))

class NvidiaNimService(BaseAIService):
    """Service for interacting with NVIDIA NIM API using OpenAI SDK."""

    # Model mapping: GUI friendly name -> API model ID
    MODEL_MAP = {
        "DeepSeek V3.2": "deepseek-ai/deepseek-v3.2",
        "Kimi K2": "moonshotai/kimi-k2-thinking",
        "Kimi K2.5": "moonshotai/kimi-k2.5",
        "GLM-4.7": "z-ai/glm4.7",
        "GLM-5": "z-ai/glm5",
        "Qwen3.5-397B-A17B": "qwen/qwen3.5-397b-a17b",
    }

    # Models that support image/vision input
    VISION_MODELS = {"Kimi K2.5", "Qwen3.5-397B-A17B"}

    def __init__(self):
        super().__init__()
        self.api_key = os.environ.get("NVIDIA_NIM_API_KEY")
        self.client = None

        if self.api_key:
            try:
                # Initialize OpenAI client with NVIDIA NIM base URL
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://integrate.api.nvidia.com/v1"
                )
            except Exception as e:
                print(f"Failed to initialize NVIDIA NIM Client: {e}")
        else:
            print("Warning: NVIDIA_NIM_API_KEY environment variable not set.")
            print("NVIDIA NIM service will be unavailable until API key is configured.")

    def _emit_error(self, message: str):
        self.status_updated.emit(f"Error: {message}")
        self.error_occurred.emit(message)

    def generate_response(self, system_prompt: str, user_input: str, model_name: str = "DeepSeek V3.2", conversation_history: list = None, **kwargs):
        """Generates a response using the NVIDIA NIM API in a background thread."""
        if not self.client:
            return self._emit_error("NVIDIA_NIM_API_KEY not found.")

        files_data = kwargs.get('files_data', [])
        is_vision = model_name in self.VISION_MODELS
        has_images = is_vision and any(
            f.get('mime_type', '').startswith('image/') for f in files_data
        )

        if not user_input.strip() and not has_images:
            return self._emit_error("Input cannot be empty.")

        api_model = self.MODEL_MAP.get(model_name, "deepseek-ai/deepseek-v3.2")
        self.status_updated.emit(f"Generating response using NVIDIA NIM {model_name}...")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if conversation_history:
            messages.extend([
                {"role": m.get("role", ""), "content": m.get("content", "")}
                for m in conversation_history if m.get("content")
            ])

        # Build user message: multipart content for vision models with images,
        # plain text otherwise
        if has_images:
            content_parts = []
            if user_input.strip():
                content_parts.append({"type": "text", "text": user_input})
            for file_data in files_data:
                mime = file_data.get('mime_type', '')
                if mime.startswith('image/'):
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{file_data['base64']}"
                        }
                    })
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": user_input})

        worker = NvidiaNimWorker(self.client, api_model, messages, enable_thinking=True)
        self._start_worker(worker)