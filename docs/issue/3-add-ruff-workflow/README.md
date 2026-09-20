# #3 Add ruff workflow

## 이슈
- GitHub Actions에 ruff 검사가 없다.
- `pyproject.toml`에 의존성 선언이 남아 있다.

## 해결책
- `.github/workflows/ruff.yml`을 추가한다. `ruff check .`와 `ruff format --check .`를 실행한다.
- `pyproject.toml`에 `[tool.ruff]` 설정을 추가한다.
- `pyproject.toml`에서 `dependencies`를 지운다. 의존성은 `requirements.txt`에만 적는다.
- `nodes/daam.py`의 `print`를 `logging.warning`으로 바꾼다.
- 버전을 1.0.2로 올린다.

## 테스트 계획
| 테스트 | 기대 결과 |
|---|---|
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | 다시 형식을 맞출 파일이 없다 |

## 테스트 결과
### 수정 전
```
nodes/daam.py:357:13: T201 `print` found
Found 1 error.
No fixes available (1 hidden fix can be enabled with the `--unsafe-fixes` option).
6 files already formatted
```

### 수정 후
```
All checks passed!
6 files already formatted
```
