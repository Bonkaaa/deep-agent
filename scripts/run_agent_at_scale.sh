#!/usr/bin/env bash

# Hàm format thời gian
format_time() {
  local total_seconds=$1
  local hours=$((total_seconds / 3600))
  local minutes=$(((total_seconds % 3600) / 60))
  local seconds=$((total_seconds % 60))

  printf "%02d:%02d:%02d" "$hours" "$minutes" "$seconds"
}

# Thời gian bắt đầu toàn bộ script
script_start=$(date +%s)

for folder in data/*/; do
  vic_name=$(basename "$folder")

  output_file="output/${vic_name}/${vic_name}_source_sink_analysis.txt"

  if [ -f "$output_file" ]; then
    echo "Output file $output_file already exists. Skipping VIC: $vic_name"
    continue
  fi

  echo "========================================"
  echo "Processing VIC: $vic_name"

  # Thời gian bắt đầu cho từng VIC
  start_time=$(date +%s)

  python3 -m src.agent.deep_agent "$vic_name"

  # Thời gian kết thúc cho từng VIC
  end_time=$(date +%s)
  elapsed=$((end_time - start_time))

  echo "Finished processing VIC: $vic_name"
  echo "Time taken: $(format_time "$elapsed")"
  echo "========================================"
done

# Tổng thời gian chạy script
script_end=$(date +%s)
total_elapsed=$((script_end - script_start))

echo ""
echo "All VICs processed."
echo "Total execution time: $(format_time "$total_elapsed")"