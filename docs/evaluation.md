# 분류 평가

`backend/eval/`는 합성 파일 38개로 분류 결과를 잰다. 모든 이름과 내용은 허구다. 표본이 작고 직접 만든 데이터이므로 실제 파일에 대한 정확도가 아니라 **회귀 감시용 수치**다.

```bash
cd backend
venv/bin/python -m eval.run --split tune
venv/bin/python -m eval.run --split holdout
venv/bin/python -m eval.run --llm-url http://127.0.0.1:1234/v1 --llm-model <모델>
```

- `tune`(24개)은 임계값과 키워드를 고칠 때 본다.
- `holdout`(14개)은 정답을 보기 전에 나눴고, 조정에 쓰지 않는다.
- `confident_wrong`은 신뢰도 0.7 이상인데 틀린 수다. 정확도보다 먼저 본다. 사용자가 믿고 넘어가는 오답이기 때문이다.

## 기록

2026-11-04, 임베딩 `paraphrase-multilingual-MiniLM-L12-v2`, 로컬 LLM `qwen/qwen2.5-coder-7b`(LM Studio).

| 세트 | 조건 | 수정 전 정확도 | 수정 전 고신뢰 오답 | 수정 후 정확도 | 수정 후 고신뢰 오답 |
|---|---|---|---|---|---|
| tune | LLM 없음 | 19/24 | 5 | 22/24 | 0 |
| tune | LLM 사용 | 20/24 | 4 | 23/24 | 1 |
| holdout | LLM 없음 | 11/14 | 3 | 12/14 | 0 |
| holdout | LLM 사용 | 14/14 | 0 | 14/14 | 0 |

- 보류 세트는 수정 후 한 번만 평가했고, 그 결과로 다시 조정하지 않았다.
- 보류 세트의 LLM 사용 조건은 수정 전후가 같아, 이 표본에서는 LLM 쪽 개선을 말할 수 없다.
- LLM 응답은 모델과 실행에 따라 달라질 수 있다.
