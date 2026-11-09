import ast
import html
import io
import json
import re
import textwrap
from urllib.request import Request, urlopen
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

# 데이터 주소
BASE = 'https://raw.githubusercontent.com/nasa-petal/'
JSON_URL = BASE + 'bio-strategy-extractor/main/asknature-data.json'
PAPER_URL = BASE + 'nasa_petal_snorkel/main/labeled_data.csv'
FUNCTION_URL = BASE + 'nasa_petal_snorkel/main/biomimicry_functions_enumerated.csv'

# 기능 코드: (한국어 이름, 문제 표현, 영어 검색 표현, 활용 방향)
RULES = {
    'attach_permanently': ('영구 접착', '접착|붙이|붙는|붙게|안 붙|떨어지', 'adhesi|adhere|glue|cement', '접착 구조나 물질을 참고한 접합 방식'),
    'attach_temporarily': ('일시적 부착', '탈부착|뗐다|떼었다|붙였다|흡착', 'temporary adhesion|reversible adhesion|suction|attach', '반복하여 붙이고 떼는 부착 방식'),
    'protect_from_excess_liquids': ('과도한 물로부터 보호', '방수|젖|빗물|비 오는|물 들어|물들어|물 침투', 'water.repell|waterproof|hydrophobic|prevent.*water|water.*prevent', '물 침투를 줄이는 표면이나 덮개'),
    'protect_from_loss_liquids': ('수분 손실 방지', '건조|마르|보습|수분 손실', 'water loss|desiccation|retain.*water|prevent.*dry', '수분이 빠져나가는 것을 줄이는 보관 구조'),
    'manage_impact': ('충격 관리', '충격|떨어뜨|떨어졌|완충|부딪|깨지', 'impact|shock|cushion|dissipat.*energy', '충격을 분산하는 포장재나 보호 장치'),
    'prevent_fracture_rupture': ('파손 방지', '파손|부러|깨지|균열', 'fracture|crack|rupture|toughness', '균열이나 파손을 줄이는 재료 구조'),
    'regulate_drag_turbulence': ('항력과 난류 조절', '마찰|저항|항력|난류|물살', 'drag|turbulence|friction', '유체의 저항을 줄이는 표면이나 형상'),
    'protect_from_temperature': ('온도로부터 보호', '더위|추위|뜨거|차갑|단열|보온', 'insulat|thermal|heat loss|overheat|cooling', '열 이동을 조절하는 외피나 단열 구조'),
    'modify_convert_thermal_energy': ('열에너지 변환·조절', '냉각|식히|열 조절|온도 조절', 'heat exchange|cooling|thermal|thermoregulat', '열을 방출하거나 교환하는 구조'),
    'protect_from_microbes': ('미생물로부터 보호', '세균|항균|살균|미생물|곰팡이', 'antimicrobial|antibacterial|bactericidal|microb', '미생물 부착이나 증식을 줄이는 표면'),
    'absorb_filter_solids': ('고체 입자 여과', '먼지|미세먼지|입자|필터|여과', 'filter|filtration|trap.*particle|capture.*particle', '입자를 걸러 내는 필터 구조'),
    'detox_purify': ('해독·정화', '정화|오염|독성|유해 물질', 'detox|purif|pollut|contaminant', '오염 물질을 제거하는 정화 방식'),
    'capture_liquids': ('물 모으기', '물 모으|물모으|집수|안개|물 부족', 'collect.*water|harvest.*water|fog|capture.*water', '안개나 물방울을 모으는 집수 장치'),
    'sense_sound_vibrations': ('소리·진동 감지', '진동 감지|소리 감지|소리감지|진동감지', 'sense.*vibrat|detect.*sound|hear|auditory', '소리나 진동을 감지하는 센서'),
    'send_sound_signals': ('소리 전달', '소리 전달|소리 키|증폭|잘 들리', 'amplif|resonan|vocal|sound production', '소리가 잘 전달되도록 하는 공명 구조'),
    'sense_touch_and_mechanical_forces': ('접촉·힘 감지', '압력|촉각|접촉 감지|바람 감지', 'mechanosens|sense.*air|sense.*force|sensitive.*hair', '작은 힘이나 공기 흐름을 감지하는 센서'),
    'camouflage_mimicry': ('위장·의태', '위장|숨기|눈에 띄|보이지', 'camouflage|mimicry|conceal', '주변 환경에 맞춰 눈에 덜 띄는 외관'),
    'change_structural_color': ('구조색', '구조색|변색|색 바꾸|색 변화', 'structural colo|iridescen|photonic', '표면 미세 구조로 색을 표현하는 소재'),
    'modify_convert_light_energy': ('빛에너지 변환', '태양광|광합성|빛 에너지', 'photosynth|solar|light energy', '빛을 모으거나 에너지로 전환하는 구조'),
    'store_energy': ('에너지 저장', '에너지 저장|전기 저장|배터리', 'store.*energy|energy stor', '에너지를 저장하는 구조나 방식'),
}

