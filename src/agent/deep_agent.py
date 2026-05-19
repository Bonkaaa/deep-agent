from pathlib import Path
import os

from deepagents import create_deep_agent
from deepagents.backends import StoreBackend, CompositeBackend, StateBackend
from deepagents.backends.utils import create_file_data
from langgraph.store.memory import InMemoryStore

try:
    from ..components.get_llm import get_llm
    from ..components.template import SYSTEM_PROMPT
except ImportError:
    # Allow running this file directly: `python src/agent/deep_agent.py`
    from src.components.get_llm import get_llm
    from src.components.template import SYSTEM_PROMPT

# --- CẤU HÌNH LLM & PROMPT ---
llm = get_llm()

# --- CHUẨN BỊ STORE VÀ ĐƯA FILES ĐẦU VÀO ---
store = InMemoryStore()

# Giả sử bạn đã có các file VIC: pre, post, diff tại các vị trí sau
ROOT_DIR = Path(__file__).resolve().parents[2]

pre_path = ROOT_DIR / "data" / "index_before.js"
post_path = ROOT_DIR / "data" / "index_after.js"
diff_path = ROOT_DIR / "data" / "diff.diff"

if pre_path.exists():
    store.put(namespace=("vic",), key="/pre/index_before.js",
              value=create_file_data(pre_path.read_text(encoding="utf-8")))
if post_path.exists():
    store.put(namespace=("vic",), key="/post/index_after.js",
              value=create_file_data(post_path.read_text(encoding="utf-8")))
if diff_path.exists():
    store.put(namespace=("vic",), key="/diff/diff.diff",
              value=create_file_data(diff_path.read_text(encoding="utf-8")))

# --- GẮN SKILL/KNOWLEDGE (có thể là hướng dẫn xác định source/sink) ---
skill_path = ROOT_DIR / "skills" / "source-sink" / "SKILL.md"

if skill_path.exists():
    store.put(namespace=("filesystem",), key="/skills/source-sink/SKILL.md",
              value=create_file_data(skill_path.read_text(encoding="utf-8")))

# --- KHỞI TẠO AGENT VỚI BACKEND TỔNG HỢP ---
agent = create_deep_agent(
    name="SourceSinkIdentificationAgent",
    system_prompt=SYSTEM_PROMPT,
    model=llm,
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(namespace=lambda _rt: ("memories",)),
            "/vic/": StoreBackend(namespace=lambda _rt: ("vic",)),  # Route VIC files through store
            "/filesystem/": StoreBackend(namespace=lambda _rt: ("filesystem",)),  # Route skill files through store
        }
    ),
    store=store,
)

if __name__ == "__main__":
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Please analyze the provided pre-VIC, post-VIC, and diff files to identify the top 5 most suspicious source-sink pairs related to taint flows.\n"
                        "Focus on changes introduced by the vulnerability-inducing commit and document your findings according to the instructions in the SKILL.md.\n\n"
                        "Use these exact store paths and do not guess alternative file names:\n"
                        "- /vic/pre/index_before.js\n"
                        "- /vic/post/index_after.js\n"
                        "- /vic/diff/diff.diff\n"
                        "- /filesystem/skills/source-sink/SKILL.md\n\n"
                    )
                }
            ]
        },
        config=
            {"configurable": {
                "thread_id": "12345", 
                "recursion_limit": 50,
                "max_steps": 50,
                }
            }
    )

    # Save result to a file for review
    output_path = ROOT_DIR / "output" / "source_sink_analysis_result.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(result))
        

    print("Final Result:")
    print(result)
    # print("Store contents:")
    # for ns in store._data:
    #     print(f"Namespace: {ns}")
    #     for k in store._data[ns]:
    #         print(f"  Key: {k}")
