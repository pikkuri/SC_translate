# -*- coding:utf-8 -*-

import csv
import os
import unicodedata

def contains_japanese(text):
    for char in text:
        name = unicodedata.name(char)
        if "CJK UNIFIED" in name or "HIRAGANA" in name or "KATAKANA" in name:
            return True
    return False

def extract_english_keys_from_csv(filename):
    english_keys = []
    trans_values = []
    jap = []

    with open(filename, mode='r', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # ヘッダー行をスキップ

        for row in reader:
            key = row[2]
            translation = row[3]

            if not contains_japanese(translation):
                english_keys.append(key)
                trans_values.append(translation)
            else:
                jap.append(translation)

    return english_keys, trans_values, jap

# 試験
if __name__ == '__main__':
    version="v3.20.0b"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, '..', version, 'WIP_ini.csv')

    english_keys, trans_values, jap = extract_english_keys_from_csv(csv_path)
    print("END")