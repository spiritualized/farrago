
def normalize_path_chars(path):
    tmp = path

    replacements = {
        ':': '：',
        '/': '∕',
        '?': '﹖',
        '<': '〈',
        '>': '〉',
        '"': '＂',
        '|': '｜',
        '*': '٭',
    }

    for x in replacements:
        tmp = tmp.replace(x, replacements[x])

    return tmp
