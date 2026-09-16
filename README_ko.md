# ComfyUI-DAAM-Pack

[English](README.md) | [한국어](README_ko.md)

https://github.com/user-attachments/assets/9903ff79-d4fa-459b-bf72-b7c09f0b21f6

![DAAM Tag Explorer](assets/comfyui-daam-pack-example-poster.png)

프롬프트의 어떤 태그가 이미지의 어느 부분을 만들었는지 크로스 어텐션 히트맵([DAAM](https://arxiv.org/abs/2210.04885))으로 봅니다.

> [!IMPORTANT]
> **SDXL 전용입니다.** 히트맵은 UNet의 크로스 어텐션 블록에서 읽어냅니다. Flux, SD3, Qwen-Image, Wan 같은 DiT 모델에는 그 블록이 없습니다.

## 사용법

모든 조작은 **DAAM Tag Explorer** 노드 안에서 이뤄집니다. 왼쪽은 이미지, 오른쪽은 태그 목록입니다.

| 조작 | 결과 |
|------|------|
| **이미지 호버** | 그 픽셀에서 각 태그가 차지하는 어텐션 비율이 바로 표시됩니다. 태그 N개 기준 파랑은 2/N, 노랑은 1/N 초과 |
| **이미지 클릭** | 그 픽셀을 지배하는 태그가 선택됩니다. Ctrl/Shift 클릭은 교체가 아니라 선택에 추가 |
| **태그 호버** | 포인터가 머무는 동안 그 태그의 맵을 보여줍니다 |
| **태그 클릭** | 고정됩니다. 여러 개를 고정하면 각자의 스케일 그대로 함께 표시됩니다 |
| **방향키** | 목록을 이동합니다. `Enter` / `Space` 고정, `Escape` 해제 |

포인터가 이미지 밖에 있을 때 바는 **그 태그가 그림에 형태를 만들었는지**를 0~1로 나타냅니다. 뾰족한 봉우리든 경계가 깔끔한 영역이든 형태로 칩니다. 다른 태그와의 상대 순위가 아니라 고정된 기준이라, 아무것도 높지 않은 프롬프트는 실제로 아무 형태도 만들지 않은 것입니다. 행은 이 점수로 정렬됩니다.

| 컨트롤 | 하는 일 |
|--------|---------|
| `strength` | 맵을 얼마나 강하게 적용할지. 0이면 렌더 그대로 |
| `smooth` | 맵을 흐리는 정도. 0이면 어텐션 셀이 그대로 보입니다 |
| `view: heatmap` | 이미지 위에 jet 컬러. 컬러바 0~1 |
| `view: mask` | 맵을 이미지의 가시성으로 사용합니다. 태그가 본 곳은 남고 나머지는 어두워집니다 |

## 예제

[`workflows/comfyui-daam-pack-workflow.json`](workflows/comfyui-daam-pack-workflow.json)

![Workflow](workflows/comfyui-daam-pack-workflow.png)

## 설치

ComfyUI Manager에서 **ComfyUI-DAAM-Pack** 검색, 또는:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/alchemine/comfyui-daam-pack
```

## 노드 (`DaamPack/DAAM`)

**Sampler Custom (DAAM)** — `SamplerCustom`에 토큰별 어텐션 맵인 `pos_heatmaps` / `neg_heatmaps` 출력이 추가된 노드. 연결하지 않으면 `SamplerCustom`과 비용이 같습니다.

**DAAM Tag Explorer** — 위의 뷰어.

| 입력 | 설명 |
|------|------|
| `clip` | 프롬프트를 인코딩한 CLIP |
| `text` | 프롬프트 문자열(BREAK 포함). 컨디셔닝을 만든 것과 **완전히 같은 문자열**이어야 합니다. 같은 노드에서 분기하세요. 다르면 태그가 어긋납니다 |
| `heatmaps` | Sampler Custom (DAAM)의 `pos_heatmaps` |
| `images` | 디코딩된 이미지 |

## 라이선스

GPL-3.0 — [LICENSE](LICENSE) 참조.
