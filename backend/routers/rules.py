from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from database import get_db
from models.schema import Rule
from utils.response import ok, fail
from utils.errors import ErrorCode, raise_error

router = APIRouter(prefix="/rules", tags=["rules"])

VALID_TYPES = {"date", "content", "extension"}


class CreateRuleRequest(BaseModel):
    priority: int
    type: str
    value: str
    folder_name: str


class PatchRuleRequest(BaseModel):
    priority: Optional[int] = None
    folder_name: Optional[str] = None


def _rule_to_dict(rule: Rule) -> dict:
    return {
        "id": rule.id,
        "priority": rule.priority,
        "type": rule.type,
        "value": rule.value,
        "folder_name": rule.folder_name,
    }


@router.get("")
async def list_rules(db: Session = Depends(get_db)):
    """UC-05: 규칙 목록 조회 (우선순위 오름차순)"""
    rules = db.query(Rule).order_by(Rule.priority).all()
    return JSONResponse(content=ok({"rules": [_rule_to_dict(r) for r in rules]}))


@router.post("")
async def create_rule(body: CreateRuleRequest, db: Session = Depends(get_db)):
    """UC-05: 규칙 추가"""
    if body.type not in VALID_TYPES:
        raise_error(ErrorCode.INVALID_TYPE, f"지원하지 않는 규칙 type: {body.type}")

    # 중복 규칙 검사 (동일 type + value)
    existing = (
        db.query(Rule)
        .filter(Rule.type == body.type, Rule.value == body.value)
        .first()
    )
    if existing:
        raise_error(ErrorCode.RULE_CONFLICT, "동일한 type + value 규칙이 이미 존재합니다")

    rule = Rule(
        priority=body.priority,
        type=body.type,
        value=body.value,
        folder_name=body.folder_name,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return JSONResponse(content=ok(_rule_to_dict(rule)))


@router.patch("/{rule_id}")
async def update_rule(
    rule_id: int,
    body: PatchRuleRequest,
    db: Session = Depends(get_db),
):
    """UC-05: 규칙 수정"""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise_error(ErrorCode.RULE_NOT_FOUND)

    if body.priority is not None:
        rule.priority = body.priority
    if body.folder_name is not None:
        rule.folder_name = body.folder_name

    db.commit()
    db.refresh(rule)
    return JSONResponse(content=ok(_rule_to_dict(rule)))


@router.delete("/{rule_id}")
async def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """UC-05: 규칙 삭제"""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise_error(ErrorCode.RULE_NOT_FOUND)

    db.delete(rule)
    db.commit()
    return JSONResponse(content=ok({"deleted_id": rule_id}))
