# -*- coding:utf-8 -*-

import configparser
import re
import sys
import os
import openai
from dotenv import load_dotenv

load_dotenv()  # .env ファイルから環境変数を読み込む
openai_api_key = os.getenv("OPENAI_API_KEY")

# OpenAI APIキーを設定します
openai.api_key = openai_api_key

# 翻訳の前後
LangFrom = "English"    # 翻訳前
LangTo   = "Japanese"   # 翻訳語

# 初期プロンプト
initial_prompt = f'You are a helpful assistant that translates {LangFrom} to {LangTo}. Whenever you translate, treat up to the tag [END] as a single sentence. Keep the tag [END] unchanged at the end of each translated text. Also, keep specialized terms and names in their original {LangFrom} form.'

# バッチ処理に使うトークンカウンター
def count_tokens(text):
    # ここでは、単純に空白、句読点、記号の数をカウントしています。
    # もちろん、より詳細なトークンのカウント方法を適用することもできます。
    return len(re.findall(r'\w+|\S', text))


# chat GPT 節約のためのバッチ処理
def batch_translate(texts):
    """
    文章のリストを受け取り、翻訳を実行し、翻訳結果を返す関数
    """
    result_text = ""

    # 各テキストをユーザーメッセージとして追加
    for text in texts:
        result_text += text + " [END] "
    # 初期メッセージを設定
    messages = [{"role": "system", "content": initial_prompt},
                {"role": "user", "content": f'{result_text} [END]'}]

    # API呼び出し
    try:
        response = openai.ChatCompletion.create(
          model="gpt-3.5-turbo",
          messages=messages
        )
    except openai.error.OpenAIError as e:
        print(f"Error with OpenAI API call: {str(e)}")
        return []
    
    # レスポンスの確認
    print(response)

    # 翻訳箇所挙動テスト用
    # translated_texts = [text + "_JP" for text in texts]

    # アシスタントの返信から日本語の部分を正規表現で抽出
    assistant_reply = response['choices'][0]['message']['content']
    translated_texts = [text.replace(" [END]", "") for text in assistant_reply.split(" [END] ") if text]

    return translated_texts


# プレースホルダーに対するパターンを判別
def extract_and_replace_patterns(value, patterns):
    placeholders = []
    placeholder_counter = 0
    for pattern in patterns:
        matches = re.findall(pattern, value)
        for match in matches:
            placeholder = f"PLACEHOLDER_{placeholder_counter}"
            value = value.replace(match, placeholder, 1)  # 1回だけ置換
            placeholders.append((placeholder, match))
            placeholder_counter += 1
    return value, placeholders

def restore_patterns(value, placeholders):
    for placeholder, original in placeholders:
        value = value.replace(placeholder, original)
    return value


# iniファイルが読み取れる形じゃないのでtxtに直して使う
def read_txt_as_dict(txt_path):
    data_dict = {}
    with open(txt_path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                data_dict[key] = value
    return data_dict


# main処理
def translate_ini_file(version):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    txt_path = os.path.join(script_dir, '..', version, 'global_en.txt')
    
    # ファイルが存在するかチェック
    if not os.path.exists(txt_path):
        print(f"File {txt_path} does not exist!")
        return

    # ファイルを読み込む
    try:
        data_dict = read_txt_as_dict(txt_path)
    except Exception as e:
        print(f"Error reading {txt_path}: {str(e)}")
        return

    # 特殊な変数を翻訳しないようにする条件
    skip_keywords = {'Name', '(WIP)', 'Test', 'UEERanks', 'UGF', 'Usable_', 'UI_', 'WIP'}
    skip_valuewords = {"@", r'\<.*?\>', r'\[.*?\]', r'\(.*?\)'}

    # 翻訳してはいけないプレースホルダーを取得する正規表現を保存
    patterns = [
        r'[\w\s]+:\s[^\n]+',
        r'~mission\(\w+\)',
        r'ID#\s+\w+',
        r'~RefineryMethod\(\w+\)',
        r'~action\(\w+\)',
        r'~shopInteractionData\(\w+\)',
        r'~serviceBeacon\(\w+\)',
        r'%\w+',

        # C++ で書かれたソース部分
        r'.*;.*',          # ;で終わる行
        r'.*=.*',          # =での代入
        r'.*\{.*',         # 開始ブレース
        r'.*\}.*',         # 終了ブレース
        r'\bif\b',         # if文
        r'\bfor\b',        # forループ
        r'\bwhile\b',      # whileループ
        r'\bint\b',        # int型
        r'\bfloat\b',      # float型
        r'\bdouble\b',     # double型
    ]

    # 追加：キーのリストを用意
    keys_to_translate = []
    translation_count = 0  # 翻訳するべき行のカウンタを初期化
    to_translate = []
    placeholders_list = []

    for key, value in data_dict.items():

        # keyに特定のキーワードが含まれている場合、翻訳をスキップ
        if any(keyword in key for keyword in skip_keywords):
            continue

        # valueが特定の文字列を含む場合、翻訳をスキップ
        if any(valueword in value for valueword in skip_valuewords):
            continue

        # パターンマッチングで翻訳するべきものを分ける
        value_with_placeholders, placeholders = extract_and_replace_patterns(value, patterns)

        # トークン数を確認
        current_tokens = count_tokens(" ".join(to_translate))
        next_tokens = count_tokens(value_with_placeholders)

        # 制限を超える場合、現在のバッチを処理
        if current_tokens + next_tokens > 600:
            translated_values = batch_translate(to_translate)

            # 翻訳結果をファイルにセット
            for translated_key, translated, original_placeholders in zip(keys_to_translate, translated_values, placeholders_list):
                final_value = restore_patterns(translated, original_placeholders)
                data_dict[translated_key] = final_value

            # リストをクリア
            to_translate.clear()
            placeholders_list.clear()
            keys_to_translate.clear()  # キーリストもクリア
            translation_count += 1

        # キーもリストに追加
        keys_to_translate.append(key)
        # ここでvalue_with_placeholdersをリストに追加
        to_translate.append(value_with_placeholders)
        placeholders_list.append(placeholders)

    # 最後のバッチを処理（もし残っていれば）
    if to_translate:
        translated_values = batch_translate(to_translate)
        for translated_key, translated, original_placeholders in zip(keys_to_translate, translated_values, placeholders_list):
            final_value = restore_patterns(translated, original_placeholders)
            data_dict[translated_key] = final_value

        translation_count += 1

    # 翻訳後の内容を新しいファイルに保存
    try:
        translated_file_path = os.path.join(script_dir, '..', version, 'translated_global.txt')
        with open(translated_file_path, 'w', encoding='utf-8-sig', newline='\n') as translated_file:
            for k, v in data_dict.items():
                translated_file.write(f"{k}={v}\n")
    except Exception as e:
        print(f"Error writing to translated_global.txt: {str(e)}")

    print("バッチ処理の回数")
    print(translation_count)



if __name__ == '__main__':
    # if len(sys.argv) < 2:
    #     print("Please provide the version as an argument.")
    # else:
    #     version = sys.argv[1]
    #     translate_ini_file(version)

    translate_ini_file('v3.20.0b')