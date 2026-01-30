from ramalama_sdk import RamalamaModel
from ramalama_sdk.main import ChatMessage

sys_prompt: ChatMessage = {"role": "system", "content": "You are a pirate"}
history = [sys_prompt]

runtime_image = "quay.io/ramalama/ramalama:latest"
model = "gemma3:1b"

with RamalamaModel(model, base_image=runtime_image, timeout=60) as model:
    response = model.chat("How tall is Michael Jordan?", history)
    print(response["content"])
