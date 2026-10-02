# #12 Show tag labels as written in the prompt

이슈: https://github.com/alchemine/comfyui-daam-pack/issues/12

## 이슈

Tag Explorer의 태그 이름이 원문과 다르게 보인다.

| 원문 | 표시 |
|---|---|
| `astesia \(arknights\)` | `astesia ( arknights )` |
| `see-through` | `see - through` |
| `loose-fit` | `loose - fit` |

원인은 `split_tags()`가 태그 이름을 토큰에서 만드는 것이다.

- 토큰 id를 vocab으로 되돌린 뒤 `</w>`를 공백으로 바꿔 이어 붙인다.
- CLIP 토크나이저는 문장 부호를 별도의 단어로 떼어낸다. `see-through`는
  `see</w>`, `-</w>`, `through</w>`가 된다.
- 그래서 원문에 없던 공백이 생긴다. `\`와 대소문자도 토큰에 남지 않는다.

## 해결책

- `tokenize_break()`가 원문을 토큰 묶음에 함께 담는다. 임베딩 이름과 같은
  방식으로, 토크나이저 스트림이 쓰지 않는 키(`PROMPT_TEXT_KEY`)에 둔다.
- `split_tags()`는 디코딩한 글자를 원문 위치를 찾는 데에만 쓴다.
  - 공백을 뺀 글자 순서를, 공백과 `\`를 건너뛰고 대소문자를 무시하며
    원문에서 찾는다.
  - 찾은 원문 구간을 태그 이름으로 쓴다. 앞에 `\`가 있으면 함께 넣는다.
  - 다음 태그는 앞 태그가 끝난 위치부터 찾는다.
- 원문에서 찾지 못하면 지금처럼 디코딩한 글자를 쓴다.

가중치 괄호와 가중치 값은 토큰에 남지 않으므로 태그 이름에도 들어가지 않는다.
`(light particles,:-1.2)`는 `light particles`로 보인다.

## 테스트 계획

테스트는 `tests/issue/12-show-tag-labels-as-written-in-the-prompt/`에 있다.
`split_tags()`에 실제 CLIP 토크나이저가 만드는 토큰 조각과 원문을 함께
넘긴다.

| 테스트 | 무엇을 테스트하는가 | 기대 결과 |
|---|---|---|
| `test_labels_keep_the_prompt_text` | 이스케이프 괄호, `-`, 가중치 그룹, 대문자가 섞인 프롬프트 | 태그 이름이 원문 그대로다 |
| `test_a_leading_escape_stays_on_the_label` | `\(arknights\), red` | 첫 태그가 `\(arknights\)`다 |
| `test_labels_follow_the_prompt_across_break` | `see-through BREAK see-through, red` | 두 청크의 태그가 모두 원문 그대로다 |
| `test_a_label_missing_from_the_prompt_stays_decoded` | 원문에 없는 태그 | 디코딩한 글자 `see - through`를 쓴다 |

실행 방법:

```bash
uv venv
uv pip install -r tests/requirements.txt
.venv/bin/python -m pytest -c tests/pytest.ini tests
```

## 테스트 결과

| 테스트 | 수정 전 (`5b1e131`) | 수정 후 |
|---|---|---|
| `test_labels_keep_the_prompt_text` | 실패: `PROMPT_TEXT_KEY`가 없다 | 통과 |
| `test_a_leading_escape_stays_on_the_label` | 실패: `PROMPT_TEXT_KEY`가 없다 | 통과 |
| `test_labels_follow_the_prompt_across_break` | 실패: `PROMPT_TEXT_KEY`가 없다 | 통과 |
| `test_a_label_missing_from_the_prompt_stays_decoded` | 실패: `PROMPT_TEXT_KEY`가 없다 | 통과 |
| 합계 (기존 테스트 11개 포함) | 4 failed, 11 passed | 15 passed |

실제 SDXL 토크나이저로 `tokenize_break()`와 `split_tags()`를 함께 돌려서도
확인했다. `meteorite \(arknights\)`, `Torn see-through kneehighs`, `>:\(`,
`oil painting \(medium\)`이 원문 그대로 나온다.
