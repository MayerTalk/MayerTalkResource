static_url = "https://static.mayertalk.top/"
data_url = "char/%s.json"
special_data_url = "char/%s.spec.json"
version_url = "version/char/%s.txt"

lang_order = ["zh_CN", "zh_TW", "py", "fpy", "en_US", "ja_JP", "code"]

AIOHTTP_CLIENT_SETTINGS = {
    "max_line_size": 8190 * 2,
    "max_field_size": 8190 * 2,
}
