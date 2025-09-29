from utils.s3_csv_processor import read_s3_csv_chunk, get_basic_info, format_basic_report
from utils.logger import get_logger, log_success, log_error
from utils.error_handler import handle_errors, ToolExecutionError
import os

logger = get_logger(__name__)

# Import the MCP server instance to register tools
from server import mcp

@mcp.tool()
@handle_errors("S3 CSV analysis", reraise=True)
def analyze_s3_csv(bucket_name: str, file_key: str) -> str:
    """
    Get basic information from a CSV file stored in AWS S3.

    Args:
        bucket_name: Name of the S3 bucket containing the CSV file
        file_key: S3 object key (path) to the CSV file

    Returns:
        Basic info: count, columns, and sample 50 records.
    """
    file_path = f"s3://{bucket_name}/{file_key}"
    logger.info(f"Getting basic info from S3 CSV: {file_path}")

    # Pre-flight checks
    aws_region = os.getenv("AWS_REGION", "eu-central-1")
    logger.info(f"Using AWS region: {aws_region}")

    try:
        df_chunk = read_s3_csv_chunk(bucket_name, file_key, chunk_size=1000)
        info = get_basic_info(df_chunk)
        sample_data = df_chunk.head(50).to_dict("records")
        
        report = format_basic_report(file_path, info, sample_data)
        
        log_success(logger, f"Processed S3 CSV chunk", 
                   rows=info['total_rows'], columns=info['total_columns'])
        return report

    except ValueError as e:
        # Input validation errors
        error_msg = f"❌ Invalid input parameters: {str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(error_msg) from e
        
    except PermissionError as e:
        # AWS credentials/permissions errors
        error_msg = f"❌ AWS Authentication/Permission Error:\n{str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(error_msg) from e
        
    except ConnectionError as e:
        # AWS S3 specific errors (bucket not found, access denied, etc.)
        error_msg = f"❌ AWS S3 Error:\n{str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(error_msg) from e
        
    except FileNotFoundError as e:
        # File not found errors
        error_msg = f"❌ File Not Found:\n{str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(error_msg) from e
        
    except Exception as e:
        # Catch-all for unexpected errors
        error_msg = (
            f"❌ Unexpected error analyzing S3 CSV file:\n"
            f"   • File: {file_path}\n"
            f"   • AWS Region: {aws_region}\n"
            f"   • Error: {str(e)}\n"
            f"   • Please check the file format and try again"
        )
        log_error(logger, f"S3 CSV processing failed", e, 
                 bucket=bucket_name, file_key=file_key)
        raise ToolExecutionError(error_msg) from e