# CSV의 function_enumerated 번호 0~99에 대응하는 한국어 이름입니다.
FUNCTION_KO = """영구적으로 붙이기
일시적으로 붙이기
고체를 수동적으로 이동시키기
액체를 수동적으로 이동시키기
기체를 수동적으로 이동시키기
알갱이 물질을 수동적으로 이동시키기
고체를 능동적으로 이동시키기
액체를 능동적으로 이동시키기
기체를 능동적으로 이동시키기
알갱이 물질을 능동적으로 이동시키기
동물로부터 보호하기
식물로부터 보호하기
균류로부터 보호하기
미생물로부터 보호하기
고체 물체로부터 보호하기
과도한 물·액체로부터 보호하기
수분·액체 손실 막기
기체로부터 보호하기
바람으로부터 보호하기
온도로부터 보호하기
불로부터 보호하기
얼음으로부터 보호하기
빛으로부터 보호하기
화학물질로부터 보호하기
방사선으로부터 보호하기
충격 관리하기
항력·난류 조절하기
휘어져 좌굴되는 현상 막기
균열·파열 막기
전단력 관리하기
변형을 막거나 허용하기
반복 하중에 따른 피로 파손 막기
침식 조절하기
마모 조절하기
재료의 성질 바꾸기
번식·성장 조절하기
자기 복제하기
항상성·평형 유지하기
자기 조직화 조율하기
종 내·종 간 협력하기
종 내·종 간 경쟁하기
생물 군집의 환경 교란에 대응하기
개체군·해충·질병 관리하기
생물다양성 유지하기
무기 화합물을 화학적으로 합성하기
유기 화합물을 화학적으로 합성하기
스스로 조립되기
무기 화합물을 화학적으로 분해하기
유기 화합물을 화학적으로 분해하기
전기에너지 조절·변환하기
자기에너지 조절·변환하기
화학에너지 조절·변환하기
역학적 에너지 조절·변환하기
열에너지 조절·변환하기
빛에너지 조절·변환하기
구조를 물리적으로 조립하기
구조를 분해하기
형태·재료 최적화하기
가시광선 신호 보내기
비가시광선 신호 보내기
소리 신호 보내기
접촉 신호 보내기
화학 신호 보내기
진동 신호 보내기
전기·자기 신호 보내기
잡음에서 신호 구별하기
신호 변환하기
신호에 반응하기
가시광선 감지하기
비가시광선 감지하기
전기·자기 감지하기
생명체의 질병 감지하기
접촉·기계적 힘 감지하기
화학물질 감지하기
대기 상태 감지하기
소리·진동 감지하기
온도 변화 감지하기
움직임 감지하기
공간·균형·방향 감지하기
모양·무늬 감지하기
고체 포획하기
액체 모으기
기체 포집하기
에너지 포획하기
고체 흡수·여과하기
액체 흡수·여과하기
기체 흡수·여과하기
고체 저장하기
액체 저장하기
기체 저장하기
에너지 저장하기
고체 분배·배출하기
액체 분배·배출하기
기체 분배·배출하기
에너지 분배·방출하기
해독·정화하기
구조색 바꾸기
화학적 색·색소 바꾸기
위장·의태하기
크기·모양 바꾸기""".splitlines()

# 원문에서 확인할 수 있는 생물 이름입니다.
NAMES = {
    'mussels?': '홍합', 'geckos?': '도마뱀붙이', 'lotus': '연꽃',
    'cicadas?': '매미', 'sharks?': '상어', 'pomelos?': '포멜로',
    'spiders?': '거미', 'pelicans?': '펠리컨', 'tree-hole frogs?': '나무 구멍에 사는 개구리',
    'frogs?': '개구리', 'common reeds?': '갈대', 'flying squirrels?': '날다람쥐',
    'fireflies|firefly': '반딧불이', 'water striders?': '소금쟁이',
    'caterpillars?': '나비·나방 애벌레', 'gannets?': '부비새류',
    'anglerfish': '아귀류', 'beetles?': '딱정벌레류', 'butterflies|butterfly': '나비',
    'penguins?': '펭귄', 'termites?': '흰개미', 'owls?': '올빼미류',
}


