# 분류 평가

`backend/eval/`는 합성 파일 38개로 분류 결과를 잰다. 모든 이름과 내용은 허구다. 표본이 작고 직접 만든 데이터이므로 실제 파일에 대한 정확도가 아니라 **회귀 감시용 수치**다.

```bash
cd backend
venv/bin/python -m eval.run --split tune
venv/bin/python -m eval.run --split holdout
venv/bin/python -m eval.run --llm-url http://127.0.0.1:1234/v1 --llm-model <모델>
```

- `tune`(24개)은 임계값과 키워드를 고칠 때 본다.
- `holdout`(14개)은 분류 로직을 고치기 전에 나눴고, 조정에 쓰지 않는다.
- `confident_wrong`은 신뢰도 0.7 이상인데 틀린 수다. 정확도보다 먼저 본다. 사용자가 믿고 넘어가는 오답이기 때문이다.

## 기록

2026-11-04, 임베딩 `paraphrase-multilingual-MiniLM-L12-v2`, 로컬 LLM `qwen/qwen2.5-coder-7b`(LM Studio). 원본은 `docs/eval-results/`에 있다. 수정 전은 커밋 `88edf18`의 코드에 같은 평가 도구를 얹어 실행했다.

| 세트 | 조건 | 수정 전 정확도 | 수정 전 고신뢰 오답 | 수정 후 정확도 | 수정 후 고신뢰 오답 |
|---|---|---|---|---|---|
| tune | LLM 없음 | 19/24 | 5 | 22/24 | 0 |
| tune | LLM 사용 | 20/24 | 4 | 23/24 | 1 |
| holdout | LLM 없음 | 11/14 | 3 | 12/14 | 0 |
| holdout | LLM 사용 | 14/14 | 0 | 14/14 | 0 |

- 보류 세트 결과로 임계값이나 키워드를 조정하지 않았다. 이후 리뷰에서 나온 버그(파일명 패턴 적용 범위)를 고친 뒤 원본을 남기려고 다시 실행했고 수치는 같았다. 데이터 분할과 실행 순서는 저장소 이력만으로 증명되지 않으므로, 이 절차는 작성자의 기록으로 읽어야 한다.
- 보류 세트의 LLM 사용 조건은 수정 전후가 같아, 이 표본에서는 LLM 쪽 개선을 말할 수 없다.
- LLM 응답은 모델과 실행에 따라 달라질 수 있다.

## 소켓 측정

```bash
venv/bin/python -m eval.audit_sockets --llm-url http://127.0.0.1:1234/v1 --llm-model <모델>
```

실제 백엔드와 캐시된 임베딩 모델로 합성 파일 38개를 스캔하며 백엔드의 `socket.connect`, `socket.getaddrinfo`를 파이썬 감사 훅으로 기록한다. uvloop의 연결은 감사 훅에 보이지 않아 asyncio 루프로 실행한다. 파이썬 밖의 네이티브 코드가 직접 여는 연결은 이 방법으로 보이지 않는다.

기록(`docs/eval-results/socket-audit.json`): 연결은 `127.0.0.1:1234` 19건뿐이다.
