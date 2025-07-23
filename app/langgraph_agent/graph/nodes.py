from langgraph.graph import StateGraph
from langchain_core.runnables import RunnableLambda
from nodes.router_node import router_node_func

router_node = RunnableLambda(router_node_func)