def clean(value):
    # HTML 태그와 불필요한 공백을 제거합니다.
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', str(value)))).strip()


def normalize(value):
    return re.sub(r'[^a-z0-9]+', '_', str(value).lower()).strip('_')


def safe_url(value):
    value = str(value).strip()
    parsed = urlparse(value)
    return value if parsed.scheme in ('http', 'https') and parsed.netloc else ''


def download(url):
    request = Request(url, headers={'User-Agent': 'BiomimicryStudentApp/1.0'})
    with urlopen(request, timeout=25) as response:
        return response.read()


@st.cache_data(ttl=86400, show_spinner=False)
def load_data():
    # JSON의 두 목록에서 같은 번호의 요약과 문헌 발췌문을 연결합니다.
    raw = json.loads(download(JSON_URL))
    if not isinstance(raw, dict):
        raise ValueError('JSON의 최상위 구조가 변경되었습니다.')
    summaries, excerpts = raw.get('summary'), raw.get('source_excerpt')
    if not isinstance(summaries, list) or not isinstance(excerpts, list):
        raise ValueError('summary 또는 source_excerpt 목록이 없습니다.')
    if len(summaries) != len(excerpts):
        raise ValueError('요약과 문헌 발췌문의 개수가 다릅니다.')

    records, seen = [], set()
    for index, (summary, excerpt) in enumerate(zip(summaries, excerpts)):
        if not isinstance(summary, str):
            continue
        summary = clean(summary)
        if not summary or summary in seen:
            continue
        seen.add(summary)
        parts = excerpt if isinstance(excerpt, list) else [excerpt]
        records.append({'id': index, 'summary': summary,
                        'excerpt': '\n\n'.join(clean(p) for p in parts if p)})

    functions = pd.read_csv(io.BytesIO(download(FUNCTION_URL))).fillna('')
    if not {'function', 'function_enumerated'}.issubset(functions.columns):
        raise ValueError('기능 CSV의 열 이름이 변경되었습니다.')

    # 논문 다운로드만 실패해도 생물 원리 검색은 사용할 수 있습니다.
    paper_error = ''
    try:
        papers = pd.read_csv(io.BytesIO(download(PAPER_URL))).fillna('')
        if not {'title', 'abstract', 'label_level_3', 'doi', 'url'}.issubset(papers.columns):
            raise ValueError('논문 CSV의 열 이름이 변경되었습니다.')
    except Exception as error:
        papers = pd.DataFrame()
        paper_error = str(error)

    if not records or functions.empty:
        raise ValueError('필수 데이터가 비어 있습니다.')
    return records, functions, papers, paper_error


def classify(problem, codes):
    # 한국어 키워드가 일치하는 수로 기능 후보를 정합니다.
    scores = []
    for code, (_, korean, _, _) in RULES.items():
        count = sum(word in problem.lower() for word in korean.split('|'))
        if code in codes and count:
            scores.append((count, code))
    return sorted(scores, key=lambda item: (-item[0], item[1]))


def find_records(records, code, extra, papers):
    pattern = RULES.get(code, ('', '', '', ''))[2]
    if not pattern:
        words = [w for w in code.split('_') if len(w) > 3]
        pattern = '|'.join(re.escape(w) for w in words)
    if not pattern:
        return []

    results = []
    for row in records:
        text = row['summary'].lower()
        hits = len(re.findall(pattern, text, flags=re.I))
        if hits and (not extra or extra.lower() in text):
            names = organism_names(row['summary'])
            related = find_papers(papers, code, row['summary'])
            # 생물명, 문헌, 관련 논문을 더 많이 제공할 수 있는 후보를 먼저 표시합니다.
            detail_count = sum((bool(names), bool(row['excerpt']), bool(related)))
            results.append((detail_count, hits, row, names, related))

    results.sort(key=lambda result: (-result[0], -result[1]))
    return results[:5]


def organism_names(summary):
    names = [
        name for pattern, name in NAMES.items()
        if re.search(r'\b(?:' + pattern + r')\b', summary, re.I)
    ]
    return list(dict.fromkeys(names))


def paper_labels(value):
    try:
        labels = ast.literal_eval(str(value))
        return {normalize(v) for v in labels} if isinstance(labels, list) else set()
    except (ValueError, SyntaxError):
        return set()


