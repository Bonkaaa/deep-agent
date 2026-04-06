---
name: extract-taint-paths
description: USE THIS SKILL TO FIND TAINT PATHS IN CODE. This skill provides tools to response the taint paths, which are sequences of data flow that can lead to vulnerabilities.
---

# Extract Taint Paths

## Input 
You will provided with a folder path that contains code files and a list of vulnerable functions (can be accessed again using the `fetch_folder_path` and `fetch_vulnerable_functions` tools).

## Provided Context
1. **Folder Path**: The path to the folder containing the code files to be analyzed. Access via `fetch_folder_path` tool (from `runtime.context.folder_path`).
2. **Vulnerable Functions**: A list of functions that have been identified as vulnerable. Access via `fetch_vulnerable_functions` tool.

## Instructions

### 1. Analyze Code Files: 
Use the provided folder path to access and analyze the code files. Focus on identifying data flows that involve the vulnerable functions. Vulnerable functions can be sources, sinks, or part of the data flow that leads to vulnerabilities.

### 2. Identify Taint Paths: 
For each vulnerable function, trace the data flow to identify potential taint paths. A taint path is a sequence of function calls and data manipulations that can lead to a vulnerability. Pay special attention to how data is passed through different functions and how it interacts with the vulnerable functions.

### 3. Document Taint Paths via Inline Comments: 
Once you have identified a valid taint path, you MUST document the data flow directly in the code using the `insert_comment_at_line` tool. 

**Rules for Commenting:**
* You must invoke the tool at every line where tainted data is introduced, modified, or passed to another variable.
* The comment format MUST strictly be: `// tainted: "<variable_name>"`
* Trace the flow sequentially: Start at the taint source, mark every intermediate variable where the taint propagates, and end at the vulnerable sink.
* Only comment on the specific variables that carry the malicious payload in that step of the flow.

**Example Usage**:

If you identify a flow where user input reaches an execution sink, your resulting code modifications using `insert_comment_at_line` should look exactly like this:

***Identified Flow:***
```javascript
1  import(config) { // tainted: "config"
2    const item=JSON.parse(config) // tainted: "config"
3    let restoreData=item // tainted: "item"
4    // ...
```

### 4. Construct the Final Taint Path Report:
Once the taint path is fully identified, you must generate a comprehensive report detailing the data flow from the source to the sink. Then respone the report in a structured format that includes both natural language explanations and the relevant code snippets.

**Using the Extraction Tool:**
You MUST use the `extract_code_snippets` tool to retrieve the exact blocks of code needed for your report. Do not guess or hallucinate the code. Fetch the specific lines encompassing the taint flow, including a few surrounding context lines if necessary to show the block structure.

**Formatting Rules:**
* **Interleaved Structure:** Your final output must be a sequence of natural language explanations interleaved with the extracted code snippets showing how the code propagates the taint.
* **Section Headers:** If the taint path spans multiple files or jumps to different methods, you must create a new section. Each section MUST start with a natural language header specifying the method, class (if applicable), and file location.
* **Code Blocks:** Enclose all extracted snippets in standard markdown code blocks (e.g., ```javascript). 

***Example Output Format:***
Your final response should strictly follow this structural pattern:
````
Vulnerable method `import` of class `Environment` located in `djv/lib/djv.js`:
```js
import(config) { // tainted: "config"
  const item=JSON.parse(config) // tainted: "config"
  let restoreData=item // tainted: "item"
  if (item.name && item.fn && item.schema) {
    restoreData={
      [item.name]: item,
    }
  }
  Object.keys(restoreData).forEach((key)=>{ // tainted: "restoreData"
    const {name, schema, fn: source}=restoreData[key] // tainted: "restoreData"
    const fn=restore(source, schema, this.options) // tainted: "source"
    this.resolved[name]={
      name,
      schema,
```
Call to `restore`:
```js
function restore(source, schema, {inner}={}) { // tainted: "source"
  const tpl=new Function("schema", source)(schema) // tainted: "source"
  if (!inner) {
```
````

