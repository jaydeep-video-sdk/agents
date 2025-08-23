import os
import gspread
from typing import Optional, List, Any
from dataclasses import dataclass
from google.oauth2.service_account import Credentials


@dataclass
class SheetResponse:
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


class GoogleSheetClientError(Exception):
    pass


class GoogleSheetClient:
    def __init__(self, sheet_id: str, credentials_path: str):
        if not sheet_id or not credentials_path:
            raise GoogleSheetClientError("Sheet ID and credentials path are required.")

        creds = Credentials.from_service_account_file(
            credentials_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        self.gc = gspread.authorize(creds)

        try:
            self.sheet = self.gc.open_by_key(sheet_id).sheet1
        except gspread.SpreadsheetNotFound:
            raise GoogleSheetClientError(
                f"Google Sheet not found. Please share the sheet with your service account email:\n\n"
                f"{creds.service_account_email}"
            )

    # -------------------------
    # CRUD operations
    # -------------------------
    def create_row(self, values: List[Any]) -> SheetResponse:
        try:
            self.sheet.append_row(values)
            return SheetResponse(success=True, data=values)
        except Exception as e:
            return SheetResponse(success=False, error=str(e))

    def read_all(self) -> SheetResponse:
        try:
            records = self.sheet.get_all_values()
            return SheetResponse(success=True, data=records)
        except Exception as e:
            return SheetResponse(success=False, error=str(e))

    def update_row(self, row_index: int, values: List[Any]) -> SheetResponse:
        try:
            self.sheet.update(f"A{row_index}:Z{row_index}", [values])
            return SheetResponse(success=True, data=values)
        except Exception as e:
            return SheetResponse(success=False, error=str(e))

    def delete_row(self, row_index: int) -> SheetResponse:
        try:
            self.sheet.delete_rows(row_index)
            return SheetResponse(success=True, data={"deleted_row": row_index})
        except Exception as e:
            return SheetResponse(success=False, error=str(e))


# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":
    sheet_id = "1hEGoadbZ5XCFRWMJ8yS-VVlaNrLAG_yb2AUeMFcDQ3Y"  # <-- Replace with your Sheet ID
    creds_path = os.path.join(
        os.path.dirname(__file__),
        "arctic-dynamo-469411-g9-3b97d92e4cc2.json"
    )

    client = GoogleSheetClient(sheet_id, creds_path)

    # Create
    res = client.create_row(
        ["room_123", "Team Sync", "2025-08-24T10:00:00Z", 45, "jaydeep@example.com"]
    )
    print("Create:", res)

    # Read
    res = client.read_all()
    print("Read:", res.data)

    # Update row 2
    res = client.update_row(
        2, ["room_456", "Updated Meeting", "2025-08-25T12:00:00Z", 30, "jaydeep@example.com"]
    )
    print("Update:", res)

    # Delete row 3
    res = client.delete_row(3)
    print("Delete:", res)