def find_papers(papers, code, summary):
    # 기능 라벨과 내용 단어가 연결되는 논문을 후보로 표시합니다.
    stop = {'these', 'their', 'which', 'through', 'using', 'have', 'with', 'that', 'from', 'this', 'when', 'into', 'they', 'than', 'other', 'water', 'structure'}
    tokens = set(re.findall(r'[a-z]{4,}', summary.lower())) - stop
    matches = []
    for _, row in papers.iterrows():
        if normalize(code) not in paper_labels(row['label_level_3']):
            continue
        shared = tokens & set(re.findall(r'[a-z]{4,}', (row['title'] + ' ' + row['abstract']).lower()))
        if len(shared) >= 2:
            matches.append((len(shared), row, shared))
    return sorted(matches, key=lambda item: -item[0])[:3]


@st.cache_resource
def translation_state():
    # 같은 앱을 사용하는 사람들의 요청도 하나씩 순서대로 처리합니다.
    import threading
    return {'lock': threading.Lock(), 'next_time': 0.0,
            'blocked_until': 0.0, 'translations': {}}


def translate_korean(text):
    import time
    import textwrap
    from deep_translator import GoogleTranslator
    from deep_translator.exceptions import TooManyRequests

    if not text.strip():
        return ''
    state = translation_state()
    chunks = textwrap.wrap(text, width=4500, break_long_words=True,
                           break_on_hyphens=False, replace_whitespace=False)
    translated = []

    for chunk in chunks:
        # 잠금 안에서 저장된 번역을 확인해 동시 중복 요청도 막습니다.
        with state['lock']:
            if chunk in state['translations']:
                translated.append(state['translations'][chunk])
                continue

            now = time.monotonic()
            if now < state['blocked_until']:
                seconds = int(state['blocked_until'] - now) + 1
                raise RuntimeError(f'번역 요청이 제한되었습니다. 약 {seconds}초 뒤 다시 검색해 주세요.')

            delay = state['next_time'] - now
            if delay > 0:
                time.sleep(delay)

            try:
                result = GoogleTranslator(source='en', target='ko').translate(chunk)
                if not result or (result.strip() == chunk.strip()
                                  and re.search(r'[A-Za-z]{4,}', chunk)):
                    raise ValueError('한국어 번역 결과를 받지 못했습니다.')
            except TooManyRequests as error:
                state['blocked_until'] = time.monotonic() + 60
                raise RuntimeError(
                    '번역 요청 제한으로 1분 동안 추가 요청을 멈췄습니다. '
                    '잠시 뒤 번역하기 버튼을 다시 눌러 주세요.'
                ) from error
            finally:
                # 응답을 받은 뒤에도 1.5초를 기다려 다음 요청을 보냅니다.
                state['next_time'] = time.monotonic() + 1.5

            # 성공한 번역만 저장합니다.
            state['translations'][chunk] = result
            if len(state['translations']) > 2000:
                oldest = next(iter(state['translations']))
                del state['translations'][oldest]
            translated.append(result)

    return '\n\n'.join(translated)


def show_paper(paper, shared, widget_key):
    import hashlib

    title = str(paper['title'])
    abstract = str(paper['abstract'])
    paper_id = hashlib.sha256((title + '\n' + abstract).encode()).hexdigest()
    saved = st.session_state.setdefault('paper_translations', {})

    # 처음에는 원문만 표시합니다.
    st.markdown('**논문 제목 · 영어 원문**')
    st.write(title)
    st.markdown('**논문 초록 · 영어 원문**')
    if abstract.strip():
        st.write(abstract)
    else:
        garden_note('초록이 없는 논문입니다.')

    url = safe_url(paper['url']) or (safe_url('https://doi.org/' + paper['doi']) if paper['doi'] else '')
    if url:
        st.link_button('논문 링크', url)

    st.caption('선택한 기능 라벨 일치 · 원문 공통 단어: ' + ', '.join(sorted(shared)))
    st.caption('관련 연구 후보이며, 위 생물 원리의 직접 근거인지 원문 확인이 필요합니다.')

    # 이 버튼을 눌렀을 때만 번역을 요청합니다.
    if paper_id not in saved:
        if st.button('🌐 한국어로 번역하기', key=widget_key):
            try:
                with st.spinner('선택한 논문을 번역하고 있어요…'):
                    korean_title = translate_korean(title)
                    korean_abstract = translate_korean(abstract)
                saved[paper_id] = (korean_title, korean_abstract)
            except ModuleNotFoundError:
                garden_note('requirements.txt에 deep-translator를 추가해 주세요.')
            except Exception as error:
                garden_note('번역 요청을 완료하지 못했습니다.')
                st.caption(str(error))

    # 다른 버튼을 눌러 화면이 다시 실행되어도 번역본을 유지합니다.
    if paper_id in saved:
        korean_title, korean_abstract = saved[paper_id]
        st.markdown('**🌱 한국어 번역**')
        st.write(korean_title)
        if korean_abstract:
            st.write(korean_abstract)
        st.caption('자동 번역입니다. 전문 용어와 학명은 영어 원문도 확인하세요.')


