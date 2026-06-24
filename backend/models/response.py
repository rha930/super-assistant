from typing import Any, Dict, Optional

class SuccessResponse:
    """Success response model."""
    
    def __init__(self, data: Any = None, message: str = 'Success'):
        self.data = data
        self.message = message
    
    def to_dict(self) -> Dict[str, Any]:
        response = {
            'success': True,
            'message': self.message
        }
        if self.data is not None:
            response['data'] = self.data
        return response

class ErrorResponse:
    """Error response model."""
    
    def __init__(self, message: str, code: str = 'ERROR', details: Optional[Dict] = None):
        self.message = message
        self.code = code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': False,
            'message': self.message,
            'code': self.code,
            'details': self.details
        }
