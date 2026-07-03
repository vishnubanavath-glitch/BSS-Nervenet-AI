import logging
from database_mcp.tools.registry import mcp
from database_mcp.privacy import privacy_engine

logger = logging.getLogger(__name__)

@mcp.tool()
async def tokenize_text(text: str) -> dict:
    """Finds sensitive patterns (UIDs, Mobile numbers) in raw text and replaces them with tokens.
    
    Args:
        text: Raw text containing sensitive PII values.
        
    Returns:
        A dict containing success status and the tokenized text output.
    """
    try:
        tokenized = privacy_engine.tokenize_text(text)
        return {
            "success": True,
            "tokenized_text": tokenized
        }
    except Exception as e:
        logger.error(f"Error in tokenize_text tool: {e}", exc_info=True)
        return {
            "success": False,
            "error": {
                "code": "PRIVACY_ERROR",
                "message": str(e),
                "category": "Privacy"
            }
        }

@mcp.tool()
async def detokenize_text(text: str) -> dict:
    """Replaces all tokens of the form <//PREFIX-UUID//> back to their original values in a text block.
    
    Args:
        text: Text containing tokens to be detokenized.
        
    Returns:
        A dict containing success status and the decrypted/detokenized text.
    """
    try:
        detokenized = privacy_engine.detokenize_text(text)
        return {
            "success": True,
            "detokenized_text": detokenized
        }
    except Exception as e:
        logger.error(f"Error in detokenize_text tool: {e}", exc_info=True)
        return {
            "success": False,
            "error": {
                "code": "PRIVACY_ERROR",
                "message": str(e),
                "category": "Privacy"
            }
        }
