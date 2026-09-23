"""
Configuration and constants for PokéTan Osaka Stock Tracker
"""

# Firebase & API Configuration
FIREBASE_API_KEY = "AIzaSyAKTze8Ob3HBfflowqvDPbbCYp2hIPC8ug"
PROJECT_ID = "pokeca-map-7dabb"
FIRESTORE_BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

# Static Data URLs
POKETAN_BASE_URL = "https://poketan.jp"
STORES_URL_TEMPLATE = f"{POKETAN_BASE_URL}/data/stores/{{pref}}.json"

# Status code mappings
STATUS_CODE_MAP = {
    'i': {
        'key': 'in-stock',
        'label': 'Có hàng (In Stock)',
        'symbol': '🟢',
        'color': 'green'
    },
    'o': {
        'key': 'out-of-stock',
        'label': 'Hết hàng (Out of Stock)',
        'symbol': '🔴',
        'color': 'red'
    },
    'n': {
        'key': 'not-handled',
        'label': 'Không bán thẻ (Not Handled)',
        'symbol': '⚪',
        'color': 'gray'
    },
    'u': {
        'key': 'unknown',
        'label': 'Chưa rõ (Unknown)',
        'symbol': '❔',
        'color': 'yellow'
    }
}

# Chain names mapping
CHAIN_NAMES = {
    'seven': '7-Eleven (セブン-イレブン)',
    'lawson': 'Lawson (ローソン)',
    'familymart': 'FamilyMart (ファミリーマート)',
    'ministop': 'Ministop (ミニストップ)',
    'specialty': 'Shop thẻ bài chuyên biệt (Card Shop)',
    'joshin': 'Joshin Denki (上新電機)',
    'edion': 'EDION (エディオン)',
    'aeon': 'AEON Mall / Supermarket (イオン)',
    'geo': 'GEO (ゲオ)',
    'yamada': 'Yamada Denki (ヤマダデンキ)',
    'ks': "K's Denki (ケーズデンキ)",
    'toysrus': 'Toys "R" Us (トイザらス)',
    'biccamera': 'Bic Camera (ビックカメラ)',
    'yodobashi': 'Yodobashi Camera (ヨドバシカメラ)',
    'other': 'Cửa hàng khác (Other)'
}

# Pack codes mapping (các bộ pack mở bán)
PACK_CODES = {
    '3': '30th Anniversary',
    'e': 'Stellar Emerald (ストエメ)',
    'y': 'Abyss Eye (アビスアイ)',
    'j': 'Ninja (ニンジャ)',
    'm': 'Munikisu (ムニキス)',
    'd': 'Dream (ドリーム)',
    'x': 'Inferno (インフェルノ)',
    'b': 'Brave (ブレイブ)',
    's': 'Sinfonia (シンフォニア)'
}
