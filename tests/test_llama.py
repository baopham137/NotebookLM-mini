from llama_cpp import Llama

print("Before")

llm = Llama(
    model_path="models/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
    n_ctx=128,
    n_gpu_layers=0,
    verbose=True
)

print("After")