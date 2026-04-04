"""
Custom exception classes for DocuMind error handling.
"""


class DocuMindException(Exception):
    """Base exception for DocuMind."""
    pass


class OpenAIQuotaExceededException(DocuMindException):
    """Raised when OpenAI API quota is exceeded."""
    
    def __init__(self, message: str = None):
        if message is None:
            message = "OpenAI API quota exceeded. Please check your billing and add credits at https://platform.openai.com/account/billing/overview"
        super().__init__(message)
        self.user_facing_message = message


class OpenAIAPIError(DocuMindException):
    """Raised when OpenAI API call fails."""
    
    def __init__(self, message: str = None):
        if message is None:
            message = "OpenAI API error. Please try again or contact support."
        super().__init__(message)
        self.user_facing_message = message


class PipelineException(DocuMindException):
    """Raised when the RAG pipeline fails."""
    
    def __init__(self, message: str = None):
        if message is None:
            message = "Pipeline execution failed. Please try again."
        super().__init__(message)
        self.user_facing_message = message
