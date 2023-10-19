# -*- coding:utf-8 -*-

import configparser
import re
import sys
import os
import openai
import deepl
from dotenv import load_dotenv
from WIP_csv_for_key import contains_japanese, extract_english_keys_from_csv

load_dotenv()  # .env ファイルから環境変数を読み込む
openai_api_key = os.getenv("OPENAI_API_KEY")
deepl_api_key = os.getenv("DEEPL_API_KEY")

# OpenAI APIキーを設定します
openai.api_key = openai_api_key
# DeepL API の設定
translator = deepl.Translator(deepl_api_key)

# OpenAI 翻訳の前後
LangFrom = "English"    # 翻訳前
LangTo   = "Japanese"   # 翻訳語

# DeepL 翻訳先
target_lang = "JA"

# 初期プロンプト
initial_prompt = f'You are a helpful assistant that translates {LangFrom} to {LangTo}. Retain proper nouns and specialized terms in their original English form. Keep placeholders in the format "<[number]>" (e.g., "<0>", "<1>", "<2>", ..., and so on) or "<>" or "%I" of "%Is" unchanged.'


# chat GPT 節約のためのバッチ処理を削除して、順次翻訳をする関数に変更
def translate_text_GPT(text,count):
    """
    単一の文章を受け取り、翻訳を実行し、翻訳結果を返す関数
    """

    dammy=True
    if dammy:
        return text + "_GPT"

    messages = [
        {"role": "system", "content": initial_prompt},
        {"role": "user", "content": f'{text}'}
    ]

    try:
        response = openai.ChatCompletion.create(
          model="gpt-3.5-turbo",
          messages=messages
        )
        translated_text = response['choices'][0]['message']['content']
    except openai.error.OpenAIError as e:
        print(f"Error with OpenAI API call: {str(e)}")
        print('エラー発生：', count + 1, "行目のGPT翻訳が上手くいっていません。")
        return ""
    
    return translated_text


# DeepL API を使って翻訳
def translate_text_Deepl(text,count):

    dammy=True
    if dammy:
        return text + "_Deepl"

    try:
        translated_text = translator.translate_text(text, target_lang=target_lang)
    except deepl.DeepLException as e:
        errorMessage = str(e)
        print(errorMessage)
        print('エラー発生：', count + 1, "行目のdeepl翻訳が上手くいっていません。")
    return translated_text



# プレースホルダーに対するパターンを判別
def extract_and_replace_patterns(value, patterns):
    placeholders = []
    placeholder_counter = 0
    use_gpt = False
    # 改行記号を <> に置き換えてあげる
    value = value.replace("\\n", "<>")

    def replacer(match):
        nonlocal placeholder_counter
        placeholder = f"<{placeholder_counter}>"
        placeholders.append((placeholder, match.group(0)))
        placeholder_counter += 1
        return placeholder

    for pattern in patterns:
        value = re.sub(pattern, replacer, value)

    if placeholder_counter > 0:
        use_gpt = True
    
    return value, placeholders, use_gpt


def restore_patterns(value, placeholders):
    for placeholder, original in placeholders:
        result = value.replace(placeholder, original)
    return result



