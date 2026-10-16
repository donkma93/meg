import json
import re
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def main():
    dump_cs_path = os.path.join("dump", "dump.cs")
    dump_json_path = os.path.join("dump", "script.json")
    offsets_path = "megamu_offsets.json"

    with open(offsets_path, "r", encoding="utf-8") as f:
        app_offsets = json.load(f)

    with open(dump_json_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    script_methods = {m["Address"]: m for m in script_data.get("ScriptMethod", [])}
    script_metadata = {m["Address"]: m for m in script_data.get("ScriptMetadata", [])}

    print(f"Loaded {len(script_methods)} ScriptMethods and {len(script_metadata)} ScriptMetadata from script.json")

    with open(dump_cs_path, "r", encoding="utf-8", errors="ignore") as f:
        dump_lines = f.readlines()

    print(f"Loaded {len(dump_lines)} lines from dump.cs")

    rva_pattern = re.compile(r"//\s*RVA:\s*0x([0-9a-fA-F]+)")
    field_pattern = re.compile(r";\s*//\s*0x([0-9a-fA-F]+)")

    rva_to_line = {}
    for i, line in enumerate(dump_lines):
        m = rva_pattern.search(line)
        if m:
            rva_int = int(m.group(1), 16)
            next_code = dump_lines[i+1].strip() if i+1 < len(dump_lines) else ""
            rva_to_line[rva_int] = (i+1, line.strip(), next_code)

    print(f"Indexed {len(rva_to_line)} RVAs from dump.cs")

    results = []

    for key, val in app_offsets.items():
        if key == "game_module" or not isinstance(val, str) or not val.startswith("0x"):
            results.append({
                "key": key,
                "val": val,
                "type": "CONSTANT/INTEGER",
                "status": "PASS",
                "details": f"Hằng số hoặc giá trị cấu hình ({val})"
            })
            continue

        val_int = int(val, 16)

        # Check if it's a method RVA
        if val_int in rva_to_line or val_int in script_methods or val_int in script_metadata:
            line_no, rva_line, code_line = rva_to_line.get(val_int, (None, "", ""))
            sm = script_methods.get(val_int)
            meta = script_metadata.get(val_int)

            method_name = sm["Name"] if sm else (meta["Name"] if meta else code_line)
            sig = sm.get("Signature", "") if sm else ""

            results.append({
                "key": key,
                "val": val,
                "type": "METHOD_RVA",
                "status": "PASS",
                "line": line_no,
                "method_name": method_name,
                "signature": sig,
                "details": f"Khớp RVA chính xác! -> {method_name}"
            })
            continue

        # Check if it is a field offset (usually small, < 0x1000)
        if val_int < 0x1000:
            results.append({
                "key": key,
                "val": val,
                "type": "FIELD_OFFSET",
                "status": "CHECK_FIELD",
                "details": f"Field offset {val} (cần đối chiếu với Class tương ứng)"
            })
            continue

        results.append({
            "key": key,
            "val": val,
            "type": "METHOD_RVA",
            "status": "NOT_FOUND",
            "details": f"Không tìm thấy RVA {val} trong dump.cs mới!"
        })

    # In báo cáo
    print("\n" + "="*80)
    print("BÁO CÁO ĐỐI CHIẾU OFFSETS APP VỚI DUMP.CS MỚI NHẤT (16/10/2026)")
    print("="*80)

    pass_rva = [r for r in results if r["type"] == "METHOD_RVA" and r["status"] == "PASS"]
    fail_rva = [r for r in results if r["type"] == "METHOD_RVA" and r["status"] == "NOT_FOUND"]
    field_offsets = [r for r in results if r["type"] == "FIELD_OFFSET"]
    consts = [r for r in results if r["type"] == "CONSTANT/INTEGER"]

    print(f"\n[1] METHOD RVA CHÍNH XÁC (MATCH 100%): {len(pass_rva)} / {len(pass_rva) + len(fail_rva)}")
    for r in pass_rva:
        print(f"  ✅ {r['key']:<26}: {r['val']:<12} -> {r['method_name']}")

    if fail_rva:
        print(f"\n[2] METHOD RVA KHÔNG TÌM THẤY: {len(fail_rva)}")
        for r in fail_rva:
            print(f"  ❌ {r['key']:<26}: {r['val']:<12} -> {r['details']}")
    else:
        print("\n[2] METHOD RVA KHÔNG TÌM THẤY: 0 (Tất cả đều khớp!)")

    print(f"\n[3] FIELD OFFSETS: {len(field_offsets)}")
    for r in field_offsets:
        print(f"  🔍 {r['key']:<26}: {r['val']}")

if __name__ == "__main__":
    main()
