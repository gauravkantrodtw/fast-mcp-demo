import logging
import pandas as pd
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
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
        
    Raises:
        ValueError: For invalid parameters
        FileNotFoundError: If the S3 object doesn't exist
        PermissionError: If access is denied
        ConnectionError: If there are network/connection issues
        Exception: For other unexpected errors
    """
    logger.info(f"Reading CSV chunk from S3: s3://{bucket_name}/{file_key}")
    
    # Validate inputs
    if not bucket_name or not file_key:
        raise ValueError("Both bucket_name and file_key must be provided and non-empty")
    
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    
    try:
        # Attempt to get the S3 object
        obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        
        # Read and parse CSV
        csv_data = obj["Body"].read()
        if not csv_data:
            raise ValueError(f"CSV file is empty: s3://{bucket_name}/{file_key}")
            
        df = pd.read_csv(BytesIO(csv_data), nrows=chunk_size)
        
        logger.info(f"Loaded chunk: {df.shape[0]} rows, {df.shape[1]} columns")
        return df
        
    except NoCredentialsError:
        error_msg = (
            "❌ AWS credentials not found. Please configure AWS credentials using one of:\n"
            "   • AWS CLI: `aws configure`\n"
            "   • Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY\n"
            "   • IAM role (if running on EC2/Lambda)\n"
            "   • AWS profile: set AWS_PROFILE environment variable"
        )
        logger.error(error_msg)
        raise PermissionError(error_msg)
        
    except PartialCredentialsError as e:
        error_msg = (
            f"❌ Incomplete AWS credentials. Missing: {e}\n"
            "Please provide all required AWS credentials:\n"
            "   • AWS_ACCESS_KEY_ID\n"
            "   • AWS_SECRET_ACCESS_KEY\n"
            "   • AWS_SESSION_TOKEN (if using temporary credentials)"
        )
        logger.error(error_msg)
        raise PermissionError(error_msg)
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        if error_code == 'NoSuchBucket':
            error_msg = (
                f"❌ S3 bucket not found: '{bucket_name}'\n"
                f"   • Check if the bucket name is correct\n"
                f"   • Verify the bucket exists in the current AWS region\n"
                f"   • Current region: {s3_client.meta.region_name}"
            )
        elif error_code == 'NoSuchKey':
            error_msg = (
                f"❌ S3 object not found: s3://{bucket_name}/{file_key}\n"
                f"   • Check if the file path is correct\n"
                f"   • Verify the file exists in the bucket\n"
                f"   • Check for typos in the file key"
            )
        elif error_code == 'AccessDenied':
            error_msg = (
                f"❌ Access denied to s3://{bucket_name}/{file_key}\n"
                f"   • Check if your AWS credentials have s3:GetObject permission\n"
                f"   • Verify the bucket policy allows access\n"
                f"   • Ensure you're using the correct AWS account"
            )
        elif error_code == 'InvalidAccessKeyId':
            error_msg = (
                f"❌ Invalid AWS Access Key ID\n"
                f"   • Check your AWS_ACCESS_KEY_ID environment variable\n"
                f"   • Verify the access key is correct and active"
            )
        elif error_code == 'SignatureDoesNotMatch':
            error_msg = (
                f"❌ AWS signature mismatch\n"
                f"   • Check your AWS_SECRET_ACCESS_KEY\n"
                f"   • Verify the secret key corresponds to the access key\n"
                f"   • Ensure your system clock is synchronized"
            )
        elif error_code == 'TokenRefreshRequired':
            error_msg = (
                f"❌ AWS session token expired\n"
                f"   • Refresh your temporary credentials\n"
                f"   • Update AWS_SESSION_TOKEN if using temporary credentials"
            )
        else:
            error_msg = (
                f"❌ AWS S3 error ({error_code}): {error_message}\n"
                f"   • Check AWS documentation for error code: {error_code}\n"
                f"   • Verify your AWS configuration and permissions"
            )
        
        logger.error(error_msg)
        raise ConnectionError(error_msg) from e
        
    except Exception as e:
        error_msg = (
            f"❌ Unexpected error reading S3 CSV: {str(e)}\n"
            f"   • File: s3://{bucket_name}/{file_key}\n"
            f"   • Check if the file is a valid CSV format\n"
            f"   • Verify network connectivity to AWS S3"
        )
        logger.error(error_msg)
        raise Exception(error_msg) from e


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
