import json
import urllib.error
import urllib.request

from agent_praxis.framework.gymnasium_wrapper import AgentPraxisGymEnv

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.1:8b"

def get_action_from_ollama(messages, action_names):
    """Call Ollama and ask it to pick an action index."""
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "format": "json"
    }
    
    req = urllib.request.Request(
        OLLAMA_URL, 
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        content = result["message"]["content"]
        
        # The model should return {"action_index": X} based on our prompt
        try:
            choice = json.loads(content)
            index = int(choice.get("action_index", 0))
            if 0 <= index < len(action_names):
                return index, content
        except (ValueError, json.JSONDecodeError):
            pass
            
        print(f"[Warning] Failed to parse action from response: {content}")
        return 0, content  # Fallback to action 0 (usually status or description)
        
    except urllib.error.URLError as e:
        print(f"Failed to connect to Ollama: {e}")
        return None, str(e)


def main():
    print(f"Starting Agent Praxis evaluation using Ollama model: {MODEL}")
    env = AgentPraxisGymEnv(environment="dorian-gray", seed=20260201)
    
    obs, info = env.reset()
    action_names = info["action_names"]
    
    system_prompt = (
        "You are an SRE investigating a failing system. "
        "At each step, you will be given the current state of the system and a list of available actions. "
        "Your goal is to solve the problem and execute the action that 'finalizes' your resolution.\n\n"
        "You MUST respond ONLY with valid JSON containing a single key 'action_index' corresponding to the index of the action you want to take.\n"
        "Example output: {\"action_index\": 1}"
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    
    max_steps = 15
    for step in range(max_steps):
        print(f"\n=== Step {step + 1} ===")
        
        actions_text = "\n".join([f"[{i}] {name}" for i, name in enumerate(action_names)])
        user_prompt = f"CURRENT STATE:\n{obs}\n\nAVAILABLE ACTIONS:\n{actions_text}\n\nWhich action index do you want to take?"
        
        messages.append({"role": "user", "content": user_prompt})
        
        print("Thinking...")
        action_idx, raw_response = get_action_from_ollama(messages, action_names)
        if action_idx is None:
            break
            
        action_name = action_names[action_idx]
        print(f"Agent chose action: [{action_idx}] {action_name}")
        
        messages.append({"role": "assistant", "content": raw_response})
        
        obs, reward, terminated, truncated, info = env.step(action_idx)
        
        if terminated or truncated:
            print("\n=== EPISODE FINISHED ===")
            print(f"Final Score: {reward}")
            print("Evaluation Details:")
            print(json.dumps(info.get("evaluation", {}), indent=2))
            break

if __name__ == "__main__":
    main()
