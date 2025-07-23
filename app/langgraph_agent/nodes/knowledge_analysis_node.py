"""
Knowledge Analysis Node - Sets up semantic search capabilities
"""

import os
import subprocess
import sys
from typing import Dict, Any
from pathlib import Path
from langsmith import traceable
from app.langgraph_agent.knowledge.semantic_search import SemanticEventSearch

@traceable(name="knowledge_analysis_node")
def knowledge_analysis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set up semantic search capabilities for the user's calendar
    """
    user_id = state.get("user_id")
    
    if not user_id:
        return {
            **state,
            "response": "Error: User ID is required for knowledge analysis",
            "error": "Missing user_id"
        }
    
    try:
        # First check if semantic search is already available
        semantic_search = SemanticEventSearch(user_id=user_id)
        stats = semantic_search.get_stats()
        
        if stats.get("available", False):
            indexed_events = stats.get("indexed_events", 0)
            response = f"✅ **Semantic search is already available!**\n\n"
            response += f"📊 **Statistics:**\n"
            response += f"   • {indexed_events} events indexed\n"
            response += f"   • Directory: {stats.get('output_directory', 'Unknown')}\n\n"
            response += f"🔍 **You can now use smart search queries like:**\n"
            response += f"   • 'meetings with John'\n"
            response += f"   • 'project discussions last week'\n"
            response += f"   • 'lunch appointments'\n"
            response += f"   • 'recurring standup meetings'\n"
            
            return {
                **state,
                "response": response,
                "status": "completed"
            }
        
        # Run knowledge analysis
        response = "🚀 **Setting up semantic search for your calendar...**\n\n"
        response += "This process will:\n"
        response += "• Analyze all your calendar events\n"
        response += "• Create semantic embeddings for smart search\n"
        response += "• Enable natural language queries\n\n"
        response += "⏳ Processing... (this may take a few minutes)\n"
        
        # Get the project root directory
        project_root = Path(__file__).parent.parent.parent.parent
        analysis_script = project_root / "app" / "langgraph_agent" / "knowledge" / "unstructured_analysis.py"
        
        if not analysis_script.exists():
            return {
                **state,
                "response": f"❌ **Error**: Analysis script not found at {analysis_script}",
                "error": "Script not found"
            }
        
        # Run the analysis script
        result = subprocess.run(
            [sys.executable, str(analysis_script), str(user_id)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            # Check the results
            semantic_search_new = SemanticEventSearch(user_id=user_id)
            new_stats = semantic_search_new.get_stats()
            
            if new_stats.get("available", False):
                indexed_events = new_stats.get("indexed_events", 0)
                response = "✅ **Semantic search setup completed successfully!**\n\n"
                response += f"📊 **Statistics:**\n"
                response += f"   • {indexed_events} events processed and indexed\n"
                response += f"   • Directory: {new_stats.get('output_directory', 'Unknown')}\n\n"
                response += f"🔍 **You can now use smart search queries like:**\n"
                response += f"   • 'meetings with John'\n"
                response += f"   • 'project discussions last week'\n"
                response += f"   • 'lunch appointments'\n"
                response += f"   • 'recurring standup meetings'\n\n"
                response += f"💡 **Tip**: The system will automatically use semantic search when you perform text-based queries!"
            else:
                response = "⚠️ **Setup completed but semantic search is not available.**\n\n"
                response += f"Reason: {new_stats.get('reason', 'Unknown error')}"
        else:
            response = "❌ **Knowledge analysis failed**\n\n"
            response += f"Error details:\n"
            response += f"Return code: {result.returncode}\n"
            if result.stderr:
                response += f"Error: {result.stderr[:500]}...\n"
            if result.stdout:
                response += f"Output: {result.stdout[:500]}...\n"
        
        return {
            **state,
            "response": response,
            "status": "completed" if result.returncode == 0 else "failed"
        }
        
    except subprocess.TimeoutExpired:
        return {
            **state,
            "response": "❌ **Knowledge analysis timed out** (5 minute limit exceeded)\n\nPlease try again or contact support.",
            "error": "Timeout"
        }
    except Exception as e:
        return {
            **state,
            "response": f"❌ **Error setting up semantic search**: {str(e)}",
            "error": str(e)
        }
