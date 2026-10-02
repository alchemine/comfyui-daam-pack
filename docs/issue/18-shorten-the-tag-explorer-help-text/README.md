# #18 Shorten the tag explorer help text

이슈: https://github.com/alchemine/comfyui-daam-pack/issues/18

## 이슈

Tag Explorer 상단의 안내 문구가 긴 산문 한 문단이라 읽기 어렵다.

## 해결책

컨트롤마다 한 줄씩 짧게 설명한다. 줄바꿈과 들여쓰기가 보이도록 안내 영역에
`whiteSpace: "pre-wrap"`을 준다. 상태 문구("Run the node to load tags." 등)는
그대로 둔다.

```
strength: overlay opacity
smooth: blur the map before colouring
view
  - heatmap: jet colours over the image
  - mask: the map dims the image
bar: how clearly the tag shaped the image
  - blue ≥ 0.5, yellow > 0, grey 0
  - hovering the image: the tag's share there
tag: point to see its map, click to pin
```

## 테스트 계획

변경이 브라우저 JS의 문구에만 있다. 브라우저에서 직접 확인한다.

| 확인 | 방법 | 기대 결과 |
|---|---|---|
| 문구 | 노드를 실행한다 | 위 문구가 줄바꿈과 들여쓰기를 지킨 채 보인다 |
| 상태 문구 | 실행 전 노드를 본다 | `Run the node to load tags.`가 보인다 |
