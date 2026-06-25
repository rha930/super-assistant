import logging
from typing import Optional, Dict, Any
from config import DEFAULT_CONFIG
from models.message import Message
from services.strands_agent import StrandsAgentService
from services.graph_artifact_service import GraphArtifactService

logger = logging.getLogger(__name__)

class ChatService:
    """Service for handling chat operations."""
    
    def __init__(self):
        self.conversations: Dict[str, list] = {}
        self.current_conversation_id: Optional[str] = None
        self.agent = StrandsAgentService()
        self.graph_artifact_service = GraphArtifactService()
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

            history = self._build_context_history(conversation_id)
            context_cfg = self.config.get('context_config', {})
            
            agent_result = self.agent.invoke_agent(
                agent_id=None,
                session_id=conversation_id,
                user_message=message,
                system_prompt=self.config.get('system_prompt'),
                conversation_history=history,
                model=self.config.get('model'),
                temperature=self.config.get('model_parameters', {}).get('temperature', 0.7),
                top_p=self.config.get('model_parameters', {}).get('top_p', 0.9),
                max_tokens=self.config.get('model_parameters', {}).get('max_tokens', 1000),
                context_max_messages=context_cfg.get('max_messages', 12),
                context_max_input_chars=context_cfg.get('max_input_chars', 12000)
            )
            agent_response = agent_result.get('response', '')
            artifacts = self.graph_artifact_service.create_graph_artifacts(message, agent_response)
            logger.info(
                "Graph artifacts generated (sync): conversation_id=%s count=%s",
                conversation_id,
                len(artifacts)
            )
            context_meta = {
                'history_message_count': len(history),
                'context_max_messages': context_cfg.get('max_messages', 12),
                'context_max_input_chars': context_cfg.get('max_input_chars', 12000)
            }
            
            agent_msg = Message(
                role='agent',
                content=agent_response,
                metadata={
                    **agent_result.get('metadata', {'tokens_used': 0, 'tool_calls': []}),
                    'artifacts': artifacts,
                    'context': context_meta
                }
            )
            self.conversations[conversation_id].append(agent_msg.to_dict())
            
            self.current_conversation_id = conversation_id
            
            return {
                'response': agent_response,
                'conversation_id': conversation_id,
                'metadata': agent_msg.metadata,
                'artifacts': artifacts
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
            history = self._build_context_history(cid)
            context_cfg = self.config.get('context_config', {})

            stream = self.agent.stream_agent(
                user_message=message,
                system_prompt=self.config.get('system_prompt'),
                conversation_history=history,
                model=self.config.get('model'),
                temperature=self.config.get('model_parameters', {}).get('temperature', 0.7),
                top_p=self.config.get('model_parameters', {}).get('top_p', 0.9),
                max_tokens=self.config.get('model_parameters', {}).get('max_tokens', 1000),
                context_max_messages=context_cfg.get('max_messages', 12),
                context_max_input_chars=context_cfg.get('max_input_chars', 12000)
            )

            for event in stream:
                metadata = event.get('metadata', {'tool_calls': []})
                done = event.get('done', False)

                if done:
                    # Build artifacts from final response content for deterministic done payload delivery.
                    # The route aggregates chunks and persists the final message content.
                    metadata = {
                        **metadata,
                        'artifacts': []
                    }

                yield {
                    'conversation_id': cid,
                    'chunk': event.get('chunk', ''),
                    'done': done,
                    'metadata': {
                        **metadata,
                        'context': {
                            'history_message_count': len(history),
                            'context_max_messages': context_cfg.get('max_messages', 12),
                            'context_max_input_chars': context_cfg.get('max_input_chars', 12000)
                        }
                    }
                }

        except Exception as e:
            logger.error(f"Error streaming message: {e}")
            raise

    def finalize_stream_message(self, conversation_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Persist final streamed assistant message to history."""
        conversation_messages = self.conversations.get(conversation_id, [])
        user_prompt = ''
        if conversation_messages:
            for msg in reversed(conversation_messages):
                if msg.get('role') == 'user':
                    user_prompt = msg.get('content', '')
                    break

        artifacts = self.graph_artifact_service.create_graph_artifacts(user_prompt, content)
        logger.info(
            "Graph artifacts generated (stream): conversation_id=%s count=%s",
            conversation_id,
            len(artifacts)
        )

        agent_msg = Message(
            role='agent',
            content=content,
            metadata={
                **(metadata or {'tool_calls': []}),
                'artifacts': artifacts
            }
        )
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        self.conversations[conversation_id].append(agent_msg.to_dict())

        return artifacts
    
    def get_history(self, conversation_id: str) -> list:
        """Get conversation history."""
        return self.conversations.get(conversation_id, [])

    def _build_context_history(self, conversation_id: str) -> list:
        """Build bounded conversation history for agent context, excluding newest user turn."""
        messages = self.conversations.get(conversation_id, [])
        if not messages:
            return []

        # Exclude latest user turn because it is passed separately as user_message.
        trimmed = messages[:-1] if len(messages) > 0 else []
        return trimmed
    
    def reset(self):
        """Reset the current conversation."""
        if self.current_conversation_id:
            del self.conversations[self.current_conversation_id]
            self.current_conversation_id = None
