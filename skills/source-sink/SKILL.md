---
name: extract-source-sink-pairs
description: USE THIS SKILL TO IDENTIFY SUSPICIOUS SOURCE-SINK PAIRS IN CODE CHANGES, FOCUSING ON VULNERABILITY-INDUCING COMMITS (VIC). The purpose is to detect data flows introduced or altered by the vulnerability-inducing commit, prioritizing top pairs with the highest security risks.
---

# Extract Suspicious Source-Sink Pairs

## Input
You are provided with three files:
- **Pre-Vulnerability File**: The version of the source code in javascript before the vulnerability-inducing commit.
- **Post-Vulnerability File**: The version of the code in javascript after the vulnerability-inducing commit.
- **Diff File**: The code diff showing changes between the two versions.

## Instructions

### 1. Comprehend the Code Changes  
Read all three files, focusing on positions where code has been added, modified, or removed in the diff. The main objective is to find new or changed data flows that could constitute a potential vulnerability.

### 2. Identify Source and Sink Candidates  
- A **source** is any location where untrusted input may enter the application (e.g. user inputs, file reads, network requests, environment variables).
- A **sink** is any sensitive or security-relevant operation (e.g. file writes, database queries, command execution, reflection, deserialization).

### 3. Search for Code Flows  
For each diff-affected area, trace the flow of data:
- Start from new or modified sources.
- Follow how data propagates through variables, functions, and method calls.
- Identify any path where tainted data introduced or modified by the commit is able to reach a sink.

### 4. Score and Rank the Pairs  
Each source-sink pair you find must be **scored** based on risk criteria. Prioritize pairs that:
- Directly involve changes from the commit (the diff).
- Form a new path from source to sink that did not exist in the pre-commit version.
- Involve sources or sinks that are inherently high-risk (e.g. obvious user inputs, command execution).
- Show absence or removal of validation, sanitization, or security checks.

### 5. Report the Top 5 Highest-Risk Pairs  
Select the **top 5 source-sink pairs** with the highest risk scores.
For each pair, your report should contain:
- A brief explanation why you think this source-sink pair is suspicious and high risk.
- Supporting code snippets from both the pre- and post-commit files, illustrating the data flow, the relevant changes, and the absence/presence of checks.
- The location in the file(s) (filename, method, and line numbers).
- The risk factors present (e.g. "source introduced by commit", "sink is command execution", "no sanitization present").

## Execution constraints:
- Do not call ls more than 2 times total.
- Do not use parent traversal paths such as '..'.
- If any required file cannot be read, stop immediately and report the missing path.
- After reading required files, produce the final analysis directly.

## Output Format

Your final output must strictly follow this structure for each pair:
1. **Section header:** Summary of the source-sink pair (location, function, file, etc.)
2. **Explanation:** Why this pair is a top risk.
3. **Code comparisons:** Show relevant code from the pre- and post-vulnerability files (with line numbers), highlighting the changed logic or new path.
4. **Risk factors:** Bullet or summary at the end of each pair.

Present the report as an ordered list from highest to lowest risk.

---

# Example Output
````
## 1. User Input Reaches Command Execution  
**Location:** `app/controllers/upload.js` – Function `handleUpload`  
**Lines involved:** 24-41 (post-commit)

**Explanation:**  
The commit introduces a new path where untrusted user file input (from HTTP request) is passed directly into a `child_process.exec` call. There is no sanitization or validation for filenames, enabling command injection risk.

**Pre-commit code:**  
```javascript
24  function handleUpload(req, res) {
25      const filename = req.body.filename;
26      // Previously: only allowed .png uploads
27      if (!filename.endsWith('.png')) return res.status(400).send('Invalid type');
28      fs.writeFileSync("/uploads/" + filename, req.body.data);
29      res.send("ok");
30  }
```

**Post-commit code:**
```javascript
24  function handleUpload(req, res) {
25      const filename = req.body.filename;
26      // Input type check removed
27      fs.writeFileSync("/uploads/" + filename, req.body.data);
28      // Direct command execution using untrusted input
29      require('child_process').exec("convert " + filename + " /outputs/" + filename + ".pdf");
30      res.send("ok");
31  }
```

**Risk factors:**
- Source: event.upload.name (attacker-supplied).
- Sink: filename for file write.
- No name checks.
- This path is new in the commit.
````