st.set_page_config(page_title='생체모방 아이디어 제안', page_icon='🌿', layout='wide')

# 식물 테마 디자인
st.markdown("""
<style>
.block-container {max-width: 980px; padding-top: 3rem;}
.garden-hero {
    padding: 1.35rem 1.6rem; border-radius: 22px;
    background: linear-gradient(125deg, #e4f2e3, #f6f4de);
    color: #174630; border: 1px solid #b8d4bd; margin-bottom: 1.2rem;
}
.garden-hero h1 {color: #174630; padding: 0; font-size: 2.15rem;}
.garden-hero p {margin: .45rem 0 0;}
.garden-note {
    color: #426a5a; opacity: .88; padding: .5rem .7rem;
    background: rgba(104, 157, 124, .12); border-radius: 8px;
}
@media (prefers-color-scheme: dark) {
    .garden-note {color: #b1d6bf;}
}
</style>
<div class="garden-hero">
<h1>🌿 생체모방 아이디어 제안</h1>
<p>생활 속 고민에서 출발해 자연이 문제를 해결하는 방법을 찾아보세요.</p>
</div>
""", unsafe_allow_html=True)


def garden_note(message):
    # 정보가 없거나 확인되지 않았을 때는 옅은 색으로 안내합니다.
    st.markdown(
        '<p class="garden-note">🍂 ' + html.escape(message) + '</p>',
        unsafe_allow_html=True,
    )


st.caption('논문은 영어 원문으로 표시됩니다. 원하는 논문의 한국어로 번역하기 버튼을 눌러 보세요.')

try:
    with st.spinner('생체모방 데이터를 불러오는 중입니다…'):
        records, functions, papers, paper_error = load_data()
except Exception as error:
    st.error('데이터를 불러오지 못했습니다. 인터넷 연결과 GitHub 원본 주소를 확인하고 다시 시도해 주세요.')
    with st.expander('오류 상세'):
        st.text(str(error))
    if st.button('다시 불러오기'):
        st.cache_data.clear()
        st.rerun()
    st.stop()

if paper_error:
    st.warning('논문 데이터를 불러오지 못했습니다. 생물 원리 검색은 사용할 수 있습니다.')
    if st.button('논문 데이터 다시 불러오기'):
        st.cache_data.clear()
        st.rerun()

problem = st.text_area('해결하고 싶은 실생활 문제', placeholder='예: 비가 오면 신발이 젖어요. / 물건을 떨어뜨려도 깨지지 않게 하고 싶어요.', max_chars=1000)
codes = functions['function'].astype(str).tolist()

# 기능 선택창에는 한국어를 표시하고 검색에는 영어 코드를 사용합니다.
function_labels = {}
for _, function_row in functions.iterrows():
    number = int(function_row['function_enumerated'])
    function_labels[str(function_row['function'])] = (
        FUNCTION_KO[number] if 0 <= number < len(FUNCTION_KO)
        else f'새로 추가된 기능 {number} (번역 준비 중)'
    )

ranked = classify(problem, codes)
recommended = ranked[0][1] if ranked else None
uncertain = not ranked or (len(ranked) > 1 and ranked[0][0] == ranked[1][0])


def label(code):
    return function_labels.get(code, '기능 번역 준비 중')


# 문제를 입력하기 전에는 기능 선택창을 숨깁니다.
if not problem.strip():
    st.session_state.pop('search_results', None)
    st.session_state.pop('search_context', None)
    st.stop()

if uncertain:
    garden_note('필요한 기능을 자동으로 정하기 어려워요. 아래 목록에서 직접 골라 주세요.')
    if ranked:
        st.caption('기능 후보 · ' + ', '.join(RULES[code][0] for _, code in ranked[:3]))
    selected = st.selectbox(
        f'필요한 기능 확인·선택 (전체 기능 {len(codes)}개)',
        [''] + codes,
        format_func=lambda code: label(code) if code else '기능을 선택하세요',
        key='function_' + problem.strip(),
    )
