# #1 Serve Tag Explorer results from memory

이슈: https://github.com/alchemine/comfyui-daam-pack/issues/1

## 이슈

`DAAMTagExplorer`는 실행할 때마다 배치의 모든 이미지에 대해 PNG와 태그 맵
`.npy`를 ComfyUI의 `temp/`에 쓴다.

- 패널은 배치의 첫 이미지만 그리므로 나머지 파일은 읽히지 않는다.
- 파일은 서버를 재시작할 때까지 계속 쌓인다.

## 해결책

explorer 노드별로 최신 결과 하나만 메모리에 두고, 팩의 라우트로 제공한다.

- `explore()`는 히트맵이 있는 첫 이미지의 PNG와 태그 맵을 바이트로 만들어
  `EXPLORER_RESULTS[unique_id]`에 넣는다. 같은 노드를 다시 실행하면 값이
  교체된다.
- `GET /daam/tag_explorer/{kind}?node_id=...`가 `kind`에 따라 PNG(`image`)
  또는 `.npy`(`maps`)를 돌려준다. 결과가 없는 노드는 404다.
- UI 메시지는 파일 항목(`tag_images`, `tag_maps`) 대신 `tag_key`를 보내고,
  프론트엔드는 이 키로 라우트를 호출한다.

## 테스트 계획

테스트는 `tests/issue/1-serve-tag-explorer-results-from-memory/`에 있다.
노드는 ComfyUI가 호출하는 방식(선언된 hidden 입력만 전달)으로 호출한다.

| 테스트 | 무엇을 테스트하는가 | 기대 결과 |
|---|---|---|
| `test_writes_nothing_to_temp` | `explore()` 실행 후의 `temp/` | 비어 있다 |
| `test_ui_message_carries_the_node_key` | `explore()`가 돌려주는 UI 메시지 | `tag_key`가 노드 id이고 파일 항목이 없다 |
| `test_route_serves_image_and_maps` | 라우트의 `image`, `maps` 응답 | PNG는 입력 이미지 크기이고, 맵은 `(태그 수, map_h, map_w)`다 |
| `test_route_404_for_unknown_node` | 실행한 적 없는 노드 id로 요청 | 404 |
| `test_rerun_replaces_the_result` | 같은 노드를 다른 이미지로 다시 실행 | 결과가 하나만 남고 새 이미지로 바뀐다 |

실행 방법:

```bash
uv run --group test pytest -c tests/pytest.ini tests
```

## 테스트 결과

| 테스트 | 수정 전 (`52e4fb6`) | 수정 후 |
|---|---|---|
| `test_writes_nothing_to_temp` | 실패: `temp/`에 파일 2개 (PNG 1, `.npy` 1) | 통과 |
| `test_ui_message_carries_the_node_key` | 실패: UI 메시지에 `tag_key`가 없다 | 통과 |
| `test_route_serves_image_and_maps` | 실패: 라우트가 없다 | 통과 |
| `test_route_404_for_unknown_node` | 실패: 라우트가 없다 | 통과 |
| `test_rerun_replaces_the_result` | 실패: `EXPLORER_RESULTS`가 없다 | 통과 |
| 합계 | 5 failed | 5 passed |

수정 전 결과는 수정 전 코드를 따로 꺼내 같은 테스트를 돌려서 얻었다.

```bash
git archive 52e4fb6 | tar -x -C /tmp/daam-before
cp -r tests pyproject.toml /tmp/daam-before/
cd /tmp/daam-before
uv run --group test pytest -c tests/pytest.ini tests
```
