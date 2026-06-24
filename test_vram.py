import torch
import json

def check():
    res = {}
    res["cuda_available"] = torch.cuda.is_available()
    if res["cuda_available"]:
        vram_bytes = torch.cuda.get_device_properties(0).total_memory
        vram_gb = vram_bytes / (1024**3)
        res["vram_bytes"] = vram_bytes
        res["vram_gb"] = vram_gb
        res["vram_gb_lt_3_5"] = bool(vram_gb < 3.5)
        res["vram_gb_lt_4_0"] = bool(vram_gb < 4.0)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    check()
