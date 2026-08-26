---
name: extract-source-sink-pairs
description: USE THIS SKILL TO IDENTIFY SUSPICIOUS SOURCE-SINK PAIRS IN CODE CHANGES, FOCUSING ON VULNERABILITY-INDUCING COMMITS (VIC). The purpose is to detect data flows introduced or altered by the vulnerability-inducing commit, prioritizing top pairs with the highest security risks.
---

# Extract Suspicious Source-Sink Pairs

## Input
You are provided with one VIC folder containing two code snapshots and one diff file:
- **before/**: The code snapshot before the vulnerability-inducing commit. This represents the state of the codebase prior to the changes that introduced the vulnerability which includes modified files and deleted files in the "after" snapshot but does not include any new files that were added in the "after" snapshot.
- **after/**: The code snapshot after the vulnerability-inducing commit.
- **diff.diff**: The code diff showing changes between the two versions.

Each VIC folder contains only the files that changed between the two commits inside the `before/` and `after/` directories, plus `diff.diff` to show the differences.

## Instructions

### 1. Comprehend the Code Changes  
Read the files inside `before/` and `after/`, and focus on positions where code has been added, modified, or removed in `diff.diff`. The main objective is to find new or changed data flows that could constitute a potential vulnerability.

### 1.1 Traverse the Backend Precisely
- Start with `diff.diff` and enumerate the exact touched file paths before reading anything else.
- Read the matching files in `before/` and `after/` for each touched path.
- For each changed hunk, inspect the enclosing function or class first, then only the directly connected local helper functions, imported local modules, or callers/callees that are necessary to explain the flow.
- Expand one hop at a time. Do not scan unrelated backend files, and do not guess filenames that are not explicitly referenced by the diff or by code you already read.
- If the diff changes a function that calls another local helper, read that helper before exploring anything farther away.
- Keep locations precise and only cite code lines that were directly read from tool output.

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
- IF FILE MAY EXCEED 100 LINES, DO NOT READ THE ENTIRE FILE AT ONCE. INSTEAD, USE OFFSET-BASED READING TO PROCESS THE FILE IN CHUNKS OF 100 LINES UNTIL YOU REACH THE END OF THE FILE (EOF). THIS APPROACH ENSURES EFFICIENT MEMORY USAGE AND ALLOWS YOU TO HANDLE LARGE FILES WITHOUT ISSUES.
- Prefer exact path references from `/vic/...`, `/skills/...`, and other paths directly evidenced in the code. Do not invent alternate filenames or directories.
- Do not cite any line not directly read from tool output.

## Output Format

Your output must be a JSON array of exactly 5 objects. Each object represents one suspicious source-sink pair, with the following structure:
- `source`: An object describing the untrusted input/source.
  - `name` (string): The variable or function where untrusted input enters.
  - `file` (string): The filename in which the source appears.
  - `location` (object):
    - `line_numbers` (array of int): List of line numbers related to the source.
    - `code_snippet` (string): The relevant code snippet (as read from the file) showing this source.

- `sink`: An object describing the destination/sink.
  - `name` (string): The variable, function, or API that acts as the sink.
  - `file` (string): The filename in which the sink appears.
  - `location` (object):
    - `line_numbers` (array of int): List of line numbers related to the sink.
    - `code_snippet` (string): The relevant code snippet showing the sink.

- `explanation` (string): A concise justification in English for why this pair is risky and how the tainted data could reach the sink.

- `rank` (int): An integer from 1 to 5 indicating the risk level, with 1 being the highest risk and 5 being the lowest among the top 5 pairs.


Present the report as an ordered list from highest to lowest risk.
No text, section headers, or additional fields outside this array are allowed.
If there are fewer than 5 pairs found, the array must still contain 5 elements; unused slots must be set to null.
---

# Output Example
```
[
  {
    "source": {
      "name": "req.body.filename",
      "file": "controllers/upload.js",
      "location": {
        "line_numbers": [12, 13],
        "code_snippet": "const filename = req.body.filename;"
      }
    },
    "sink": {
      "name": "child_process.exec",
      "file": "controllers/upload.js",
      "location": {
        "line_numbers": [15],
        "code_snippet": "require('child_process').exec(\"convert \" + filename);"
      }
    },
    "explanation": "User-provided filename is passed directly to a shell command without validation or sanitization, enabling command injection."
  },
  {
    "source": {
      "name": "req.query.username",
      "file": "routes/user.js",
      "location": {
        "line_numbers": [47],
        "code_snippet": "const username = req.query.username;"
      }
    },
    "sink": {
      "name": "db.execute",
      "file": "routes/user.js",
      "location": {
        "line_numbers": [49],
        "code_snippet": "db.execute(\"DELETE FROM users WHERE name = '\" + username + \"'\");"
      }
    },
    "explanation": "Untrusted username input is concatenated directly into a SQL query, making SQL injection possible."
  },
  {
    "source": {
      "name": "req.cookies.sessionid",
      "file": "services/session.js",
      "location": {
        "line_numbers": [12],
        "code_snippet": "const sid = req.cookies.sessionid;"
      }
    },
    "sink": {
      "name": "fs.writeFileSync",
      "file": "services/session.js",
      "location": {
        "line_numbers": [13],
        "code_snippet": "fs.writeFileSync(\"/tmp/sessions/\" + sid, JSON.stringify(data));"
      }
    },
    "explanation": "Session ID from user cookie is used as a filename without checks, allowing for arbitrary file write or overwrite."
  },
  {
    "source": {
      "name": "process.env.SERVICE_KEY",
      "file": "server/config.js",
      "location": {
        "line_numbers": [78],
        "code_snippet": "res.send({status: \"ok\", secret: process.env.SERVICE_KEY});"
      }
    },
    "sink": {
      "name": "HTTP response",
      "file": "server/config.js",
      "location": {
        "line_numbers": [78],
        "code_snippet": "res.send({status: \"ok\", secret: process.env.SERVICE_KEY});"
      }
    },
    "explanation": "Sensitive environment variable is exposed in an HTTP response, enabling information disclosure."
  },
  {
    "source": {
      "name": "event.upload.name",
      "file": "lib/logger.js",
      "location": {
        "line_numbers": [103],
        "code_snippet": "fs.appendFileSync(\"/logs/\" + event.upload.name + \".log\", event.info);"
      }
    },
    "sink": {
      "name": "fs.appendFileSync",
      "file": "lib/logger.js",
      "location": {
        "line_numbers": [103],
        "code_snippet": "fs.appendFileSync(\"/logs/\" + event.upload.name + \".log\", event.info);"
      }
    },
    "explanation": "Untrusted upload name is used as a log filename, which could allow overwriting or forging log files."
  }
]
```
