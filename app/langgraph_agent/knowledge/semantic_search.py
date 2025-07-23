"""
Semantic Search Module - Handles embedding-based event search
"""

import os
import json
import openai
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np
from dotenv import load_dotenv

load_dotenv()

class SemanticEventSearch:
    """
    Handles semantic search of calendar events using embeddings
    """
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.output_dir = f"user_knowledge/user_{user_id}"
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Initialize ChromaDB
        try:
            self.chroma_client = chromadb.Client(Settings(
                persist_directory=self.output_dir
            ))
            self.collection = self.chroma_client.get_or_create_collection(name="calendar_events")
        except Exception as e:
            print(f"Warning: ChromaDB initialization failed: {e}")
            self.collection = None
    
    def embed_query(self, query: str) -> Optional[List[float]]:
        """
        Create embedding for search query
        """
        try:
            response = self.openai_client.embeddings.create(
                input=[query],
                model="text-embedding-ada-002"
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error creating embedding: {e}")
            return None
    
    def semantic_search(self, query: str, limit: int = 10, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Perform semantic search on calendar events
        
        Args:
            query: Natural language search query
            limit: Maximum number of results to return
            threshold: Minimum similarity threshold (0-1)
        
        Returns:
            List of matching events with similarity scores
        """
        print(f"Performing semantic search for query: {query}")
        if not self.collection:
            return []
        
        # Create embedding for the query
        query_embedding = self.embed_query(query)
        if not query_embedding:
            return []
        
        try:
            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                include=["metadatas", "documents", "distances"]
            )
            
            # Process results
            semantic_results = []
            if results['metadatas'] and results['metadatas'][0]:
                for i, metadata in enumerate(results['metadatas'][0]):
                    # Convert distance to similarity score (ChromaDB uses cosine distance)
                    distance = results['distances'][0][i] if results['distances'] and results['distances'][0] else 1.0
                    similarity = 1 - distance  # Convert distance to similarity
                    # Apply threshold filter
                    if similarity >= threshold:
                        event_data = {
                            'event_id': metadata.get('event_id'),
                            'title': metadata.get('title'),
                            'attendees': metadata.get('attendees'),
                            'location': metadata.get('location'),
                            'start': metadata.get('start'),
                            'end': metadata.get('end'),
                            'duration_min': metadata.get('duration_min'),
                            'organizer': metadata.get('organizer'),
                            'provider': metadata.get('provider'),
                            'calendar_id': metadata.get('calendar_id'),
                            'rsvp_status': metadata.get('rsvp_status'),
                            'similarity_score': round(similarity, 3),
                            'matched_text': results['documents'][0][i] if results['documents'] and results['documents'][0] else ""
                        }
                        semantic_results.append(event_data)
            
            # Sort by similarity score (descending)
            semantic_results.sort(key=lambda x: x['similarity_score'], reverse=True)
            return semantic_results
            
        except Exception as e:
            print(f"Error performing semantic search: {e}")
            return []
    
    def is_available(self) -> bool:
        """
        Check if semantic search is available for this user
        """
        return (
            self.collection is not None and 
            os.path.exists(os.path.join(self.output_dir, "unstructured_meta.json"))
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the semantic search index
        """
        if not self.collection:
            return {"available": False, "reason": "ChromaDB not initialized"}
        
        try:
            count = self.collection.count()
            meta_file = os.path.join(self.output_dir, "unstructured_meta.json")
            meta_exists = os.path.exists(meta_file)
            
            return {
                "available": True,
                "indexed_events": count,
                "metadata_file_exists": meta_exists,
                "output_directory": self.output_dir
            }
        except Exception as e:
            return {"available": False, "reason": f"Error accessing collection: {e}"}

def format_semantic_results(results: List[Dict[str, Any]], query: str) -> str:
    """
    Format semantic search results for display
    """
    if not results:
        return f"No events found matching '{query}' using semantic search."
    
    response = f"🔍 **Semantic Search Results for '{query}'** (Found {len(results)} events):\n\n"
    
    for i, event in enumerate(results[:5], 1):
        title = event.get('title', 'Untitled Event')
        start = event.get('start', 'Unknown time')
        location = event.get('location', '')
        attendees = event.get('attendees', '')
        similarity = event.get('similarity_score', 0.0)
        provider = event.get('provider', 'Unknown')
        
        # Format date/time if available
        try:
            if start and start != 'Unknown time':
                dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%A, %d %b %Y at %H:%M')
            else:
                formatted_time = start
        except:
            formatted_time = start
        
        response += f"{i}. **{title}** (similarity: {similarity:.1%})\n"
        response += f"   📅 {formatted_time}\n"
        response += f"   🏢 {provider}\n"
        
        if location:
            response += f"   📍 {location}\n"
        
        if attendees and attendees != 'None':
            response += f"   👥 {attendees}\n"
        
        response += f"   🎯 Matched: {event.get('matched_text', '')[:100]}...\n\n"
    
    if len(results) > 5:
        response += f"... and {len(results) - 5} more events\n"
    
    return response
