# #34 Score tag map shape by how narrow the high region is and how much sits on the border

이슈: https://github.com/alchemine/comfyui-daam-pack/issues/34

## 이슈

포인터가 이미지 밖에 있을 때 bar 점수(`structure_scores`)는 맵의 모양을 4단계로
갈라야 한다.

| 단계 | 맵의 모양 | 예 |
|---|---|---|
| 1 가장 높음 | 좁은 곳만 높고 나머지는 평탄하게 낮다 | `fingernails`, `saliva`, `rolling eyes` |
| 2 약간 높음 | 넓은 곳만 높고 나머지는 평탄하게 낮다 | `posing`, `floating hair` |
| 3 약간 낮음 | 이미지 전체에 두루 퍼져 있다 | `dutch angle`, `light particles` |
| 4 가장 낮음 | 높은 값이 가장자리에 몰려 있다 | `cover image`, `novel illustration` |

지금 점수(섬 엔트로피)는 가장자리에 몰린 맵을 가르지 못한다. 가장자리 10%를
잘라 낸 뒤 안쪽을 다시 0~1로 늘리므로, 안쪽의 약한 봉우리 하나가 섬 하나가 되어
높게 나온다.

Table 1. 태그 62개짜리 렌더에서 지금 점수.

| 태그 | 단계 | 지금 점수 |
|---|---|---|
| `licking` | 1 | 0.81 |
| `fingernails` | 1 | 0.63 |
| `posing` | 2 | 0.66 |
| `light particles` | 3 | 0.70 |
| `cover image` | 4 | 0.53 |
| `novel illustration` | 4 | 0.59 |

이 렌더의 태그 37개에 단계를 붙이고 다른 단계의 태그 쌍 481개를 비교하면, 위
단계 태그의 점수가 더 높은 쌍은 84%다. 4단계의 평균(0.56)이 3단계(0.37)와
2단계(0.50)보다 높다.

## 해결책

맵을 0~1로 늘린 뒤 두 값을 곱한다.

1. 가장자리 띠(짧은 변의 8%, `BORDER`) 안쪽에서 맵의 중앙값을 구해 1에서
   뺀다. 좁은 곳만 높으면 중앙값이 0에 가까워 1에 가깝다. 높은 영역이 넓을수록,
   맵 전체가 중간값으로 퍼질수록 중앙값이 올라가 낮아진다.
2. 맵을 4제곱(`HIGH_POWER`)해서 높은 값만 남기고, 그 합 중 가장자리 띠에 있는
   비율을 1에서 뺀다. 높은 값이 가장자리에 몰리면 0에 가깝다.

색 기준은 0.75 이상이 파랑, 0.5 이상이 노랑이다(`LANDED_CLEAR`, `LANDED_AT_ALL`).
1단계가 파랑, 2단계가 노랑, 3·4단계가 회색에 오도록 정했다.

함께 바꾸는 것:

- 섬 엔트로피 계산(`_island_sums`, `_gathered`, `EDGE_CUT`, `RED_LEVEL`)을 지운다.
- README의 bar 점수 설명을 4단계 기준으로 고친다.
- #23의 테스트를 지운다. "흩뿌린 작은 봉우리는 낮다"는 새 기준에 없다.

가장자리에 실제로 있는 물체도 4단계처럼 낮아진다. 같은 렌더에서 `sofa`는 0.15,
`living room`은 0.32다. 맵 모양만으로는 가장자리에 몰린 attention sink와 가장자리의
물체를 가를 수 없다.

## 테스트 계획

테스트는 `tests/issue/34-score-tag-map-shape-by-how-narrow-the-high-region-is-and-how-much-sits-on-the-border/`에 있다.
맵은 64×64 인공 맵이다.

| 테스트 | 무엇을 테스트하는가 | 기대 결과 |
|---|---|---|
| `test_narrow_region_scores_blue` | 반지름 3인 봉우리 하나 | 0.75 이상 |
| `test_wide_region_scores_yellow` | 반지름 14인 봉우리 하나 | 0.5 이상 0.75 미만 |
| `test_map_spread_all_over_scores_grey` | 반지름 3인 봉우리 200개를 흩뿌린 맵 | 0.5 미만 |
| `test_border_pile_scores_lowest` | 테두리를 따라 높은 맵, 꼭짓점에 몰린 맵 | 둘 다 0.1 미만 |

실행 방법:

```bash
.venv/bin/python -m pytest -c tests/pytest.ini tests
```

## 테스트 결과

| 테스트 | 수정 전 (`be228e3`) | 수정 후 |
|---|---|---|
| `test_narrow_region_scores_blue` | 통과 | 통과 |
| `test_wide_region_scores_yellow` | 통과 | 통과 |
| `test_map_spread_all_over_scores_grey` | 실패: 0.52 | 통과 |
| `test_border_pile_scores_lowest` | 실패: 0.45 | 통과 |
| 합계 | 2 failed, 2 passed | 4 passed |

수정 전 결과는 수정 전 코드를 따로 꺼내 같은 테스트를 돌려서 얻었다.

```bash
git archive be228e3 | tar -x -C /tmp/daam-before
cp -r tests /tmp/daam-before/
cd /tmp/daam-before
<팩 경로>/.venv/bin/python -m pytest -q -c tests/pytest.ini tests/issue/34-*
```

전체 `pytest`는 수정 후 19개가 통과한다. #23의 테스트 5개는 지웠다.

Table 1의 렌더에서 수정 후 결과는 아래와 같다. 태그 쌍 481개 중 95%에서 위 단계
태그의 점수가 더 높고, 단계별 평균은 0.91, 0.61, 0.40, 0.07이다. 전체 62개 중
파랑 27개, 노랑 18개, 회색 17개다.

| 태그 | 단계 | 수정 전 | 수정 후 |
|---|---|---|---|
| `licking` | 1 | 0.81 | 0.99 |
| `fingernails` | 1 | 0.63 | 0.84 |
| `posing` | 2 | 0.66 | 0.59 |
| `light particles` | 3 | 0.70 | 0.51 |
| `cover image` | 4 | 0.53 | 0.07 |
| `novel illustration` | 4 | 0.59 | 0.02 |
