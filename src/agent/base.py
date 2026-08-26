from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Type

from pydantic import BaseModel
from deepagents import create_deep_agent
from deepagents.backends import StoreBackend, CompositeBackend, StateBackend, FilesystemBackend
from langgraph.store.memory import InMemoryStore

try:
    from .. import artifacts
    from ..components.get_llm import get_llm
    from ..utils import setup_logger, collect_tool_calls
    from ..config import ROOT_DIR
except ImportError:
    from src import artifacts
    from src.components.get_llm import get_llm
    from src.utils import setup_logger, collect_tool_calls
    from src.config import ROOT_DIR


class AgentOutputError(RuntimeError):
    """Raised when the agent does not return a valid structured output."""
    pass


class BaseVICAgent(ABC):
    stage: str
    agent_name: str
    system_prompt: str
    response_format: Type[BaseModel]
    skill_name: str | None = None

    def __init__(self, vic: str | None = None):
        self._require_class_attrs()
        self.vic = vic
        self.llm = get_llm()
        self.store = InMemoryStore()
        self.agent = None
        self.iteration = 1
        
        # Setup specific logger per agent
        self.logger = setup_logger(f"{self.skill_name or self.stage}.log", f"{self.agent_name}Logger")
        
        if self.vic:
            self.agent = self.create_agent()

    def _require_class_attrs(self):
        required = ["stage", "agent_name", "system_prompt", "response_format"]
        for attr in required:
            if not hasattr(self, attr):
                raise TypeError(f"Class {self.__class__.__name__} must define class attribute '{attr}'.")

    @property
    def skill_dir(self) -> Path:
        return Path(ROOT_DIR) / "skills" / (self.skill_name or self.stage)

    @property
    def thread_id(self) -> str:
        return f"{self.vic}-{self.stage}-{self.iteration}"

    def extra_routes(self) -> dict[str, FilesystemBackend]:
        return {}

    def tools(self) -> list[Any] | None:
        return None

    def create_agent(self):
        routes = {
            "/memories/": StoreBackend(namespace=lambda _rt: ("memories",)),
            "/vic/": FilesystemBackend(root_dir=Path(ROOT_DIR) / "data" / self.vic, virtual_mode=True),
            "/skills/": FilesystemBackend(root_dir=self.skill_dir, virtual_mode=True),
        }
        routes.update(self.extra_routes())

        return create_deep_agent(
            name=self.agent_name,
            system_prompt=self.system_prompt,
            model=self.llm,
            backend=CompositeBackend(
                default=StateBackend(),
                routes=routes,
            ),
            store=self.store,
            response_format=self.response_format,
            skills=[f"/skills/{self.skill_name or self.stage}"],
            tools=self.tools(),
        )

    def invoke_config(self, thread_id: str | None = None) -> dict:
        t_id = thread_id or self.thread_id
        return {
            "configurable": {
                "thread_id": t_id,
                "recursion_limit": 50,
                "max_steps": 50,
            }
        }

    def _extract(self, result: Any) -> BaseModel:
        if not isinstance(result, Mapping):
            raise AgentOutputError(f"{self.stage}: agent returned {type(result).__name__}, expected a mapping.")
        
        payload = None
        for key in ("structured_response", "structured_output"):
            if result.get(key) is not None:
                payload = result[key]
                break
        else:
            raise AgentOutputError(
                f"{self.stage}: no structured response for {self.vic!r} "
                f"(keys present: {sorted(result)}). The model returned no validated output."
            )
        
        if isinstance(payload, self.response_format):
            return payload
        return self.response_format.model_validate(payload)

    def _persist(self, result: Any, structured: BaseModel):
        # Persist structured output using artifacts registry
        artifacts.write_result(self.vic, self.stage, structured, self.iteration)
        
        # Persist tool calls using artifacts registry
        tool_calls = collect_tool_calls(result)
        artifacts.write_tool_calls(self.vic, self.stage, tool_calls, self.iteration)

    @abstractmethod
    def task_message(self, *args, **kwargs) -> str:
        pass

    def run(self, *args, **kwargs) -> dict:
        # Determine data_name (vic)
        if not self.vic:
            if args:
                self.vic = args[0]
                args = args[1:]
            elif "data_name" in kwargs:
                self.vic = kwargs.pop("data_name")
            else:
                raise ValueError("VIC name must be provided (either via __init__ or run args).")
        
        # Ensure agent is instantiated
        if not self.agent:
            self.agent = self.create_agent()

        self.logger.info(f"Running {self.agent_name} for VIC: {self.vic}")

        # Construct prompt
        user_prompt = self.task_message(*args, **kwargs)

        try:
            t_id = kwargs.get("thread_id") or self.thread_id
            config = self.invoke_config(thread_id=t_id)

            result = self.agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": user_prompt
                        }
                    ]
                },
                config=config
            )
            self.logger.info(f"Successfully invoked the agent. Result: {result}")
        except Exception as e:
            self.logger.error(f"Error during agent invocation: {str(e)}")
            raise

        # Extract structured response to validate
        structured = self._extract(result)
        
        # Persist output
        self._persist(result, structured)
        
        return result


class AsyncVICAgent(BaseVICAgent):
    
    async def create_agent_async(self):
        routes = {
            "/memories/": StoreBackend(namespace=lambda _rt: ("memories",)),
            "/vic/": FilesystemBackend(root_dir=Path(ROOT_DIR) / "data" / self.vic, virtual_mode=True),
            "/skills/": FilesystemBackend(root_dir=self.skill_dir, virtual_mode=True),
        }
        routes.update(self.extra_routes())

        tools = await self.tools_async()

        return create_deep_agent(
            name=self.agent_name,
            system_prompt=self.system_prompt,
            model=self.llm,
            backend=CompositeBackend(
                default=StateBackend(),
                routes=routes,
            ),
            store=self.store,
            response_format=self.response_format,
            skills=[f"/skills/{self.skill_name or self.stage}"],
            tools=tools,
        )

    async def tools_async(self) -> list[Any] | None:
        return None

    def create_agent(self):
        raise NotImplementedError("Use create_agent_async() for AsyncVICAgent.")

    async def run(self, *args, **kwargs) -> dict:
        # Determine data_name (vic)
        if not self.vic:
            if args:
                self.vic = args[0]
                args = args[1:]
            elif "data_name" in kwargs:
                self.vic = kwargs.pop("data_name")
            else:
                raise ValueError("VIC name must be provided (either via __init__ or run args).")

        if "iteration" in kwargs:
            self.iteration = kwargs["iteration"]

        # Ensure agent is instantiated (async)
        if not self.agent:
            self.agent = await self.create_agent_async()

        self.logger.info(f"Running {self.agent_name} (async) for VIC: {self.vic}")

        # Construct prompt
        user_prompt = self.task_message(*args, **kwargs)

        try:
            t_id = kwargs.get("thread_id") or self.thread_id
            config = self.invoke_config(thread_id=t_id)

            result = await self.agent.ainvoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": user_prompt
                        }
                    ]
                },
                config=config
            )
            self.logger.info(f"Successfully invoked the agent (async). Result: {result}")
        except Exception as e:
            self.logger.error(f"Error during async agent invocation: {str(e)}")
            raise

        # Extract structured response to validate
        structured = self._extract(result)
        
        # Persist output
        self._persist(result, structured)
        
        return result
