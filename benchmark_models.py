import json
import urllib.error
import urllib.request

from agent_praxis.framework.gymnasium_wrapper import ENV_SPECS, AgentPraxisGymEnv

OLLAMA_URL = "http://localhost:11434/api/chat"

MODELS = [
    "qwen2.5:0.5b",
    "llama3.2:3b",
    "phi3:latest",
    "llama3.1:8b",
    "gemma2:9b",
    "gemma4:latest",
    "mychen76/qwen3_cline_roocode:14b"
]

ENVIRONMENTS = list(ENV_SPECS.keys())

def get_action_from_ollama(model, messages, action_names):
    payload = {
        "model": model,
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
        
        try:
            choice = json.loads(content)
            index = int(choice.get("action_index", 0))
            if 0 <= index < len(action_names):
                return index, content
        except (ValueError, json.JSONDecodeError):
            pass
            
        return 0, content
        
    except Exception as e:
        return None, str(e)


def evaluate_model_on_env(model, env_name):
    print(f"\n[{model}] -> [{env_name}] Starting evaluation")
    
    # Check if model exists/works
    test_req = urllib.request.Request(
        OLLAMA_URL, 
        data=json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}], "stream": False}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        urllib.request.urlopen(test_req)
    except Exception as e:
        print(f"[{model}] failed to load or respond: {e}")
        return {"model": model, "environment": env_name, "score": 0.0, "steps": 0, "error": str(e)}

    # We use a fixed seed per environment for fair comparison
    seed_map = {
        "dorian-gray": 20260201,
        "catch-22": 20260301,
        "1984": 20260501,
        "metamorphosis": 20260401,
        "the-trial": 20260601
    }
    env = AgentPraxisGymEnv(environment=env_name, seed=seed_map.get(env_name, 2026))
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
    command_log = []
    
    final_reward = 0.0
    for _step in range(max_steps):
        actions_text = "\n".join([f"[{i}] {name}" for i, name in enumerate(action_names)])
        user_prompt = f"CURRENT STATE:\n{obs}\n\nAVAILABLE ACTIONS:\n{actions_text}\n\nWhich action index do you want to take?"
        
        messages.append({"role": "user", "content": user_prompt})
        
        action_idx, raw_response = get_action_from_ollama(model, messages, action_names)
        if action_idx is None:
            break
            
        action_name = action_names[action_idx]
        command_log.append(action_name)
        messages.append({"role": "assistant", "content": raw_response})
        
        obs, reward, terminated, truncated, info = env.step(action_idx)
        
        if terminated or truncated:
            final_reward = reward
            break

    print(f"[{model}] -> [{env_name}] Finished with score: {final_reward} in {len(command_log)} steps")
    return {
        "model": model,
        "environment": env_name,
        "score": final_reward,
        "steps": len(command_log),
        "path": command_log
    }

def main():
    results = []
    for model in MODELS:
        for env_name in ENVIRONMENTS:
            res = evaluate_model_on_env(model, env_name)
            results.append(res)
            
            # Save intermediate results
            with open("benchmark_results.json", "w") as f:
                json.dump(results, f, indent=2)
            
    print("\n\nAll models evaluated on all environments. Results saved to benchmark_results.json")

if __name__ == "__main__":
    main()
