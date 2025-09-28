from utils.file_reader import read_csv_summary
from utils.logger import get_logger, log_success, log_error
from utils.error_handler import handle_errors, ToolExecutionError

logger = get_logger(__name__)

# Import the MCP server instance to register tools
from server import mcp

@mcp.tool()
@handle_errors("CSV file summarization", reraise=True)
def summarize_csv_file(filename: str) -> str:
    """
    Summarize a CSV file by reporting its number of rows and columns.
    Args:
        filename: Name of the CSV file in the /data directory (e.g., 'sample.csv')
    Returns:
        A string describing the file's dimensions.
    """
    logger.info(f"Processing CSV file: {filename}")
    
    try:
        result = read_csv_summary(filename)
        log_success(logger, f"Processed CSV file: {filename}")
        return result
    except Exception as e:
        log_error(logger, f"CSV file processing failed", e, filename=filename)
        raise ToolExecutionError(f"Failed to process CSV file {filename}: {e}") from e