import os
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# Initialize the OpenAI model
# It uses the OPENAI_API_KEY environment variable by default
api_key = os.getenv("OPENAI_API_KEY") or "mock-key"

# Create the ChatOpenAI model
model = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
    temperature=0.0,
    openai_api_key=api_key
)

# Placeholder system prompt for Phase 4.2
SYSTEM_PROMPT = "You are a helpful assistant for customer issues and account management."

# Create the agent using create_agent
agent = create_agent(
    model=model,
    tools=[],
    system_prompt=SYSTEM_PROMPT
)

async def respond(message: str) -> str:
    """
    Invokes the LangChain agent with the user message
    and returns the final AI reply content.
    """
    input_data = {"messages": [HumanMessage(content=message)]}
    result = await agent.ainvoke(input_data)
    
    messages = result.get("messages", [])
    if messages:
        return messages[-1].content
    return "No response generated."
