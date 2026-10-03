# #27 Shorten the heatmap, mask and bar help to symbols and nouns

이슈: https://github.com/alchemine/comfyui-daam-pack/issues/27

## 이슈

Tag Explorer 도움말의 heatmap, mask, bar 줄은 설명이 문장이라 읽는 데 시간이
걸린다.

## 해결책

세 줄의 설명을 기호와 명사로 바꾸고, 나머지 줄은 그대로 둔다.

```
strength: overlay strength
smooth: overlay softness
view: heatmap or mask
  - heatmap: red ↑, blue ↓
  - mask: dark ↓
bar: attention focus
image: hover to see tags there
tag: hover to show, click to pin
```

## 테스트 계획

| 확인 | 방법 | 기대 결과 |
|---|---|---|
| 렌더 | 패널과 같은 스타일(폭 210px, 안쪽 여백 6px, 11px, 줄 간격 1.3)로 도움말을 헤드리스 브라우저에 그린다 | 8줄로 그려지고, 화살표가 글자로 보인다 |
| 기존 동작 | `pytest`, `ruff` | 모두 통과한다 |

## 테스트 결과

| 확인 | 결과 |
|---|---|
| 렌더 | 8줄 (도움말 영역 높이 114px), 화살표가 보인다 |
| `pytest` | 20 passed |