else:
    selected = recommended
    st.success('🌱 자동으로 정한 기능 · ' + label(selected))

extra = st.text_input('선택 사항: 결과를 좁힐 영어 단어', placeholder='예: mussel, wet, lotus (요약에 이 표현이 있는 자료만 표시)')

# 번역 버튼을 눌러도 검색 결과가 사라지지 않도록 보관합니다.
context = (problem.strip(), selected, extra.strip())
if st.session_state.get('search_context') != context:
    st.session_state.pop('search_results', None)
    st.session_state['search_context'] = context

if st.button('🌱 생물 원리 찾기', type='primary', disabled=not selected):
    st.session_state['search_results'] = find_records(records, selected, extra.strip(), papers)

if 'search_results' in st.session_state:
    st.subheader('🍃 추천 아이디어')
    results = st.session_state['search_results']

    if not results:
        garden_note('조건과 연결되는 원리를 찾지 못했습니다. 기능을 다시 선택하거나 영어 검색어를 줄여 보세요.')
    else:
        st.caption('기능 표현이 일치하는 후보입니다. 젖은 환경·재료·온도 등 입력한 모든 조건에 적합하다는 의미는 아닙니다.')

    for number, (_, _, row, names, related) in enumerate(results, 1):
        with st.container(border=True):
            st.subheader(f'🌿 {number}. ' + (' · '.join(names) if names else '생물 원리'))
            if not names:
                garden_note('생물 이름을 자동으로 확인하지 못했어요.')

            st.markdown('**생물의 특징·작동 원리 — 데이터 요약 원문**')
            st.write(row['summary'])

            st.markdown('**활용할 특징**')
            st.write('위 원문에서 설명한 구조·작동 방식 중, 선택한 기능과 관련되는 부분을 참고하세요. 원문의 세부 원리를 임의로 번역·확장하지 않았습니다.')

            st.markdown('**자료에 제시된 응용 사례**')
            garden_note('이 JSON에는 기술 응용 사례를 구분한 항목이 없어 자동으로 확인하지 못했습니다.')

            st.markdown('**🌱 원리를 바탕으로 제안한 활용 예시**')
            direction = RULES.get(selected, ('', '', '', ''))[3]
            st.write((direction + '를 구상할 때 위 생물의 구조를 참고해 볼 수 있습니다.') if direction else '선택한 기능을 수행하는 설계를 구상할 때 위 원문의 구조를 참고해 볼 수 있습니다.')
            st.caption('기능에 따른 일반적인 설계 제안이며, 이 생물로 검증된 제품 사례가 아닙니다. 실제 적합성은 제작·실험으로 확인해야 합니다.')

            st.link_button('요약 데이터 출처', JSON_URL)
            st.caption(f'원본 summary / source_excerpt 목록의 {row["id"] + 1}번째 항목')

            with st.expander('연결된 문헌 발췌문 (영어 원문)'):
                if row['excerpt']:
                    st.write(row['excerpt'])
                else:
                    garden_note('발췌문이 없어요.')
                st.caption('원본 JSON에는 문헌별 URL이 별도 항목으로 제공되지 않습니다.')

            st.markdown('**관련 연구 후보**')
            if not related:
                garden_note('관련 연구를 찾지 못했습니다.' if not paper_error else '논문 데이터를 불러오지 못해 확인할 수 없습니다.')

            for paper_index, (_, paper, shared) in enumerate(related):
                show_paper(paper, shared, f'paper_{row["id"]}_{paper_index}')

with st.expander('데이터와 검색 방식'):
    st.write(f'중복 제거 원리 {len(records):,}개 · 기능 {len(functions)}개 · 논문 {len(papers)}개')
    st.write('한국어 자동 분류는 코드에 등록된 기능을 지원하며, 나머지 기능은 직접 선택할 수 있습니다. 선택한 영어 기능의 단어로 찾은 결과는 관련성이 넓을 수 있습니다.')
    st.write('자료 공개: NASA PeTaL / 생물 전략 자료 기반: AskNature. 이 앱은 NASA 또는 AskNature의 공식 서비스가 아닙니다.')
    st.link_button('생물 원리 JSON', JSON_URL)
    st.link_button('기능 CSV', FUNCTION_URL)
    st.link_button('논문 CSV', PAPER_URL)
