# 읽기 전용 MCP 서버

에이전트가 Clasp의 분류 결과를 조회하고 정리 계획을 검토할 수 있게 하는 stdio MCP 서버다. **파일을 옮기거나 바꾸는 도구는 없다.** 실제 정리는 사람이 앱에서 승인한다.

## 설치와 연결

```bash
cd backend
venv/bin/pip install -r requirements-mcp.txt
```

```json
{
  "mcpServers": {
    "clasp": {
      "command": "<레포 경로>/backend/venv/bin/python",
      "args": ["-m", "mcp_server"],
      "cwd": "<레포 경로>/backend"
    }
  }
}
```

앱에서 폴더를 한 번 스캔한 뒤에 쓴다. 배포 앱에는 포함되지 않는다.

## 도구

| 도구 | 돌려주는 것 |
|---|---|
| `get_classification_summary` | 전체·미분류 건수, 카테고리별·분류 단계별 건수 |
| `list_classified_files` | 파일 ID, 확장자, 카테고리, 분류 단계, 신뢰도, 수동 여부. 카테고리·미분류 필터, 최대 100건 |
| `preview_organize_plan` | 이동·제외 건수, 만들 폴더 수, 충돌 수, 폴더별 건수. 파일을 옮기지 않는다 |
| `get_organize_history` | 정리 이력과 되돌림 상태 |

## 설계

MCP 클라이언트는 클라우드 LLM일 수 있다. 그래서 이 서버의 응답도 앱의 전송 경계 안에 둔다.

- **기본 응답에 파일명, 태그, 본문, 절대 경로가 없다.** 본문을 돌려주는 도구는 어떤 설정에서도 없다.
- 파일명과 태그는 `CLASP_MCP_SHOW_FILENAMES=1`을 직접 설정해야 나온다. 이 경우 파일명이 클라이언트로 전달된다는 뜻이다. 민감 파일 키워드에 걸린 파일의 이름은 이 설정에서도 나오지 않는다.
- 파일명은 `untrusted_filename` 필드로 나간다. 누구나 정할 수 있는 값이므로 프롬프트 주입 경로가 된다. 제어 문자를 지우고 200자로 자르지만, 클라이언트도 데이터로 다뤄야 한다.
- 데이터베이스는 `mode=ro`와 `PRAGMA query_only`로 연다. 쓰기는 SQLite가 거부한다. 파일이 없으면 만들지 않고 오류를 돌려준다.
- `folder_path`는 홈 아래 경로만 받는다.
- 진행 중인 이동의 조정(`reconcile_pending`)은 쓰기 작업이라 호출하지 않는다.

## 범위 밖

- 정리 실행과 되돌리기. 사람의 승인 없이 파일을 옮기는 경로를 만들지 않는다.
- 네트워크 전송 방식(SSE, HTTP). stdio만 쓴다.
