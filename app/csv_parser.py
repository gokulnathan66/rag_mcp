"""
CSV Parser Component

This module provides functionality for reading and parsing CSV files,
handling various encodings, delimiters, and error conditions.
"""

import csv
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

import logfire

from .models import CSVDocument
from .config import ServerConfig
from .errors import FileAccessError, CSVParsingError


logger = logging.getLogger(__name__)


class CSVParser:
    """
    CSV Parser component for reading and parsing CSV files.
    
    Responsibilities:
    - Read CSV files with configurable delimiters and encodings
    - Handle file access errors (not found, permissions)
    - Parse CSV rows into structured CSVDocument format
    - Generate unique document IDs for each row
    - Preserve row metadata (row_number, source_file)
    """
    
    def __init__(self, config: ServerConfig):
        """
        Initialize CSV parser with configuration.
        
        Args:
            config: Server configuration containing CSV settings
        """
        self.config = config
        self.delimiter = config.csv_delimiter
        self.encoding = config.csv_encoding
        self.column_mapping = config.csv_column_mapping or {}
        
    def read_csv_file(
        self,
        file_path: str,
        delimiter: Optional[str] = None,
        encoding: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Read a CSV file and return rows as list of dictionaries.
        
        Args:
            file_path: Path to the CSV file
            delimiter: Optional delimiter override (defaults to config)
            encoding: Optional encoding override (defaults to config)
            
        Returns:
            List of dictionaries representing CSV rows
            
        Raises:
            FileAccessError: If file cannot be accessed or read
            CSVParsingError: If CSV parsing fails
        """
        with logfire.span("csv_parser.read_csv_file", file_path=file_path, encoding=encoding):
            delimiter = delimiter or self.delimiter
            encoding = encoding or self.encoding
            
            # Validate file path
            path = Path(file_path)
        
        # Check if file exists
        if not path.exists():
            error_msg = f"CSV file not found: {file_path}"
            logger.error(error_msg)
            raise FileAccessError(error_msg, file_path=file_path)
        
        # Check if path is a file
        if not path.is_file():
            error_msg = f"Path is not a file: {file_path}"
            logger.error(error_msg)
            raise FileAccessError(error_msg, file_path=file_path)
        
        # Try to read the file
        try:
            with open(path, 'r', encoding=encoding, newline='') as csvfile:
                # Use csv.DictReader for automatic header parsing
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                
                # Read all rows
                rows = []
                for row in reader:
                    rows.append(dict(row))
                
                logger.info(f"Successfully read {len(rows)} rows from {file_path}")
                logfire.info("CSV file read successfully", rows_count=len(rows), file_path=file_path)
                return rows
                
        except PermissionError as e:
            error_msg = f"Permission denied reading file: {file_path}"
            logger.error(f"{error_msg} - {str(e)}")
            logfire.error("CSV file permission denied", file_path=file_path, error=str(e))
            raise FileAccessError(error_msg, file_path=file_path, original_error=str(e))
            
        except UnicodeDecodeError as e:
            # Try alternative encodings
            alternative_encodings = ['latin-1', 'iso-8859-1', 'cp1252']
            
            for alt_encoding in alternative_encodings:
                if alt_encoding == encoding:
                    continue
                    
                try:
                    logger.warning(
                        f"Failed to read {file_path} with {encoding}, "
                        f"trying {alt_encoding}"
                    )
                    with open(path, 'r', encoding=alt_encoding, newline='') as csvfile:
                        reader = csv.DictReader(csvfile, delimiter=delimiter)
                        rows = [dict(row) for row in reader]
                        logger.info(
                            f"Successfully read {len(rows)} rows from {file_path} "
                            f"using {alt_encoding} encoding"
                        )
                        return rows
                except (UnicodeDecodeError, Exception):
                    continue
            
            # If all encodings fail, raise error
            error_msg = f"Failed to decode file with encoding {encoding}: {file_path}"
            logger.error(f"{error_msg} - {str(e)}")
            raise CSVParsingError(
                error_msg,
                file_path=file_path,
                row_number=None,
                original_error=str(e)
            )
            
        except csv.Error as e:
            error_msg = f"CSV parsing error in file: {file_path}"
            logger.error(f"{error_msg} - {str(e)}")
            raise CSVParsingError(
                error_msg,
                file_path=file_path,
                row_number=None,
                original_error=str(e)
            )
            
        except Exception as e:
            error_msg = f"Unexpected error reading file: {file_path}"
            logger.error(f"{error_msg} - {str(e)}")
            raise FileAccessError(error_msg, file_path=file_path, original_error=str(e))
    
    def parse_csv_to_documents(
        self,
        file_path: str,
        delimiter: Optional[str] = None,
        encoding: Optional[str] = None
    ) -> List[CSVDocument]:
        """
        Parse CSV file into structured CSVDocument objects.
        
        Args:
            file_path: Path to the CSV file
            delimiter: Optional delimiter override
            encoding: Optional encoding override
            
        Returns:
            List of CSVDocument objects
            
        Raises:
            FileAccessError: If file cannot be accessed
            CSVParsingError: If CSV parsing fails
        """
        with logfire.span("csv_parser.parse_csv_to_documents", file_path=file_path):
            # Read CSV rows
            rows = self.read_csv_file(file_path, delimiter, encoding)
        
        # Parse rows into CSVDocument objects
        documents = []
        ingestion_time = datetime.utcnow()
        
        for idx, row in enumerate(rows, start=1):
            try:
                # Apply column mapping if configured
                if self.column_mapping:
                    mapped_row = {}
                    for csv_col, mapped_col in self.column_mapping.items():
                        if csv_col in row:
                            mapped_row[mapped_col] = row[csv_col]
                    # Include unmapped columns as well
                    for col, val in row.items():
                        if col not in self.column_mapping:
                            mapped_row[col] = val
                    row = mapped_row
                
                # Generate unique document ID
                doc_id = self._generate_document_id(file_path, idx, row)
                
                # Create CSVDocument
                document = CSVDocument(
                    document_id=doc_id,
                    source_file=file_path,
                    row_number=idx,
                    content=row,
                    ingestion_time=ingestion_time
                )
                
                documents.append(document)
                
            except Exception as e:
                error_msg = f"Failed to parse row {idx} in {file_path}"
                logger.warning(f"{error_msg}: {str(e)}")
                # Continue processing other rows
                continue
        
            logger.info(
                f"Successfully parsed {len(documents)} documents from {file_path} "
                f"({len(rows) - len(documents)} rows skipped due to errors)"
            )
            logfire.info(
                "CSV documents parsed",
                documents_count=len(documents),
                rows_skipped=len(rows) - len(documents),
                file_path=file_path
            )
            
            return documents
    
    def _generate_document_id(
        self,
        file_path: str,
        row_number: int,
        content: Dict[str, Any]
    ) -> str:
        """
        Generate a unique document ID based on file path, row number, and content.
        
        Args:
            file_path: Path to the CSV file
            row_number: Row number in the CSV file
            content: Row content as dictionary
            
        Returns:
            Unique document ID string
        """
        # Create a deterministic ID based on file path and row number
        # This allows re-ingestion to update the same documents
        id_string = f"{file_path}:row:{row_number}"
        
        # Use SHA256 hash for consistent, unique IDs
        doc_id = hashlib.sha256(id_string.encode()).hexdigest()[:16]
        
        return doc_id
    
    def get_csv_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Get metadata about a CSV file without reading all rows.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            Dictionary containing file metadata
            
        Raises:
            FileAccessError: If file cannot be accessed
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileAccessError(f"CSV file not found: {file_path}", file_path=file_path)
        
        try:
            stat = path.stat()
            
            # Read just the header
            with open(path, 'r', encoding=self.encoding, newline='') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=self.delimiter)
                headers = reader.fieldnames or []
            
            metadata = {
                'file_path': str(path.absolute()),
                'file_name': path.name,
                'file_size_bytes': stat.st_size,
                'modified_time': datetime.fromtimestamp(stat.st_mtime),
                'headers': headers,
                'num_columns': len(headers)
            }
            
            return metadata
            
        except Exception as e:
            error_msg = f"Failed to get metadata for {file_path}"
            logger.error(f"{error_msg}: {str(e)}")
            raise FileAccessError(error_msg, file_path=file_path, original_error=str(e))
