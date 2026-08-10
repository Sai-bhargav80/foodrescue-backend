import json

log_path = r"C:\Users\veman\.gemini\antigravity-ide\brain\1043b43e-48e2-4424-9ad5-3a085bc45e5c\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        step_idx = data.get("step_index")
        if step_idx == 70:
            tool_calls = data.get("tool_calls", [])
            for tc in tool_calls:
                args = tc.get("args", {})
                if "main.py" in args.get("TargetFile", ""):
                    print("StartLine:", args.get("StartLine"))
                    print("EndLine:", args.get("EndLine"))
                    print("TargetContent:")
                    print(repr(args.get("TargetContent")))
                    print("ReplacementContent:")
                    print(repr(args.get("ReplacementContent")))
                    break
