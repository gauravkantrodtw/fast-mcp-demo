from databricks.sql import connect
from utils.logger import get_logger, log_success, log_error
from utils.error_handler import handle_errors, ToolExecutionError
import json
import os

logger = get_logger(__name__)

# Import the MCP server instance to register tools
from server import mcp

# Load credentials from environment variables
server_hostname = os.getenv("DATABRICKS_HOST", "itoc-dev-tw-sales-eu-central-1.cloud.databricks.com")
http_path = os.getenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/a4071df6290ef344")
client_id = os.getenv("DATABRICKS_CLIENT_ID")
client_secret = os.getenv("DATABRICKS_CLIENT_SECRET")

def _validate_credentials():
    """Validate required environment variables for Databricks connection."""
    if not client_id:
        raise ValueError("DATABRICKS_CLIENT_ID environment variable is required")
    if not client_secret:
        raise ValueError("DATABRICKS_CLIENT_SECRET environment variable is required")

def run_query(sql_statement: str):
    """Executes a SQL query on Databricks."""
    logger.info(f"Executing SQL query: {sql_statement[:100]}...")
    
    # Validate credentials before attempting connection
    _validate_credentials()
    
    try:
        with connect(
            server_hostname=server_hostname,
            http_path=http_path,
            client_id=client_id,
            client_secret=client_secret,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql_statement)
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                results = [dict(zip(columns, row)) for row in rows]
                
                logger.info(f"Query executed successfully, returned {len(results)} rows")
                return results
                
    except Exception as e:
        logger.error(f"Failed to execute SQL query: {str(e)}")
        raise

@mcp.tool()
@handle_errors("Databricks SQL execution", reraise=True)
def run_sql(query: str) -> str:
    """
    Run an arbitrary SQL query against Databricks Unity Catalog.
    
    Args:
        query: SQL query string to execute
        
    Returns:
        JSON string containing query results
        
    Example: run_sql("SELECT COUNT(*) FROM ctl_dev_sales.sch_bronze.my_table")
    """
    logger.info(f"Executing Databricks SQL query: {query[:100]}...")
    
    # Pre-flight checks
    if not query or not query.strip():
        error_msg = "❌ Invalid input: SQL query cannot be empty"
        logger.error(error_msg)
        raise ToolExecutionError(error_msg)
    
    try:
        results = run_query(query)
        
        # Format results as JSON
        json_results = json.dumps(results, indent=2, default=str)
        
        log_success(logger, f"Databricks SQL query executed successfully", 
                   rows_returned=len(results))
        return json_results
        
    except ValueError as e:
        # Input validation errors
        error_msg = f"❌ Invalid SQL query: {str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(error_msg) from e
        
    except ConnectionError as e:
        # Databricks connection errors
        error_msg = f"❌ Databricks Connection Error:\n{str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(error_msg) from e
        
    except PermissionError as e:
        # Authentication/permissions errors
        error_msg = f"❌ Databricks Authentication/Permission Error:\n{str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(error_msg) from e
        
    except Exception as e:
        # Catch-all for unexpected errors
        error_msg = (
            f"❌ Unexpected error executing Databricks SQL query:\n"
            f"   • Query: {query[:100]}...\n"
            f"   • Server: {server_hostname}\n"
            f"   • Error: {str(e)}\n"
            f"   • Please check the query syntax and try again"
        )
        log_error(logger, f"Databricks SQL execution failed", e, 
                 query=query[:100])
        raise ToolExecutionError(error_msg) from e

# Note: This module is imported by server.py to register the tools
# No standalone execution needed

