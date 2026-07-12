from pydantic_ai import Agent

from app.agent.core.llm_router import build_model
from app.agent.core.prompt_loader import PromptLoader
from app.agent.core.prompt_renderer import PromptRenderer


async def route_skill(query: str, prompt_loader: PromptLoader, model_config: dict) -> str:
    prompt = prompt_loader.load("agents", "supervisor")
    model = build_model(**model_config)
    agent = Agent(model, system_prompt=prompt.system_prompt, defer_model_check=True)

    user_prompt = PromptRenderer.render(prompt.user_prompt_template, query=query)
    result = await agent.run(user_prompt)
    return str(result.output).strip()
