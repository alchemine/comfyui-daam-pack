# #20 Make the tag explorer help text easier to read

이슈: https://github.com/alchemine/comfyui-daam-pack/issues/20

## 이슈

#18에서 줄인 안내 문구에 전문 용어(`overlay opacity`, `jet colours`, `share`)가
남아 있어 비전문가가 읽기 어렵다.

## 해결책

모든 줄을 "영향(influence)"이라는 한 단어로 설명하고, `이름: 설명` 형식으로
맞춘다. `:` 앞의 이름은 굵게 표시한다.

```
strength: how strongly the influence shows
smooth: how soft the influence looks
view: heatmap or mask
  - heatmap: red for more influence, blue for less (overlay)
  - mask: darker for less influence
bar: how much each tag influenced the image (3 levels)
image: point at it to see which tags influenced that spot
tag: point to see its influence, click to keep it on
```

- `HELP_TEXT`를 `[들여쓰기, 이름, 설명]` 묶음의 배열로 둔다.
- 안내 영역을 채울 때 이름은 `<b>` 요소로, 나머지는 글자로 넣는다.
  `innerHTML`은 쓰지 않는다.
- 상태 문구(`Run the node to load tags.` 등)는 지금처럼 `textContent`로 넣는다.

막대 색의 기준값은 적지 않는다. 포인터가 이미지 밖에 있을 때는 고정값(0.5,
0)으로, 이미지 위에 있을 때는 태그 수에 따라 바뀌는 값(평균의 2배, 평균)으로
색을 정한다. 숫자를 적으면 한쪽에서는 틀린 설명이 된다.

## 테스트 계획

| 확인 | 방법 | 기대 결과 |
|---|---|---|
| 문구 | 노드를 실행한다 | 위 문구가 줄바꿈과 들여쓰기를 지킨 채 보이고, `:` 앞의 이름만 굵다 |
| 상태 문구 | 실행 전 노드를 본다 | `Run the node to load tags.`가 굵은 글씨 없이 보인다 |
| 문구 조립 | `quickjs`로 안내 영역에 들어가는 요소를 확인한다 | 줄마다 `<b>이름</b>`과 설명이 위 문구 순서대로 들어간다 |

## 테스트 결과

이 환경에는 브라우저가 없어서 브라우저 확인은 하지 못했다.
`quickjs`로 `showHelp()`를 실행해 안내 영역에 들어가는 요소를 확인했다.

```
<b>strength</b>: how strongly the influence shows
<b>smooth</b>: how soft the influence looks
<b>view</b>: heatmap or mask
  - <b>heatmap</b>: red for more influence, blue for less (overlay)
  - <b>mask</b>: darker for less influence
<b>bar</b>: how much each tag influenced the image (3 levels)
<b>image</b>: point at it to see which tags influenced that spot
<b>tag</b>: point to see its influence, click to keep it on
```

기존 `pytest` 15개는 수정 전후 모두 통과한다.
