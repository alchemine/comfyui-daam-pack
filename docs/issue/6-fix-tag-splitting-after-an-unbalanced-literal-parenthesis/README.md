# #6 Fix tag splitting after an unbalanced literal parenthesis

이슈: https://github.com/alchemine/comfyui-daam-pack/issues/6

## 이슈

프롬프트에 짝이 맞지 않는 글자 괄호가 있으면, 그 뒤의 태그가 전부 한
덩어리로 묶인다. `>:\(`, `:\(`, `;\)` 같은 이모티콘 태그가 그렇다.

- `annoyed, >:\(, ciloranko, mikozin`은 `annoyed`와
  `>:(, ciloranko , mikozin` 두 개로 나뉜다.
- `BREAK` 뒤의 청크도 통째로 태그 하나가 된다.

원인은 `split_tags()`의 괄호 깊이 추적이다.

- 디코딩한 토큰 글자에서 `(`와 `)`를 세어 깊이를 구하고, 깊이가 0일 때만
  쉼표를 구분자로 본다. 가중치 그룹 `(a,b:-1)` 안의 쉼표를 태그에 남기려는
  의도였다.
- ComfyUI는 토큰화하기 전에 가중치 괄호를 떼어 내므로, 토큰에 남는 괄호는
  `\(`, `\)`로 쓴 글자 괄호뿐이다.
- 글자 괄호는 짝이 맞는다는 보장이 없다. 여는 괄호 하나가 깊이를 1로 올리면
  다시 0으로 돌아오지 않고, 깊이는 77토큰 청크 경계에서도 초기화되지 않는다.

## 해결책

`split_tags()`에서 괄호 깊이 추적을 삭제한다.

- 쉼표 토큰은 언제나 태그를 끊는다.
- `),`처럼 쉼표로 끝나는 토큰도 언제나 태그를 끊는다. BPE가 `\),`를 토큰
  하나(`),</w>`)로 만들기 때문에 이 판정은 그대로 둔다.
- 글자 괄호 안에 쉼표가 있는 태그(`\(a, b\)`)는 쉼표에서 나뉜다.

## 테스트 계획

테스트는 `tests/issue/6-fix-tag-splitting-after-an-unbalanced-literal-parenthesis/`에
있다. `split_tags()`에 실제 CLIP 토크나이저가 만드는 토큰 조각을 그대로
넘긴다.

| 테스트 | 무엇을 테스트하는가 | 기대 결과 |
|---|---|---|
| `test_open_paren_does_not_swallow_later_tags` | `annoyed, >:\(, ciloranko, mikozin` | 태그 4개로 나뉘고, 토큰 인덱스가 각 태그의 토큰만 가리킨다 |
| `test_open_paren_does_not_reach_the_next_chunk` | `>:\( BREAK smell, shade` | 뒤 청크가 `smell`, `shade`로 나뉜다 |
| `test_emoticons_with_parens_split_like_any_tag` | `>:\(, smile, ;\), shade` | 태그 4개로 나뉜다 |
| `test_comma_glued_to_a_close_paren_separates` | `pozyomka \(arknights\), annoyed` | `),` 토큰에서 끊겨 태그 2개가 된다 |

실행 방법:

```bash
.venv/bin/python -m pytest -c tests/pytest.ini tests
```

## 테스트 결과

| 테스트 | 수정 전 (`a90628f`) | 수정 후 |
|---|---|---|
| `test_open_paren_does_not_swallow_later_tags` | 실패: `>:(, ciloranko , mikozin`이 태그 하나다 | 통과 |
| `test_open_paren_does_not_reach_the_next_chunk` | 실패: `smell , shade`가 태그 하나다 | 통과 |
| `test_emoticons_with_parens_split_like_any_tag` | 실패: `>:(, smile , ;)`가 태그 하나다 | 통과 |
| `test_comma_glued_to_a_close_paren_separates` | 통과 | 통과 |
| 합계 (#1의 테스트 5개 포함) | 3 failed, 6 passed | 9 passed |
