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
    parent_id: Optional[int] = None


class PatchRuleRequest(BaseModel):
    priority: Optional[int] = None
    folder_name: Optional[str] = None
    parent_id: Optional[int] = -1  # -1 = 변경 안 함, None = 루트로 이동


def _rule_to_dict(rule: Rule) -> dict:
    return {
        "id": rule.id,
        "priority": rule.priority,
        "type": rule.type,
        "value": rule.value,
        "folder_name": rule.folder_name,
        "parent_id": rule.parent_id,
    }


def _build_tree(rules: list[Rule]) -> list[dict]:
    """플랫 규칙 목록을 트리 구조로 변환"""
    rule_map = {r.id: {**_rule_to_dict(r), "children": []} for r in rules}
    tree = []
    for r in rules:
        node = rule_map[r.id]
        if r.parent_id and r.parent_id in rule_map:
            rule_map[r.parent_id]["children"].append(node)
        else:
            tree.append(node)
    return tree


@router.get("")
async def list_rules(db: Session = Depends(get_db)):
    """UC-05: 규칙 목록 조회 (트리 구조 + 플랫 목록 동시 반환)"""
    rules = db.query(Rule).order_by(Rule.priority).all()
    return JSONResponse(content=ok({
        "rules": [_rule_to_dict(r) for r in rules],
        "tree": _build_tree(rules),
    }))


@router.post("")
async def create_rule(body: CreateRuleRequest, db: Session = Depends(get_db)):
    """UC-05: 규칙 추가"""
    if body.type not in VALID_TYPES:
        raise_error(ErrorCode.INVALID_TYPE, f"지원하지 않는 규칙 type: {body.type}")

    existing = (
        db.query(Rule)
        .filter(Rule.type == body.type, Rule.value == body.value)
        .first()
    )
    if existing:
        raise_error(ErrorCode.RULE_CONFLICT, "동일한 type + value 규칙이 이미 존재합니다")

    if body.parent_id is not None:
        parent = db.query(Rule).filter(Rule.id == body.parent_id).first()
        if not parent:
            raise_error(ErrorCode.RULE_NOT_FOUND, "부모 규칙이 존재하지 않습니다")

    rule = Rule(
        priority=body.priority,
        type=body.type,
        value=body.value,
        folder_name=body.folder_name,
        parent_id=body.parent_id,
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
    """UC-05: 규칙 수정 (우선순위, 폴더명, 부모 변경)"""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise_error(ErrorCode.RULE_NOT_FOUND)

    if body.priority is not None:
        rule.priority = body.priority
    if body.folder_name is not None:
        rule.folder_name = body.folder_name
    # parent_id: -1이면 변경 안 함, None이면 루트로, 숫자면 해당 부모로
    if body.parent_id != -1:
        if body.parent_id is not None:
            if body.parent_id == rule_id:
                raise_error(ErrorCode.INVALID_TYPE, "자기 자신을 부모로 설정할 수 없습니다")
            parent = db.query(Rule).filter(Rule.id == body.parent_id).first()
            if not parent:
                raise_error(ErrorCode.RULE_NOT_FOUND, "부모 규칙이 존재하지 않습니다")
            # 간접 순환 참조 검증 (A→B→C→A 방지)
            visited = {rule_id}
            ancestor = parent
            while ancestor and ancestor.parent_id:
                if ancestor.parent_id in visited:
                    raise_error(ErrorCode.INVALID_TYPE, "순환 참조가 발생합니다")
                visited.add(ancestor.parent_id)
                ancestor = db.query(Rule).filter(Rule.id == ancestor.parent_id).first()
        rule.parent_id = body.parent_id

    db.commit()
    db.refresh(rule)
    return JSONResponse(content=ok(_rule_to_dict(rule)))


@router.delete("/{rule_id}")
async def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """UC-05: 규칙 삭제 (자식 규칙은 루트로 승격)"""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise_error(ErrorCode.RULE_NOT_FOUND)

    # 자식 규칙들을 루트로 승격
    children = db.query(Rule).filter(Rule.parent_id == rule_id).all()
    for child in children:
        child.parent_id = rule.parent_id

    db.delete(rule)
    db.commit()
    return JSONResponse(content=ok({"deleted_id": rule_id}))
