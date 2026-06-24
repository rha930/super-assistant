import logging
from typing import Optional, Dict, Any
from config import DEFAULT_CONFIG
from models.message import Message
from services.strands_agent import StrandsAgentService

logger = logging.getLogger(__name__)

class ChatService:
    """Service for handling chat operations."""
    
    def __init__(self):
        self.conversations: Dict[str, list] = {}
        self.current_conversation_id: Optional[str] = None
        self.agent = StrandsAgentService()
        self.config: Dict[str, Any] = DEFAULT_CONFIG.copy()
    
    def process_message(self, message: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a user message and get a response from the Strands agent.
        
        Args:
            message: User message
            conversation_id: Optional conversation ID
        
        Returns:
            Dictionary with agent response and metadata
        """
        try:
            # Use existing or create new conversation ID
            if not conversation_id:
                conversation_id = f"conv_{len(self.conversations)}_{id(message)}"
            
            if conversation_id not in self.conversations:
                self.conversations[conversation_id] = []
            
            # Store user message
            user_msg = Message(
                role='user',
                content=message
            )
            self.conversations[conversation_id].append(user_msg.to_dict())
            
            agent_result = self.agent.invoke_agent(
                agent_id=None,
                session_id=conversation_id,
                user_message=message,
                system_prompt=self.config.get('system_prompt'),
                model=self.config.get('model'),
                temperature=self.config.get('model_parameters', {}).get('temperature', 0.7),
                top_p=self.config.get('model_parameters', {}).get('top_p', 0.9),
                max_tokens=self.config.get('model_parameters', {}).get('max_tokens', 1000)
            )
            agent_response = agent_result.get('response', '')
            
            agent_msg = Message(
                role='agent',
                content=agent_response,
                metadata=agent_result.get('metadata', {'tokens_used': 0, 'tool_calls': []})
            )
            self.conversations[conversation_id].append(agent_msg.to_dict())
            
            self.current_conversation_id = conversation_id
            
            return {
                'response': agent_response,
                'conversation_id': conversation_id,
                'metadata': agent_msg.metadata
            }
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            raise

    def start_conversation(self, message: str, conversation_id: Optional[str] = None) -> str:
        """Ensure conversation exists and append the user message."""
        if not conversation_id:
            conversation_id = f"conv_{len(self.conversations)}_{id(message)}"

        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        user_msg = Message(role='user', content=message)
        self.conversations[conversation_id].append(user_msg.to_dict())
        self.current_conversation_id = conversation_id
        return conversation_id

    def stream_message(self, message: str, conversation_id: Optional[str] = None):
        """Yield response chunks from the model and keep conversation state."""
        try:
            cid = self.start_conversation(message, conversation_id)

            stream = self.agent.stream_agent(
                user_message=message,
                system_prompt=self.config.get('system_prompt'),
                model=self.config.get('model'),
                temperature=self.config.get('model_parameters', {}).get('temperature', 0.7),
                top_p=self.config.get('model_parameters', {}).get('top_p', 0.9),
                max_tokens=self.config.get('model_parameters', {}).get('max_tokens', 1000)
            )

            for event in stream:
                yield {
                    'conversation_id': cid,
                    'chunk': event.get('chunk', ''),
                    'done': event.get('done', False),
                    'metadata': event.get('metadata', {'tool_calls': []})
                }

        except Exception as e:
            logger.error(f"Error streaming message: {e}")
            raise

    def finalize_stream_message(self, conversation_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Persist final streamed assistant message to history."""
        agent_msg = Message(
            role='agent',
            content=content,
            metadata=metadata or {'tool_calls': []}
        )
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        self.conversations[conversation_id].append(agent_msg.to_dict())
    
    def get_history(self, conversation_id: str) -> list:
        """Get conversation history."""
        return self.conversations.get(conversation_id, [])
    
    def reset(self):
        """Reset the current conversation."""
        if self.current_conversation_id:
            del self.conversations[self.current_conversation_id]
            self.current_conversation_id = None
