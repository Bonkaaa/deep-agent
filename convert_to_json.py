from pathlib import Path
import re
import json
import sys

def parse_location_info(txt):
    # Parse location=Location(line=..., column=...)
    loc_match = re.search(r"location=Location\(line=(\d+), column=(\d+)\)", txt)
    if loc_match:
        return {
            "line": int(loc_match.group(1)),
            "column": int(loc_match.group(2))
        }
    return {}

def parse_endpoint_info(txt):
    # e.g. EndPointInfo(name='...', file='...', location=Location(...))
    name = re.search(r"name=['\"](.*?)['\"]", txt)
    file = re.search(r"file=['\"](.*?)['\"]", txt)
    location = parse_location_info(txt)
    result = {}
    if name: result["name"] = name.group(1)
    if file: result["file"] = file.group(1)
    if location: result["location"] = location
    return result

def parse_pair(txt):
    # e.g. SourceSinkPair(source=EndPointInfo(...), sink=EndPointInfo(...), explaination='...', rank=1)
    # For robustness, allow fields in any order
    source = re.search(r"source=EndPointInfo\((.*?)\),", txt, re.DOTALL)
    sink = re.search(r"sink=EndPointInfo\((.*?)\),", txt, re.DOTALL)
    explaination = re.search(r"explaination=(['\"])(.*?)\1\s*,\s*rank=", txt, re.DOTALL)
    rank = re.search(r"rank=(\d+)", txt)
    result = {}
    if source:
        result["source"] = parse_endpoint_info(source.group(1))
    if sink:
        result["sink"] = parse_endpoint_info(sink.group(1))
    if explaination:
        result["explaination"] = explaination.group(2).replace("\\'", "'")
    if rank:
        result["rank"] = int(rank.group(1))
    return result

def extract_pairs_text(content):
    start = content.find("pairs=[")
    if start == -1:
        return None

    i = start + len("pairs=[")
    depth = 0
    in_string = None
    escape = False

    while i < len(content):
        ch = content[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = None
        else:
            if ch in ('"', "'"):
                in_string = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                if depth > 0:
                    depth -= 1
            elif ch == "]" and depth == 0:
                return content[start + len("pairs=["):i]

        i += 1

    return None

if __name__ == "__main__":
    
    if len(sys.argv) < 2:
        raise SystemExit("No output directory path provided. Usage: python convert_to_json.py <output_directory_path>")

    output_dir = sys.argv[1]

    file_name = next(Path(output_dir).glob("*_source_sink_analysis.txt"))

    if not file_name:
        raise SystemExit(f"No *_source_sink_analysis.txt file found in {output_dir}!")

    pairs = []

    with open(file_name, encoding="utf-8") as f:
        content = f.read()

    # Extract the top-level pairs list from the serialized response
    pairs_text = extract_pairs_text(content)
    if not pairs_text:
        raise RuntimeError("Could not find the pairs=[...] block!")

    # Now split each top-level SourceSinkPair(...) using balanced parentheses.
    pair_matches = []
    index = 0
    marker = "SourceSinkPair("
    while True:
        start = pairs_text.find(marker, index)
        if start == -1:
            break

        position = start + len(marker)
        depth = 1
        in_string = None
        escape = False

        while position < len(pairs_text):
            ch = pairs_text[position]

            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == in_string:
                    in_string = None
            else:
                if ch in ('"', "'"):
                    in_string = ch
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        pair_matches.append(pairs_text[start + len(marker):position])
                        index = position + 1
                        break

            position += 1

        else:
            raise RuntimeError("Unbalanced SourceSinkPair(...) block!")

    for pair_txt in pair_matches:
        pair_json = parse_pair(pair_txt)
        pairs.append(pair_json)

    output_json = Path(output_dir) / "parsed_source_sink_pairs.json"

    # Pretty-print JSON to file
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(pairs, f, indent=2, ensure_ascii=False)

    print(f"Wrote parsed pairs to {output_json}")