import os
from config.local_config import PDF_STORAGE_PATH

class LocalStorageManager:
    """Manages PDF storage locally - will be replaced by Azure Blob Storage"""
    
    def __init__(self):
        self.storage_path = PDF_STORAGE_PATH
        os.makedirs(self.storage_path, exist_ok=True)
    
    def upload_resume(self, file_obj, candidate_id: str) -> str:
        """
        Save resume locally, preserving original extension (.pdf, .docx).
        """
        ext = os.path.splitext(file_obj.filename)[1].lower() or ".pdf"
        filename = f"{candidate_id}{ext}"
        filepath = os.path.join(self.storage_path, filename)

        file_obj.seek(0)
        file_obj.save(filepath)

        return filepath
    
    def get_resume_path(self, candidate_id: str) -> str:
        """Get path to stored PDF"""
        return os.path.join(self.storage_path, f"{candidate_id}.pdf")
    
    def delete_resume(self, candidate_id: str):
        """Delete stored PDF"""
        filepath = self.get_resume_path(candidate_id)
        if os.path.exists(filepath):
            os.remove(filepath)