# txt ファイルを読み込み
def read_txt_as_dict(txt_path):
    data_dict = {}
    with open(txt_path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                data_dict[key] = value
    return data_dict


# 中国語の global.ini.txt から触っちゃいけない key を判別する。
def extract_keys_without_chinese_characters(version):
    # テキストファイルを読み取る
    script_dir = os.path.dirname(os.path.abspath(__file__))
    txt_path = os.path.join(script_dir, '..', version, 'global_cn.ini.txt')

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
    
    keys_without_chinese = []
    for key, value in data_dict.items():
        if not re.search(r'[\u4e00-\u9fff]', value):
            keys_without_chinese.append(key)
    
    return keys_without_chinese



# main処理
def translate_ini_file(version):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    txt_path = os.path.join(script_dir, '..', version, 'global_en.ini.txt')
    
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

    # 特殊なkeyを翻訳しないようにする条件
    skip_keywords = extract_keys_without_chinese_characters(version)

    skip_valuewords = {'@','blah','---------------------'}

    # 翻訳してはいけないプレースホルダーを取得する正規表現を保存
    patterns = [
        # r'~mission\([\w|]+\)',
        # r'~RefineryMethod\(\w+\)',
        # r'~action\(\w+\)',
        # r'~shopInteractionData\(\w+\)',
        # r'~serviceBeacon\(\w+\)',
        # r'~ItemModifierMethod\(\w+\)',
        r'#~(\w+)\((\w+)\)',
        r'~(\w+)\((\w+)\)',
        r'ID#\s+\w+',
        r'[\w\s]+:\s[^\n]+',
        r'%\w+',
        r'WIP',
        r'.*;.*',          # ;で終わる行
        r'.*=.*',          # =での代入
        r'.*\{.*',         # 開始ブレース
        r'.*\}.*',         # 終了ブレース
        r'\bif\b',         # if文
        r'\bfor\b',        # forループ
        r'\bwhile\b',      # whileループ
        r'\bint\b',        # int型
        r'\bfloat\b',      # float型
        r'\bdouble\b'     # double型
    ]

    # WIP_ini.csv より、翻訳済みのデータをスルーして翻訳していない場所にだけアプローチする
    csv_path = os.path.join(script_dir, '..', version, 'WIP_ini.csv')
    # 翻訳していないkey, 未翻訳文リスト, 翻訳済みリスト
    english_keys, trans_values, jap = extract_english_keys_from_csv(csv_path)

    translation_count = 0  # 翻訳するべき行のカウンタを初期化
    gpt_count = 0
    deepl_count = 0

    for key, value in data_dict.items():

        use_gpt = False
        # keyに特定のキーワードが含まれている場合、翻訳をスキップ
        if any(keyword in key for keyword in skip_keywords):
            continue

        # 翻訳済みでない Key 以外は翻訳をスキップ
        if not any(transkeyword in key for transkeyword in english_keys):
            continue

        # valueが特定の文字列を含む場合、翻訳をスキップ
        if any(valueword in value for valueword in skip_valuewords):
            continue


        # パターンマッチングで翻訳するべきものを分ける
        value_with_placeholders, placeholders, use_gpt = extract_and_replace_patterns(value, patterns)

        # ここで順次的に翻訳を実行
        if use_gpt == True:
            translated_value = translate_text_GPT(value_with_placeholders,translation_count)
            # 改行記号のプレースホルダーの置き換え修正
            translated_value = translated_value.replace("<>", "\\n")
            translated_value = restore_patterns(translated_value, placeholders)
            gpt_count += 1
        else:
            translated_value = translate_text_Deepl(value_with_placeholders,translation_count)
            deepl_count += 1

        # プレースホルダー置換テスト
        # final_value = value_with_placeholders
        data_dict[key] = translated_value

        translation_count += 1

    # 翻訳後の内容を新しいファイルに保存
    try:
        translated_file_path = os.path.join(script_dir, '..', version, 'translated_global.ini.txt')
        with open(translated_file_path, 'w', encoding='utf-8-sig', newline='\n') as translated_file:
            for k, v in data_dict.items():
                translated_file.write(f"{k}={v}\n")
    except Exception as e:
        print(f"Error writing to translated_global.ini.txt: {str(e)}")

    print("処理の回数")
    print(translation_count)
    print("gptを使った回数")
    print(gpt_count)
    print("deeplを使った回数")
    print(deepl_count)


if __name__ == '__main__':
    # if len(sys.argv) < 2:
    #     print("Please provide the version as an argument.")
    # else:
    #     version = sys.argv[1]
    #     translate_ini_file(version)

    translate_ini_file('v3.20.0b')