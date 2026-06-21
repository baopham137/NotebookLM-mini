import requests
import json
import time

def test_factoid():
    print("\n--- Test Factoid Router & Compression ---")
    notebook_id = "test_router_notebook"
    
    payload = {
        "query": "Thủ đô của Việt Nam là gì?",
        "notebook_id": notebook_id
    }
    
    start_time = time.time()
    with requests.post("http://localhost:8000/api/chat", json=payload, stream=True) as r:
        for line in r.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith('data: '):
                    data = json.loads(decoded[6:])
                    if data['type'] == 'status':
                        print(f"Status: {data['message']}")
                    elif data['type'] == 'chunk':
                        print(data['text'], end="", flush=True)
    print(f"\nTime taken: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    test_factoid()
