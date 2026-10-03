# #25 Fit each tag explorer help line on one line

이슈: https://github.com/alchemine/comfyui-daam-pack/issues/25

## 이슈

Tag Explorer 도움말 8줄 중 5줄이 패널 폭(210px)을 넘어 두 줄로 꺾인다.
bar 설명("how much each tag influenced the image")은 영향의 크기를 말하지만,
#23 이후 막대는 태그의 attention이 한곳에 얼마나 모였는지를 나타낸다.

## 해결책

줄마다 33자 이하로 줄이고, bar 설명을 주목도로 바꾼다.

```
strength: overlay strength
smooth: overlay softness
view: heatmap or mask
  - heatmap: red more, blue less
  - mask: darker for less
bar: how focused its attention is
image: hover to see tags there
tag: hover to show, click to pin
```

## 테스트 계획

| 확인 | 방법 | 기대 결과 |
|---|---|---|
| 줄 수 | 패널과 같은 스타일(폭 210px, 안쪽 여백 6px, 11px, 줄 간격 1.3)로 도움말을 헤드리스 브라우저에 그린다 | 8줄로 그려지고, 꺾이는 줄이 없다 |
| 기존 동작 | `pytest`, `ruff` | 모두 통과한다 |

## 테스트 결과

| 확인 | 수정 전 | 수정 후 |
|---|---|---|
| 줄 수 | 13줄 (5줄이 꺾임, 사용자 화면) | 8줄 (도움말 영역 높이 114px = 8 × 14.3px) |
| `pytest` | 20 passed | 20 passed |
