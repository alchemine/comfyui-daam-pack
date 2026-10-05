# #39 Embed the tag maps and scores in the saved grid PNG

이슈: https://github.com/alchemine/comfyui-daam-pack/issues/39

## 이슈

Tag Explorer의 `save` 버튼은 격자 그림만 내려받는다. 맵 자체를 다시 보려면 서버의
결과 주소(`/daam/tag_explorer/maps?node_id=...`)를 노드 id를 찾아 브라우저로 직접
열어야 하고, 그 결과도 노드마다 마지막 실행 하나만 남는다. 버튼 이름 `save`도
무엇을 저장하는지 드러내지 않는다.

## 해결책

- 버튼 이름을 `save grid`로 바꾼다. 도움말은 `save grid: png file with metadata`다.
- 내려받는 PNG(`daam-tags.png`)의 격자 그림은 그대로 두고, `IEND` 앞에 압축하지
  않은 iTXt 청크를 하나 넣는다. 키워드는 `daam`, 내용은 아래 JSON이다.

| 키 | 내용 |
|---|---|
| `tags` | 모든 태그(목록에 보이는 태그만이 아님) |
| `scores` | 태그마다 bar 점수 |
| `shown` | 격자에 들어간 태그의 번호, 격자 순서대로 |
| `shape` | 맵의 크기 `[태그 수, 행, 열]` |
| `maps` | 노드가 보낸 맵 그대로, float32 little endian을 base64로 |
| `image` | 원본 렌더, PNG를 base64로 |

브라우저 캔버스는 PNG에 메타데이터를 쓰지 못하므로, `toBlob`으로 만든 PNG 바이트에
청크를 직접 끼워 넣고 CRC-32를 계산한다. 의존성은 늘지 않는다.

Python에서는 Pillow로 읽을 수 있다. 청크가 이미지 데이터 뒤에 있으므로 `load()`를
먼저 불러야 `info`에 들어온다.

```python
import base64, json, numpy as np
from PIL import Image

image = Image.open("daam-tags.png")
image.load()
data = json.loads(image.info["daam"])
maps = np.frombuffer(base64.b64decode(data["maps"]), "<f4").reshape(data["shape"])
```

## 테스트 계획

변경이 브라우저 JS에만 있다. 이 리포의 테스트는 `pytest`뿐이므로 브라우저에서
확인한다.

| 확인 | 방법 | 기대 결과 |
|---|---|---|
| 버튼 | 패널을 본다 | `save grid` 버튼과 도움말 줄이 있다 |
| 격자 | 내려받은 PNG를 연다 | #35와 같은 격자 그림이다 |
| 맵 | Pillow로 `daam` 청크를 읽어 맵을 꺼낸다 | 노드가 보낸 맵과 값이 같다 |
| 태그, 점수, 순서 | 같은 청크의 `tags`, `scores`, `shown`을 본다 | 모든 태그와 점수가 있고, `shown`이 격자 순서다 |
| 렌더 | `image`를 PNG로 연다 | 원본 렌더와 픽셀이 같다 |

## 테스트 결과

이 환경에는 ComfyUI 화면을 띄울 브라우저 세션이 없어서, `chrome-headless-shell`로
Tag Explorer만 떼어 실행했다. 맵은 풍경 렌더(태그 18개, 56×72)의 실제 맵이고,
`e`로 검색해 13개만 보이게 한 뒤 `save grid`를 눌렀다. 이 headless 브라우저에서는
`canvas.toBlob`의 콜백이 돌아오지 않아, 테스트 페이지에서만 `toBlob`을 `toDataURL`로
대신했다. 그 뒤의 청크 삽입과 내려받기 코드는 그대로 실행된다.

| 확인 | 결과 |
|---|---|
| 버튼 | `save grid` 버튼과 `save grid: png file with metadata` 도움말이 보인다 |
| 격자 | 2048×1688 PNG(7.9MB)가 만들어진다 |
| 맵 | Pillow가 `daam` 청크를 읽고, 꺼낸 맵이 원래 맵과 값까지 같다 |
| 태그, 점수, 순서 | 태그 18개가 같고, `shown`은 격자의 13개 순서다 |
| 렌더 | 1152×896이고 원본과 픽셀이 같다 |

기존 `pytest` 19개는 수정 전후 모두 통과한다.
