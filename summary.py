import os
import sys

import anthropic

# Day9：APIキーが登録されていなければ、最初に知らせて終了する
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("APIキーが見つかりません。環境変数 ANTHROPIC_API_KEY を登録してから、PowerShellを開き直して実行してください。")
    raise SystemExit

# APIキーは環境変数 ANTHROPIC_API_KEY から自動で読み込まれる（コードには書かない）
client = anthropic.Anthropic()


def read_text_file(path):
    # Day12：テキストファイルを読み込む（UTF-8 → 古いメモ帳などのShift_JIS の順に試す）
    if not os.path.isfile(path):
        print(f"ファイルが見つかりません：{path}")
        raise SystemExit
    for encoding in ("utf-8-sig", "cp932"):
        try:
            with open(path, encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    print("ファイルの文字コードが読み取れませんでした。UTF-8で保存し直してから試してください。")
    raise SystemExit


def read_pasted_text():
    # Day6：貼り付けた文章を受け取る（空行があっても続けて受け取れるよう「おわり」の行で終了）
    end_word = "おわり"
    print(f"要約したい文章を貼り付けてください。最後に「{end_word}」とだけ書いた行を入力してEnter。")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:  # Ctrl+Z → Enter でも終了できる
            break
        if line.strip() == end_word:
            break
        lines.append(line)
    return "\n".join(lines)


# 「python summary.py 記事.txt」のようにファイル名があればファイルを、なければ貼り付けを要約する
if len(sys.argv) >= 2:
    long_text = read_text_file(sys.argv[1]).strip()
    if not long_text:
        print("ファイルの中身が空でした。")
        raise SystemExit
else:
    long_text = read_pasted_text().strip()
    if not long_text:
        print("文章が入力されませんでした。もう一度実行してください。")
        raise SystemExit

# Day8：出力を3〜5行に収める
MIN_LINES = 3
MAX_LINES = 5

prompt = f"""次の文章を、日本語で{MIN_LINES}〜{MAX_LINES}行に要約してください。
- 1行は1つの要点にする
- 各行は「- 」で始める
- 文章に書かれていないことは付け足さない
- 要約の行以外（前置き・あいさつ・まとめの一言）は書かない

文章：
{long_text}"""


def ask_claude(messages):
    # Day9：よくある失敗は、英語のエラー文の代わりに日本語で原因を表示して終了する
    try:
        # fallbacks="default"：万一リクエストが断られたとき、別のモデルで自動的にやり直す設定
        message = client.beta.messages.create(
            model="claude-opus-5-5",
            max_tokens=16000,
            output_config={"effort": "low"},  # 要約は簡単な作業なので「low」で速く・安く
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=messages,
        )
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        print("APIキーが使えませんでした。期限切れや入力ミスがないか確認してください。")
        raise SystemExit
    except anthropic.APIConnectionError:  # タイムアウトもここに含まれる
        print("通信できませんでした。ネット接続を確認してください。")
        raise SystemExit
    except anthropic.RateLimitError:
        print("利用上限にかかりました。少し待ってから再実行してください。")
        raise SystemExit
    except anthropic.InternalServerError:  # 混雑（529）やサーバー側の不調
        print("Claude側が混雑しているか、不調のようです。少し待ってから再実行してください。")
        raise SystemExit
    except anthropic.APIError as e:
        print(f"エラーが発生しました：{e}")
        raise SystemExit

    if message.stop_reason == "refusal":
        print("リクエストが断られました:", message.stop_details)
        raise SystemExit
    return "".join(block.text for block in message.content if block.type == "text")


def pick_summary_lines(text):
    # 「- 」で始まる行だけを要約として拾う（前置きなどが混ざっても除外できる）
    return [line.strip() for line in text.splitlines() if line.strip().startswith("- ")]


messages = [{"role": "user", "content": prompt}]
answer = ask_claude(messages)
summary_lines = pick_summary_lines(answer)

# 行数が範囲外なら、1回だけ直してもらう
if not (MIN_LINES <= len(summary_lines) <= MAX_LINES):
    messages += [
        {"role": "assistant", "content": answer},
        {"role": "user", "content": f"今の要約は{len(summary_lines)}行でした。「- 」で始まる{MIN_LINES}〜{MAX_LINES}行に直して、要約の行だけを出力してください。"},
    ]
    answer = ask_claude(messages)
    summary_lines = pick_summary_lines(answer)

if summary_lines:
    print("\n".join(summary_lines))
    if not (MIN_LINES <= len(summary_lines) <= MAX_LINES):
        print(f"（注意：{MIN_LINES}〜{MAX_LINES}行に収まりませんでした。{len(summary_lines)}行です）")
else:
    # 形式が崩れた場合は、返ってきた文章をそのまま表示する
    print(answer)
