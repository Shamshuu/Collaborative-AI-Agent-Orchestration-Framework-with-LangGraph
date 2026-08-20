import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Tracks attempts for flaky simulation
flaky_tool_attempts: Dict[str, int] = {}


def reset_flaky_attempts():
    """Reset attempts dictionary (useful for testing)."""
    global flaky_tool_attempts
    flaky_tool_attempts.clear()


def simulated_search_tool(query: str) -> str:
    """
    Simulated web search tool providing technical information on AI agent frameworks.
    Simulates transient network failures when query is '__FLAKY_TEST__'.
    """
    cleaned_query = query.strip()
    
    # Flaky network simulation
    if "__FLAKY_TEST__" in cleaned_query:
        attempts = flaky_tool_attempts.get(cleaned_query, 0)
        if attempts == 0:
            flaky_tool_attempts[cleaned_query] = 1
            raise Exception("Simulated transient network timeout.")
        
        flaky_tool_attempts[cleaned_query] = attempts + 1
        return (
            "Search results retrieved on second attempt: "
            "LangGraph enables cyclic graphs and granular multi-agent state machines with persistence and human-in-the-loop gates. "
            "CrewAI provides role-based persona orchestration with sequential/hierarchical process structures."
        )

    # Standard technical query knowledge base
    query_lower = cleaned_query.lower()
    if "langgraph" in query_lower or "crewai" in query_lower or "comparison" in query_lower:
        return (
            "LangGraph Technical Findings:\n"
            "- Architecture: Built on LangChain, uses cyclic state graphs (StateGraph) where agents/tools are nodes and edges represent transitions.\n"
            "- State & Persistence: Native checkpointers (Postgres, SQLite, Memory) allowing time-travel, replay, and human-in-the-loop interrupts.\n"
            "- Orchestration Style: Low-level, highly customizable state machines, multi-agent branching, conditional routing, and parallel fan-out.\n\n"
            "CrewAI Technical Findings:\n"
            "- Architecture: High-level role-playing agent abstraction (Agent, Task, Crew, Process).\n"
            "- Process Execution: Sequential and Hierarchical manager-led agent collaboration.\n"
            "- Memory & Tools: Built-in short-term, long-term, and entity memory systems with seamless tool integration.\n"
            "- Orchestration Style: Persona-driven delegation with higher-level developer ergonomics."
        )

    return f"Technical research findings on '{cleaned_query}': Agent orchestration frameworks provide modular decomposition of complex AI workflows into collaborative specialized agents with persistent state and tool augmentation."
