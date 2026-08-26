#!/bin/bash

repo=$1

echo "Repo: $repo"

python3 -m src.agent.deep_agent "$repo"