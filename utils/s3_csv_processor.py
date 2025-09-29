import logging
import pandas as pd
import boto3
from botocore.config import Config
from io import BytesIO
from typing import Dict, Any, List
import os

logger = logging.getLogger(__name__)

# Cold start optimization: Create optimized S3 client at module level
# This ensures the client is initialized once per Lambda container
s3_client = boto3.client(
    "s3",
    config=Config(
        # Connection pooling for better performance
        max_pool_connections=50,
        # Retry configuration
        retries={'max_attempts': 3, 'mode': 'adaptive'},
        # Keep-alive for persistent connections
        tcp_keepalive=True,
        # Region configuration from environment
        region_name=os.getenv("AWS_REGION", "eu-central-1")
    )
)


def read_s3_csv_chunk(bucket_name: str, file_key: str, chunk_size: int = 1000) -> pd.DataFrame:
    """
    Read CSV file from S3 in chunks and return first chunk.
    
    Args:
        bucket_name: S3 bucket name
        file_key: S3 object key
        chunk_size: Size of chunk to read
        
    Returns:
        pandas DataFrame (first chunk)
    """
    logger.info(f"Reading CSV chunk from S3: s3://{bucket_name}/{file_key}")
    
    obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    df = pd.read_csv(BytesIO(obj["Body"].read()), nrows=chunk_size)
    
    logger.info(f"Loaded chunk: {df.shape[0]} rows, {df.shape[1]} columns")
    return df


def get_basic_info(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Get basic information from a pandas DataFrame.
    
    Args:
        df: pandas DataFrame to analyze
        
    Returns:
        Dictionary containing basic info
    """
    total_rows, total_columns = df.shape
    
    return {
        "total_rows": total_rows,
        "total_columns": total_columns,
        "columns": list(df.columns),
    }


def format_basic_report(
    file_path: str,
    info: Dict[str, Any],
    sample_data: List[Dict[str, Any]],
) -> str:
    """
    Format basic information into a simple report.
    
    Args:
        file_path: Full S3 file path
        info: Basic info from get_basic_info
        sample_data: Sample data rows
        
    Returns:
        Formatted report string
    """
    sample_lines = [
        f"  Row {i}:\n" + "\n".join(
            f"    {col}: {str(value)[:47] + '...' if len(str(value)) > 50 else value}"
            for col, value in row.items()
        )
        for i, row in enumerate(sample_data, 1)
    ]
    
    return "\n".join([
        "📊 S3 CSV Basic Info",
        "===================",
        f"📁 File: {file_path}",
        f"📊 Count: {info['total_rows']:,} rows",
        f"📋 Columns: {info['total_columns']} ({', '.join(info['columns'])})",
        f"\n📄 Sample Data (first {len(sample_data)} rows):",
        *sample_lines,
    ])
