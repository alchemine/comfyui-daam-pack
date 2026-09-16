# ComfyUI-DAAM-Pack

[English](README.md) | [한국어](README_ko.md)

프롬프트의 어떤 태그가 이미지의 어느 부분을 만들었는지 크로스 어텐션 히트맵([DAAM](https://arxiv.org/abs/2210.04885))으로 봅니다. SDXL 전용.

[![DAAM Tag Explorer](assets/comfyui-daam-pack-example-poster.jpg)](https://github.com/alchemine/comfyui-daam-pack/blob/main/assets/comfyui-daam-pack-example-v1.0.0.mp4)

*[▶ 데모](https://github.com/alchemine/comfyui-daam-pack/blob/main/assets/comfyui-daam-pack-example-v1.0.0.mp4) (34초)*

## 설치

ComfyUI Manager에서 **ComfyUI-DAAM-Pack** 검색, 또는:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/alchemine/comfyui-daam-pack
```

## 예제

[`workflows/comfyui-daam-pack-workflow.json`](workflows/comfyui-daam-pack-workflow.json)

![Workflow](workflows/comfyui-daam-pack-workflow.png)

## 노드 (`DaamPack/DAAM`)

### Sampler Custom (DAAM)

`SamplerCustom`에 히트맵 출력 2개가 추가된 노드. 연결하지 않으면 `SamplerCustom`과 비용이 같습니다.

| 입력 | 설명 |
|------|------|
| `SamplerCustom`과 동일 | `model`, `add_noise`, `noise_seed`, `cfg`, `positive`, `negative`, `sampler`, `sigmas`, `latent_image` |

| 출력 | 설명 |
|------|------|
| `output`, `denoised_output` | `SamplerCustom`과 동일 |
| `pos_heatmaps` / `neg_heatmaps` | 토큰별 어텐션 맵. 익스플로러에 연결 |

### DAAM Tag Explorer

| 입력 | 설명 |
|------|------|
| `clip` | 프롬프트를 인코딩한 CLIP |
| `text` | 프롬프트 문자열(BREAK 포함). 컨디셔닝을 만든 것과 **완전히 같은 문자열**이어야 합니다. 같은 노드에서 분기하세요. 다르면 태그가 어긋납니다 |
| `heatmaps` | Sampler Custom (DAAM)의 `pos_heatmaps` |
| `images` | 디코딩된 이미지 |

| 조작 | 설명 |
|------|------|
| 이미지 호버 | 그 지점에서 각 태그가 차지하는 어텐션 비율을 바로 표시. 태그 N개 기준 파랑은 2/N 초과, 노랑은 1/N 초과 |
| 이미지 클릭 | 그 지점을 지배하는 태그 선택. Ctrl/Shift 클릭은 선택에 추가 |
| 태그에 포인터 | 포인터가 머무는 동안 해당 맵을 표시 |
| 태그 클릭 | 고정. 여러 개를 고정하면 각자의 스케일 그대로 함께 표시 |
| 방향키 | 목록 이동. `Enter` / `Space` 고정, `Escape` 해제 |
| `strength` | 맵을 얼마나 강하게 적용할지. 0이면 렌더 그대로 |
| `smooth` | 맵을 흐리는 정도. 0이면 어텐션 셀이 그대로 보임 |
| `view: heatmap` | 이미지 위에 jet 컬러. 컬러바 0~1 |
| `view: mask` | 맵을 이미지의 가시성으로 사용. 태그가 본 곳은 남고 나머지는 어두워짐 |

포인터가 이미지 밖에 있을 때의 바는 **그 태그가 그림에 형태를 만들었는지**를 0~1로 나타냅니다. 뾰족한 봉우리든 경계가 깔끔한 영역이든 형태로 칩니다. 다른 태그와의 상대 순위가 아니라 고정된 기준이라, 아무것도 높지 않은 프롬프트는 실제로 아무 형태도 만들지 않은 것입니다. 행은 이 점수로 정렬됩니다.

## 라이선스

GPL-3.0 — [LICENSE](LICENSE) 참조.
