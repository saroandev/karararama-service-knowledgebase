"""
API Client for backend communication
"""
import requests
from typing import Dict, List, Optional, Tuple, Any
from config.settings import API_BASE_URL


class APIClient:
    """Handles all API communications with the backend"""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url

    def query(self, question: str, use_reranker: bool = True, top_k: int = 5) -> Dict:
        """Send query to API"""
        try:
            payload = {
                "question": question,
                "top_k": top_k,
                "use_reranker": use_reranker
            }

            response = requests.post(
                f"{self.base_url}/query",
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"API Error: {response.status_code}"}

        except Exception as e:
            return {"error": str(e)}

    def upload_document(self, file) -> Tuple[bool, str, Dict]:
        """Upload a document to the API"""
        try:
            # Prepare request
            files = {"file": (file.name, file.getvalue(), file.type or "application/pdf")}

            # Send to API
            response = requests.post(
                f"{self.base_url}/ingest",
                files=files,
                timeout=300
            )

            if response.status_code == 200:
                result = response.json()

                # Handle different response types based on status
                if "chunks_created" in result:
                    # Successful new document
                    return True, file.name, result
                elif "chunks_count" in result:
                    # Document already exists
                    return True, file.name, {"message": "Doküman zaten mevcut", "existing": True}
                else:
                    return False, file.name, result.get('message', 'Bilinmeyen hata')
            else:
                return False, file.name, f"HTTP {response.status_code}: {response.text}"

        except Exception as e:
            return False, file.name, str(e)

    def fetch_documents(self) -> List[Dict]:
        """Fetch all documents from knowledge base"""
        try:
            response = requests.get(
                f"{self.base_url}/documents",
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                return []
        except Exception:
            return []

    def delete_document(self, document_id: str) -> Tuple[bool, Any]:
        """Delete a document from knowledge base"""
        try:
            response = requests.delete(
                f"{self.base_url}/documents/{document_id}",
                timeout=10
            )
            return response.status_code == 200, response.json() if response.status_code == 200 else response.text
        except Exception as e:
            return False, str(e)

    def check_health(self) -> bool:
        """Check API health status"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False


# Create a singleton instance
api_client = APIClient()