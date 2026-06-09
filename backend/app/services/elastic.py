import logging
from datetime import date, datetime
from typing import List, Dict, Any
import math
import numpy as np
import pandas as pd
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from app.core.config import settings

logger = logging.getLogger("elastic")


def _elastic_safe_value(value: Any) -> Any:
    """Converts pandas/numpy scalars into JSON-safe values accepted by Elasticsearch."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return _elastic_safe_value(value.item())
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value

class ElasticsearchService:
    @staticmethod
    def api_key() -> str:
        """Returns the configured Elastic API key, including the legacy field name."""
        return settings.elastic_cluster or settings.elastic_key

    @staticmethod
    def is_configured() -> bool:
        """Returns True if live Elastic integration parameters are present."""
        return bool(settings.elastic_url and ElasticsearchService.api_key())

    @staticmethod
    def get_client() -> Elasticsearch:
        """Instantiates and returns the official Elasticsearch client."""
        if not ElasticsearchService.is_configured():
            raise ValueError("Elasticsearch is not configured in environment settings.")
        return Elasticsearch(
            settings.elastic_url,
            api_key=ElasticsearchService.api_key(),
            request_timeout=120
        )

    @staticmethod
    def init_pipeline_and_index(session_id: str):
        """Creates the ELSER pipeline and the session-scoped index if they do not exist."""
        if not ElasticsearchService.is_configured():
            logger.info("Elastic Cloud not configured; skipping pipeline & index initialization.")
            return

        es = ElasticsearchService.get_client()

        # 1. Initialize the ELSER pipeline
        pipeline_name = "marketmind-pipeline"
        try:
            es.ingest.get_pipeline(id=pipeline_name)
        except Exception:
            pipeline_body = {
                "processors": [
                    {
                        "inference": {
                            "model_id": ".elser-2-elasticsearch",
                            "input_output": [
                                {
                                    "input_field": "content",
                                    "output_field": "embedding"
                                }
                            ]
                        }
                    }
                ]
            }
            es.ingest.put_pipeline(id=pipeline_name, body=pipeline_body)
            logger.info(f"Created ELSER pipeline: {pipeline_name}")

        # 2. Initialize the session index with mapping
        index_name = f"marketmind-{session_id}"
        if not es.indices.exists(index=index_name):
            mapping = {
                "mappings": {
                    "properties": {
                        "session_id": {"type": "keyword"},
                        "doc_type": {"type": "keyword"},  # "structured" | "unstructured"
                        "source_file": {"type": "keyword"},
                        "row_number": {"type": "integer"},
                        "page_number": {"type": "integer"},
                        "chunk_index": {"type": "integer"},
                        "content": {"type": "text"},
                        "embedding": {
                            "type": "sparse_vector"
                        }
                    },
                    "dynamic": True  # CSV column fields are added dynamically
                }
            }
            es.indices.create(index=index_name, body=mapping)
            logger.info(f"Created session index: {index_name}")

    @staticmethod
    def index_structured_data(session_id: str, filename: str, df: pd.DataFrame) -> bool:
        """Indexes CSV/Excel rows using the bulk API."""
        if not ElasticsearchService.is_configured():
            logger.info("Elastic Cloud not configured; running in Mock Local Mode.")
            return False

        try:
            ElasticsearchService.init_pipeline_and_index(session_id)
            es = ElasticsearchService.get_client()
            index_name = f"marketmind-{session_id}"

            actions = []
            for idx, row in df.iterrows():
                row_dict = row.to_dict()
                row_dict = {str(k): _elastic_safe_value(v) for k, v in row_dict.items()}

                # Form text description for ELSER inference
                content_parts = [f"{k}: {v}" for k, v in row_dict.items() if v is not None]
                content_str = ", ".join(content_parts)

                action = {
                    "_index": index_name,
                    "_id": f"{filename}-row-{idx}",
                    "pipeline": "marketmind-pipeline",
                    "session_id": session_id,
                    "doc_type": "structured",
                    "source_file": filename,
                    "row_number": idx + 1,
                    "content": content_str,
                    **row_dict
                }
                actions.append(action)

            if actions:
                bulk(es, actions, refresh=True)
                logger.info(f"Successfully indexed {len(actions)} structured rows to {index_name}")
            return True
        except Exception as exc:
            logger.warning("Structured Elastic indexing failed for %s: %s", filename, exc)
            return False

    @staticmethod
    def index_unstructured_data(session_id: str, filename: str, pages_text: List[str]) -> bool:
        """Chunks PDF text into ~512 words segments with 50 words overlap and indexes them."""
        if not ElasticsearchService.is_configured():
            logger.info("Elastic Cloud not configured; running in Mock Local Mode.")
            return False

        try:
            ElasticsearchService.init_pipeline_and_index(session_id)
            es = ElasticsearchService.get_client()
            index_name = f"marketmind-{session_id}"

            actions = []
            chunk_idx = 0

            for page_idx, page_text in enumerate(pages_text, start=1):
                if not page_text or not page_text.strip():
                    continue

                words = page_text.split()
                i = 0
                while i < len(words):
                    chunk_words = words[i:i + 512]
                    chunk_content = " ".join(chunk_words)

                    action = {
                        "_index": index_name,
                        "_id": f"{filename}-chunk-{chunk_idx}",
                        "pipeline": "marketmind-pipeline",
                        "session_id": session_id,
                        "doc_type": "unstructured",
                        "source_file": filename,
                        "page_number": page_idx,
                        "chunk_index": chunk_idx,
                        "content": chunk_content
                    }
                    actions.append(action)
                    chunk_idx += 1
                    i += 512 - 50  # 50 words overlap
                    if i >= len(words) and len(words) - (i - 462) < 50:
                        break

            if actions:
                bulk(es, actions, refresh=True)
                logger.info(f"Successfully indexed {len(actions)} unstructured chunks to {index_name}")
            return True
        except Exception as exc:
            logger.warning("Unstructured Elastic indexing failed for %s: %s", filename, exc)
            return False

    @staticmethod
    def delete_file_documents(session_id: str, filename: str) -> bool:
        """Deletes all indexed documents for a specific source file in the session index."""
        if not ElasticsearchService.is_configured():
            logger.info("Elastic Cloud not configured; skipping file document deletion.")
            return False

        try:
            es = ElasticsearchService.get_client()
            index_name = f"marketmind-{session_id}"
            if not es.indices.exists(index=index_name):
                return False

            es.delete_by_query(
                index=index_name,
                body={"query": {"term": {"source_file": filename}}},
                refresh=True,
                conflicts="proceed",
            )
            logger.info(f"Deleted indexed documents for {filename} from {index_name}")
            return True
        except Exception as exc:
            logger.warning("Elastic file document deletion failed for %s: %s", filename, exc)
            return False

    @staticmethod
    def delete_session_index(session_id: str) -> bool:
        """Drops the session-scoped index from Elasticsearch."""
        if not ElasticsearchService.is_configured():
            logger.info("Elastic Cloud not configured; skipping index deletion.")
            return False

        try:
            es = ElasticsearchService.get_client()
            index_name = f"marketmind-{session_id}"
            if es.indices.exists(index=index_name):
                es.indices.delete(index=index_name)
                logger.info(f"Deleted session index: {index_name}")
                return True
        except Exception as exc:
            logger.warning("Elastic session index deletion failed for %s: %s", session_id, exc)
        return False
