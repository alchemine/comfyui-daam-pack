# #23 Score tag map shape by island entropy

이슈: https://github.com/alchemine/comfyui-daam-pack/issues/23

## 이슈

태그 맵의 모양 점수(`structure_scores`)는 sharpness와 separability를 값을
정렬해서만 계산한다. 패치의 위치를 보지 않으므로 아래 맵을 가르지 못한다.

- 높은 패치가 한곳에 모인 맵과, 여기저기 튄 노이즈 맵
- 바탕 전체가 빨간 맵
- 모서리에만 값이 몰린 맵(attention sink)

## 해결책

점수를 섬 단위 엔트로피 하나로 바꾼다.

1. 각 변의 1/10을 잘라 낸다(`EDGE_CUT`). 모서리에 몰린 값을 빼기 위해서다.
2. 맵을 0~1로 펴고, 0.5(`RED_LEVEL`) 미만 패치를 버린다.
3. 남은 패치를 8방향으로 이어 섬으로 묶고, 섬마다 값의 합을 구한다.
4. 섬들의 엔트로피를 `log(빨간 패치 수)`로 나눠 정규화하고, 1에서 뺀다.
   섬이 하나면 넓이와 상관없이 1이고, 빨간 패치가 모두 따로 떨어지면 0이다.
5. 맵의 중앙값이 0.5 이상이면 빨간 바탕으로 보고 이 값을 뒤집는다.
6. (1 − 맵의 평균)을 곱한다. 화면 전체가 밝은 맵은 낮게 나온다.

## 테스트 계획

테스트는 `tests/issue/23-score-tag-map-shape-by-island-entropy/`에 있다.
맵은 64×64 인공 맵이다.

| 테스트 | 무엇을 테스트하는가 | 기대 결과 |
|---|---|---|
| `test_one_island_scores_high_whatever_its_size` | 반지름 2와 10인 봉우리 하나 | 둘 다 0.7 초과 |
| `test_two_islands_still_count` | 떨어진 작은 봉우리 두 개(두 눈) | 0.7 초과 |
| `test_sprinkled_map_scores_low` | 작은 봉우리 12개를 흩뿌린 맵 | 0.5 미만 |
| `test_red_background_scores_low` | 가운데만 낮고 바깥이 높은 맵 | 0.1 미만 |
| `test_corner_pile_does_not_count` | 꼭짓점에 몰린 봉우리와 약한 노이즈 | 0.5 미만 |

0.5는 Explorer가 막대를 높음 색으로 칠하는 기준(`LANDED_CLEAR`)이다.

실행 방법:

```bash
.venv/bin/python -m pytest -c tests/pytest.ini tests
```

## 테스트 결과

| 테스트 | 수정 전 (`7df6118`) | 수정 후 |
|---|---|---|
| `test_one_island_scores_high_whatever_its_size` | 통과 | 통과 |
| `test_two_islands_still_count` | 통과 | 통과 |
| `test_sprinkled_map_scores_low` | 실패: 1.00 | 통과 |
| `test_red_background_scores_low` | 실패: 0.52 | 통과 |
| `test_corner_pile_does_not_count` | 실패: 0.99 | 통과 |
| 합계 | 3 failed, 2 passed | 5 passed |

수정 전 결과는 수정 전 코드를 따로 꺼내 같은 테스트를 돌려서 얻었다.

```bash
git archive 7df6118 | tar -x -C /tmp/daam-before
cp -r tests /tmp/daam-before/
cd /tmp/daam-before/tests
<팩 경로>/.venv/bin/python -m pytest -q issue
```
