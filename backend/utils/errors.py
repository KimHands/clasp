from fastapi import HTTPException


class ErrorCode:
    FOLDER_NOT_FOUND = "FOLDER_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    SAVE_FAILED = "SAVE_FAILED"
    NO_COVER_DATA = "NO_COVER_DATA"
    RULE_CONFLICT = "RULE_CONFLICT"
    INVALID_TYPE = "INVALID_TYPE"
    RULE_NOT_FOUND = "RULE_NOT_FOUND"
    SCAN_NOT_FOUND = "SCAN_NOT_FOUND"
    MOVE_FAILED = "MOVE_FAILED"
    LOG_NOT_FOUND = "LOG_NOT_FOUND"
    ALREADY_UNDONE = "ALREADY_UNDONE"


ERROR_HTTP_STATUS = {
    ErrorCode.FOLDER_NOT_FOUND: 404,
    ErrorCode.PERMISSION_DENIED: 403,
    ErrorCode.FILE_NOT_FOUND: 404,
    ErrorCode.SAVE_FAILED: 500,
    ErrorCode.NO_COVER_DATA: 404,
    ErrorCode.RULE_CONFLICT: 409,
    ErrorCode.INVALID_TYPE: 400,
    ErrorCode.RULE_NOT_FOUND: 404,
    ErrorCode.SCAN_NOT_FOUND: 404,
    ErrorCode.MOVE_FAILED: 500,
    ErrorCode.LOG_NOT_FOUND: 404,
    ErrorCode.ALREADY_UNDONE: 409,
}

ERROR_MESSAGES = {
    ErrorCode.FOLDER_NOT_FOUND: "폴더 경로가 존재하지 않음",
    ErrorCode.PERMISSION_DENIED: "파일 / 폴더 접근 권한 없음",
    ErrorCode.FILE_NOT_FOUND: "해당 파일 ID 없음",
    ErrorCode.SAVE_FAILED: "SQLite 저장 실패",
    ErrorCode.NO_COVER_DATA: "표지 데이터 없음",
    ErrorCode.RULE_CONFLICT: "중복 규칙 존재",
    ErrorCode.INVALID_TYPE: "지원하지 않는 규칙 type",
    ErrorCode.RULE_NOT_FOUND: "해당 규칙 ID 없음",
    ErrorCode.SCAN_NOT_FOUND: "해당 스캔 ID 없음",
    ErrorCode.MOVE_FAILED: "파일 이동 실패",
    ErrorCode.LOG_NOT_FOUND: "해당 로그 ID 없음",
    ErrorCode.ALREADY_UNDONE: "이미 되돌리기 완료된 작업",
}


def raise_error(code: str, message: str = None):
    """에러 코드에 맞는 HTTPException 발생"""
    status_code = ERROR_HTTP_STATUS.get(code, 500)
    detail = {
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message or ERROR_MESSAGES.get(code, "알 수 없는 오류"),
        },
    }
    raise HTTPException(status_code=status_code, detail=detail)
