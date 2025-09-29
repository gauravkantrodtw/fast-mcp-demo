import pandas as pd
from pathlib import Path

# Base directory where our data lives
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def read_csv_summary(filename: str) -> str:
    """
    Read a CSV file and return a simple summary.
    Args:
        filename: Name of the CSV file (e.g. 'sample.csv')
    Returns:
        A string describing the file's contents.
    """
    file_path = DATA_DIR / filename
    
    # Check if file exists
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file '{filename}' not found in data directory: {DATA_DIR}")
    
    try:
        df = pd.read_csv(file_path)
        return f"CSV file '{filename}' has {len(df)} rows and {len(df.columns)} columns."
    except pd.errors.EmptyDataError:
        raise ValueError(f"CSV file '{filename}' is empty")
    except pd.errors.ParserError as e:
        raise ValueError(f"Error parsing CSV file '{filename}': {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error reading CSV file '{filename}': {e}")