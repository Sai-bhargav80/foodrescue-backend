import json

log_path = r"C:\Users\veman\.gemini\antigravity-ide\brain\1043b43e-48e2-4424-9ad5-3a085bc45e5c\.system_generated\logs\transcript_full.jsonl"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        step_idx = data.get("step_index")
        if step_idx and step_idx < 170:
            tool_calls = data.get("tool_calls", [])
            for tc in tool_calls:
                args = tc.get("args", {})
                if "main.py" in args.get("TargetFile", ""):
                    print(f"Step {step_idx} | Tool: {tc.get('name')} | Range: {args.get('StartLine')}-{args.get('EndLine')}")
                    tc_name = tc.get("name")
                    if tc_name == "replace_file_content":
                        print(f"  Target: {repr(args.get('TargetContent')[:100])}")
                        print(f"  Repl: {repr(args.get('ReplacementContent')[:100])}")
                    elif tc_name == "multi_replace_file_content":
                        for i, chunk in enumerate(args.get("ReplacementChunks", [])):
                            print(f"  Chunk {i} Range: {chunk.get('StartLine')}-{chunk.get('EndLine')}")
                            print(f"    Target: {repr(chunk.get('TargetContent')[:100])}")
                            print(f"    Repl: {repr(chunk.get('ReplacementContent')[:100])}")
                    print("-" * 50)
