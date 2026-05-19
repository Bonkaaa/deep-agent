from deepagents import create_deep_agent
from deepagents.backends import StoreBackend, CompositeBackend, StateBackend
from deepagents.backends.utils import create_file_data
from langgraph.store.memory import InMemoryStore

from ..components.get_llm import get_llm
from ..components.template import SYSTEM_PROMPT

from pathlib import Path
import os

# --- CẤU HÌNH LLM & PROMPT ---
llm = get_llm(model_name="gpt-oss:20b", temperature=0.7)

# --- CHUẨN BỊ STORE VÀ ĐƯA FILES ĐẦU VÀO ---
store = InMemoryStore()

# Giả sử bạn đã có các file VIC: pre, post, diff tại các vị trí sau
pre_path = Path("C:\\deep_agent\\data\\index_before.js")
post_path = Path("C:\\deep_agent\\data\\index_after.js")
diff_path = Path("C:\\deep_agent\\data\\diff.diff")

if pre_path.exists():
    store.put(namespace=("vic", "pre"), key=pre_path.name, value=create_file_data(pre_path.read_text(encoding="utf-8")))
if post_path.exists():
    store.put(namespace=("vic", "post"), key=post_path.name, value=create_file_data(post_path.read_text(encoding="utf-8")))
if diff_path.exists():
    store.put(namespace=("vic", "diff"), key=diff_path.name, value=create_file_data(diff_path.read_text(encoding="utf-8")))

# --- GẮN SKILL/KNOWLEDGE (có thể là hướng dẫn xác định source/sink) ---
skill_path = Path("C:\\deep_agent\\skills\\source-sink\\SKILL.md")
if skill_path.exists():
    store.put(namespace=("filesystem",), key="./skills/source-sink/SKILL.md", value=create_file_data(skill_path.read_text(encoding="utf-8")))

# --- KHỞI TẠO AGENT VỚI BACKEND TỔNG HỢP ---
agent = create_deep_agent(
    name="SourceSinkIdentificationAgent",
    system_prompt=SYSTEM_PROMPT,
    model=llm,
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(namespace=lambda _rt: ("memories",)),
            "/vic/": StoreBackend(namespace=lambda _rt: ("vic",)),  # Route VIC files qua store
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
                        "Please analyze the provided pre-VIC, post-VIC, and diff files to identify the top 5 most suspicious source-sink pairs related to taint flows. "
                        "Focus on changes introduced by the vulnerability-inducing commit and document your findings according to the instructions in the SKILL.md."
                    )
                }
            ]
        },
        config={"configurable": {"thread_id": "12345", "recursion_limit": "10000"}}
    )

    print("Final Result:")
    print(result)