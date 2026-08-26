import json


def _normalize_uri(uri):
    if not uri:
        return ""
    return uri.replace("file://", "")

def extract_signatures_from_sarif(file_path):
    """
    Hàm này đọc file SARIF và trả về một SET chứa các 'chữ ký' của taint path.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    signatures = set()
    
    runs = data.get('runs', [])
    if not runs:
        return signatures
    results = runs[0].get('results', [])
    
    for result in results:
        rule_id = result.get('ruleId')
        locations = result.get("locations", [])
        
        code_flows = result.get('codeFlows', [])
        for codeFlow in code_flows:
            for threadFlow in codeFlow.get('threadFlows', []):
                locations = threadFlow.get('locations', [])
                if not locations:
                    continue
                
                # 1. Locate source
                source_node = locations[0].get('location', {})
                source_start_col = source_node.get('physicalLocation', {}).get('region', {}).get('startColumn')
                source_end_col = source_node.get('physicalLocation', {}).get('region', {}).get('endColumn')
                source_text = source_node.get('message', {}).get('text')
                
                # 2. Locate sink
                sink_node = locations[-1].get('location', {})
                sink_text = sink_node.get('message', {}).get('text')
                sink_start_col = sink_node.get('physicalLocation', {}).get('region', {}).get('startColumn')
                sink_end_col = sink_node.get('physicalLocation', {}).get('region', {}).get('endColumn')
                
                # Create tuple for storing info
                signature = (rule_id, source_start_col, source_end_col, source_text, sink_text, sink_start_col, sink_end_col)
                signatures.add(signature)

        if not code_flows and locations:
            for location in locations:
                physical_location = location.get("physicalLocation", {})
                artifact_location = physical_location.get("artifactLocation", {})
                region = physical_location.get("region", {})
                message = location.get("message", {}).get("text")
                signature = (
                    rule_id,
                    message,
                    _normalize_uri(artifact_location.get("uri", "")),
                    region.get("startLine"),
                    region.get("startColumn"),
                )
                signatures.add(signature)
                
    return signatures

def _signature_to_dict(signature):
    if len(signature) == 7:
        rule_id, source_start_col, source_end_col, source_text, sink_text, sink_start_col, sink_end_col = signature
        return {
            "rule_id": rule_id,
            "source_start_col": source_start_col,
            "source_end_col": source_end_col,
            "source_text": source_text,
            "sink_text": sink_text,
            "sink_start_col": sink_start_col,
            "sink_end_col": sink_end_col,
        } 

def _signature_to_text(signature):
    if len(signature) == 7:
        rule_id, source_start_col, source_end_col, source_text, sink_text, sink_start_col, sink_end_col = signature
        return (
            f"Rule: {rule_id} | "
            f"Source: {source_text} | Source Columns: {source_start_col}-{source_end_col} | "
            f"Sink: {sink_text} | Sink Columns: {sink_start_col}-{sink_end_col}"
        )

    return (
        f"Rule: {signature[0]} | Message: {signature[1]} | "
        f"URI: {signature[2]} | Line: {signature[3]} | Col: {signature[4]}"
    )


def compare_codeql_results(file_path_before, file_path_after, emit=True):
    set_before = extract_signatures_from_sarif(file_path_before)
    set_after = extract_signatures_from_sarif(file_path_after)

    only_in_after = sorted(set_after - set_before)
    only_in_before = sorted(set_before - set_after)
    common = sorted(set_before & set_after)

    result = {
        "before_path": file_path_before,
        "after_path": file_path_after,
        "before_count": len(set_before),
        "after_count": len(set_after),
        "only_in_before": [_signature_to_dict(signature) for signature in only_in_before],
        "only_in_after": [_signature_to_dict(signature) for signature in only_in_after],
        "common": [_signature_to_dict(signature) for signature in common],
        "summary": {
            "only_in_before_count": len(only_in_before),
            "only_in_after_count": len(only_in_after),
            "common_count": len(common),
        },
    }

    if emit:
        print("--- DIFFERENTIAL ANALYSIS ---")
        print(f"Before: {result['before_count']} signatures")
        print(f"After:  {result['after_count']} signatures")
        print(f"Only in before: {result['summary']['only_in_before_count']}")
        print(f"Only in after:  {result['summary']['only_in_after_count']}")
        print(f"Common:         {result['summary']['common_count']}")

        if only_in_before:
            print("\nFindings removed in after:")
            for bug in only_in_before:
                print(f"   -> {_signature_to_text(bug)}")

        if only_in_after:
            print("\nFindings present only in after:")
            for bug in only_in_after:
                print(f"   -> {_signature_to_text(bug)}")

        if not only_in_before and not only_in_after:
            print("\nNo differential findings detected between the two versions.")

    return result

# How to used
# compare_codeql_results('output_before.json', 'output_after.json')

if __name__ == "__main__":
    compare_codeql_results('CVE-2025-99999-query-iter-1_fixed_results.json', 'CVE-2025-99999-query-iter-1_vulnerable_results.json')
