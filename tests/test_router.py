import requests
import json
import time

def test_chitchat():
    print("\n--- Test Chitchat Router ---")
    notebook_id = "test_router_notebook"
    
    # Send a chitchat query
    payload = {
        "query": "xin chào bạn",
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
    # Create notebook first
    requests.post("http://localhost:8000/api/notebooks", json={
        "id": "test_router_notebook",
        "title": "Test Router",
        "is_private": True
    })
    
    test_chitchat()
