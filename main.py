import ast
import html
import io
import json
import re
from urllib.request import Request, urlopen
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

# 유료 API 없이, 한국어 표현을 영어 기능과 연결하여 검색합니다.
BASE = 'https://raw.githubusercontent.com/nasa-petal/'
JSON_URL = BASE + 'bio-strategy-extractor/main/asknature-data.json'
PAPER_URL = BASE + 'nasa_petal_snorkel/main/labeled_data.csv'
FUNCTION_URL = BASE + 'nasa_petal_snorkel/main/biomimicry_functions_enumerated.csv'

# 기능 코드: (한국어 이름, 문제 표현, 원문 검색 표현, 활용 방향)
# 검색 표현은 원리를 번역한 것이 아니라 관련 자료를 찾는 단서입니다.
RULES = {
    'attach_permanently': (
        '영구 접착',
        '접착|붙이|붙는|붙게|안 붙|떨어지',
        'adhesi|adhere|glue|cement',
        '접착 구조나 물질을 참고한 접합 방식'
    ),
    'attach_temporarily': (
        '일시적 부착',
        '탈부착|뗐다|떼었다|붙였다|흡착',
        'temporary adhesion|reversible adhesion|suction|attach',
        '반복하여 붙이고 떼는 부착 방식'
    ),
    'protect_from_excess_liquids': (
        '과도한 물로부터 보호',
        '방수|젖|빗물|비 오는|물 들어|물들어|물 침투',
        'water.repell|waterproof|hydrophobic|prevent.*water|water.*prevent',
        '물 침투를 줄이는 표면이나 덮개'
    ),
    'protect_from_loss_liquids': (
        '수분 손실 방지',
        '건조|마르|보습|수분 손실',
        'water loss|desiccation|retain.*water|prevent.*dry',
        '수분이 빠져나가는 것을 줄이는 보관 구조'
    ),
    'manage_impact': (
        '충격 관리',
        '충격|떨어뜨|떨어졌|완충|부딪|깨지',
        'impact|shock|cushion|dissipat.*energy',
        '충격을 분산하는 포장재나 보호 장치'
    ),
    'prevent_fracture_rupture': (
        '파손 방지',
        '파손|부러|깨지|균열',
        'fracture|crack|rupture|toughness',
        '균열이나 파손을 줄이는 재료 구조'
    ),
    'regulate_drag_turbulence': (
        '항력과 난류 조절',
        '마찰|저항|항력|난류|물살',
        'drag|turbulence|friction',
        '유체의 저항을 줄이는 표면이나 형상'
    ),
    'protect_from_temperature': (
        '온도로부터 보호',
        '더위|추위|뜨거|차갑|단열|보온',
        'insulat|thermal|heat loss|overheat|cooling',
        '열 이동을 조절하는 외피나 단열 구조'
    ),
    'modify_convert_thermal_energy': (
        '열에너지 변환·조절',
        '냉각|식히|열 조절|온도 조절',
        'heat exchange|cooling|thermal|thermoregulat',
        '열을 방출하거나 교환하는 구조'
    ),
    'protect_from_microbes': (
        '미생물로부터 보호',
        '세균|항균|살균|미생물|곰팡이',
        'antimicrobial|antibacterial|bactericidal|microb',
        '미생물 부착이나 증식을 줄이는 표면'
    ),
    'absorb_filter_solids': (
        '고체 입자 여과',
        '먼지|미세먼지|입자|필터|여과',
        'filter|filtration|trap.*particle|capture.*particle',
        '입자를 걸러 내는 필터 구조'
    ),
    'detox_purify': (
        '해독·정화',
        '정화|오염|독성|유해 물질',
        'detox|purif|pollut|contaminant',
        '오염 물질을 제거하는 정화 방식'
    ),
    'capture_liquids': (
        '물 모으기',
        '물 모으|물모으|집수|안개|물 부족',
        'collect.*water|harvest.*water|fog|capture.*water',
        '안개나 물방울을 모으는 집수 장치'
    ),
    'sense_sound_vibrations': (
        '소리·진동 감지',
        '진동 감지|소리 감지|소리감지|진동감지',
        'sense.*vibrat|detect.*sound|hear|auditory',
        '소리나 진동을 감지하는 센서'
    ),
    'send_sound_signals': (
        '소리 전달',
        '소리 전달|소리 키|증폭|잘 들리',
        'amplif|resonan|vocal|sound production',
        '소리가 잘 전달되도록 하는 공명 구조'
    ),
    'sense_touch_and_mechanical_forces': (
        '접촉·힘 감지',
        '압력|촉각|접촉 감지|바람 감지',
        'mechanosens|sense.*air|sense.*force|sensitive.*hair',
        '작은 힘이나 공기 흐름을 감지하는 센서'
    ),
    'camouflage_mimicry': (
        '위장·의태',
        '위장|숨기|눈에 띄|보이지',
        'camouflage|mimicry|conceal',
        '주변 환경에 맞춰 눈에 덜 띄는 외관'
    ),
    'change_structural_color': (
        '구조색',
        '구조색|변색|색 바꾸|색 변화',
        'structural colo|iridescen|photonic',
        '표면 미세 구조로 색을 표현하는 소재'
    ),
    'modify_convert_light_energy': (
        '빛에너지 변환',
        '태양광|광합성|빛 에너지',
        'photosynth|solar|light energy',
        '빛을 모으거나 에너지로 전환하는 구조'
    ),
    'store_energy': (
        '에너지 저장',
        '에너지 저장|전기 저장|배터리',
        'store.*energy|energy stor',
        '에너지를 저장하는 구조나 방식'
    ),
}

# 이 목록에 없는 생물은 이름을 추측하지 않고 확인 필요로 표시합니다.
NAMES = {
    'mussels?': '홍합',
    'geckos?': '도마뱀붙이',
    'lotus': '연꽃',
    'cicadas?': '매미',
    'sharks?': '상어',
    'pomelos?': '포멜로',
    'spiders?': '거미',
    'pelicans?': '펠리컨',
    'tree-hole frogs?': '나무 구멍에 사는 개구리',
    'frogs?': '개구리',
    'common reeds?': '갈대',
    'flying squirrels?': '날다람쥐',
    'fireflies|firefly': '반딧불이',
    'water striders?': '소금쟁이',
    'caterpillars?': '나비·나방 애벌레',
    'gannets?': '부비새류',
    'anglerfish': '아귀류',
    'beetles?': '딱정벌레류',
    'butterflies|butterfly': '나비',
    'penguins?': '펭귄',
    'termites?': '흰개미',
    'owls?': '올빼미류',
}


def clean(value):
    # 문헌 발췌문의 HTML 태그를 없애고 일반 텍스트로 표시합니다.
    return re.sub(
        r'\s+',
        ' ',
        html.unescape(re.sub(r'<[^>]+>', ' ', str(value)))
    ).strip()


def normalize(value):
    return re.sub(
        r'[^a-z0-9]+', '_', str(value).lower()
    ).strip('_')


def safe_url(value):
    value = str(value).strip()
    parsed = urlparse(value)
    return (
        value
        if parsed.scheme in ('http', 'https') and parsed.netloc
        else ''
    )


def download(url):
    request = Request(
        url,
        headers={'User-Agent': 'BiomimicryStudentApp/1.0'}
    )
    with urlopen(request, timeout=25) as response:
        return response.read()


@st.cache_data(ttl=86400, show_spinner=False)
def load_data():
    # 실제 JSON은 두 개의 병렬 목록입니다.
    # 같은 번호의 요약과 문헌 발췌문을 연결합니다.
    raw = json.loads(download(JSON_URL))

    if not isinstance(raw, dict):
        raise ValueError('JSON의 최상위 구조가 변경되었습니다.')

    summaries = raw.get('summary')
    excerpts = raw.get('source_excerpt')

    if not isinstance(summaries, list) or not isinstance(excerpts, list):
        raise ValueError(
            'summary 또는 source_excerpt 목록이 없습니다.'
        )

    if len(summaries) != len(excerpts):
        raise ValueError('요약과 문헌 발췌문의 개수가 다릅니다.')

    records = []
    seen = set()

    for index, (summary, excerpt) in enumerate(
        zip(summaries, excerpts)
    ):
        if not isinstance(summary, str):
            continue

        summary = clean(summary)

        if not summary or summary in seen:
            continue

        seen.add(summary)

        parts = excerpt if isinstance(excerpt, list) else [excerpt]

        records.append({
            'id': index,
            'summary': summary,
            'excerpt': '\n\n'.join(
                clean(part) for part in parts if part
            )
        })

    # CSV는 pandas로 읽습니다.
    functions = pd.read_csv(
        io.BytesIO(download(FUNCTION_URL))
    ).fillna('')

    if not {
        'function', 'function_enumerated'
    }.issubset(functions.columns):
        raise ValueError('기능 CSV의 열 이름이 변경되었습니다.')

    # 논문만 불러오지 못한 경우에도 원리 검색은 계속 사용합니다.
    paper_error = ''

    try:
        papers = pd.read_csv(
            io.BytesIO(download(PAPER_URL))
        ).fillna('')

        required_columns = {
            'title', 'abstract', 'label_level_3', 'doi', 'url'
        }

        if not required_columns.issubset(papers.columns):
            raise ValueError('논문 CSV의 열 이름이 변경되었습니다.')

    except Exception as error:
        papers = pd.DataFrame()
        paper_error = str(error)

    if not records or functions.empty:
        raise ValueError('필수 데이터가 비어 있습니다.')

    return records, functions, papers, paper_error


def classify(problem, codes):
    # 키워드 개수를 점수로 사용합니다.
    # 이 점수는 AI의 신뢰도나 확률이 아닙니다.
    scores = []

    for code, (_, korean, _, _) in RULES.items():
        count = sum(
            word in problem.lower()
            for word in korean.split('|')
        )

        if code in codes and count:
            scores.append((count, code))

    return sorted(
        scores,
        key=lambda item: (-item[0], item[1])
    )


def find_records(records, code, extra):
    # 요약에서 기능 표현이 확인되는 자료만 후보로 삼습니다.
    # 사용 환경까지 적합한지는 원문 확인이 필요합니다.
    pattern = RULES.get(code, ('', '', '', ''))[2]

    if not pattern:
        words = [
            word for word in code.split('_')
            if len(word) > 3
        ]
        pattern = '|'.join(
            re.escape(word) for word in words
        )

    if not pattern:
        return []

    results = []

    for row in records:
        text = row['summary'].lower()
        hits = len(re.findall(pattern, text, flags=re.I))

        if hits and (
            not extra or extra.lower() in text
        ):
            results.append((hits, row))

    ranked = sorted(
        results,
        key=lambda item: -item[0]
    )

    return [row for _, row in ranked[:5]]


def paper_labels(value):
    # CSV의 문자열 형태 목록을 실제 목록으로 바꿉니다.
    try:
        labels = ast.literal_eval(str(value))

        if isinstance(labels, list):
            return {normalize(label) for label in labels}

        return set()

    except (ValueError, SyntaxError):
        return set()


def find_papers(papers, code, summary):
    # 기능 라벨이 같고 내용 단어가 두 개 이상 겹치는 논문만
    # 후보로 표시합니다. 직접 근거라고 단정하지 않습니다.
    stop = {
        'these', 'their', 'which', 'through', 'using',
        'have', 'with', 'that', 'from', 'this', 'when',
        'into', 'they', 'than', 'other', 'water', 'structure'
    }

    tokens = set(
        re.findall(r'[a-z]{4,}', summary.lower())
    ) - stop

    matches = []

    for _, row in papers.iterrows():
        labels = paper_labels(row['label_level_3'])

        if normalize(code) not in labels:
            continue

        paper_text = (
            row['title'] + ' ' + row['abstract']
        ).lower()

        paper_tokens = set(
            re.findall(r'[a-z]{4,}', paper_text)
        )

        shared = tokens & paper_tokens

        if len(shared) >= 2:
            matches.append((len(shared), row, shared))

    return sorted(
        matches,
        key=lambda item: -item[0]
    )[:3]


st.set_page_config(
    page_title='생체모방 아이디어 제안',
    page_icon='🌿',
    layout='wide'
)

st.title('🌿 생체모방 아이디어 제안')

st.write(
    '해결하고 싶은 문제를 입력하고, '
    '참고할 생물의 기능과 원리를 찾아보세요.'
)

st.caption(
    '유료 API 없이 키워드로 검색합니다. '
    '원문이 영어인 경우 영어 그대로 표시하며, '
    '새로운 원리나 번역을 생성하지 않습니다.'
)

try:
    with st.spinner('생체모방 데이터를 불러오는 중입니다…'):
        records, functions, papers, paper_error = load_data()

except Exception as error:
    st.error(
        '데이터를 불러오지 못했습니다. '
        '인터넷 연결과 GitHub 원본 주소를 확인하고 '
        '다시 시도해 주세요.'
    )

    with st.expander('오류 상세'):
        st.text(str(error))

    if st.button('다시 불러오기'):
        st.cache_data.clear()
        st.rerun()

    st.stop()

if paper_error:
    st.warning(
        '논문 데이터를 불러오지 못했습니다. '
        '생물 원리 검색은 사용할 수 있습니다.'
    )

    if st.button('논문 데이터 다시 불러오기'):
        st.cache_data.clear()
        st.rerun()

problem = st.text_area(
    '해결하고 싶은 실생활 문제',
    placeholder=(
        '예: 비가 오면 신발이 젖어요. / '
        '물건을 떨어뜨려도 깨지지 않게 하고 싶어요.'
    ),
    max_chars=1000
)

codes = functions['function'].astype(str).tolist()

ranked = classify(problem, codes)
recommended = ranked[0][1] if ranked else None

uncertain = (
    not ranked
    or (
        len(ranked) > 1
        and ranked[0][0] == ranked[1][0]
    )
)

if problem.strip():
    if uncertain:
        st.info(
            '분류가 불확실합니다. '
            '아래에서 필요한 기능을 직접 선택해 주세요.'
        )
    else:
        candidates = ', '.join(
            RULES[code][0]
            for _, code in ranked[:3]
        )
        st.write('입력에서 찾은 기능 후보: ' + candidates)


def label(code):
    if code in RULES:
        return f'{RULES[code][0]} · {code}'

    return code.replace('_', ' ')


options = [''] + codes

default_index = (
    options.index(recommended)
    if recommended and not uncertain
    else 0
)

selected = st.selectbox(
    '필요한 기능 확인·선택 (전체 기능 100개)',
    options,
    index=default_index,
    format_func=lambda code: (
        label(code) if code else '기능을 선택하세요'
    )
)

extra = st.text_input(
    '선택 사항: 결과를 좁힐 영어 단어',
    placeholder=(
        '예: mussel, wet, lotus '
        '(요약에 이 표현이 있는 자료만 표시)'
    )
)

if st.button('생물 원리 찾기', type='primary'):
    if not problem.strip():
        st.warning(
            '먼저 해결하고 싶은 문제를 입력해 주세요.'
        )

    elif not selected:
        st.warning('필요한 기능을 선택해 주세요.')

    else:
        st.subheader('선택한 기능: ' + label(selected))

        results = find_records(
            records,
            selected,
            extra.strip()
        )

        if not results:
            st.info(
                '조건과 연결되는 원리를 찾지 못했습니다. '
                '기능을 다시 선택하거나 '
                '영어 검색어를 줄여 보세요.'
            )

        else:
            st.caption(
                '기능 표현이 일치하는 후보입니다. '
                '젖은 환경·재료·온도 등 입력한 모든 조건에 '
                '적합하다는 의미는 아닙니다.'
            )

        for number, row in enumerate(results, 1):
            names = [
                name
                for pattern, name in NAMES.items()
                if re.search(
                    r'\b(?:' + pattern + r')\b',
                    row['summary'],
                    re.I
                )
            ]

            # 같은 이름이 반복되면 한 번만 표시합니다.
            organism_name = (
                ' · '.join(dict.fromkeys(names))
                if names
                else '생물 이름: 자동 확인 불가'
            )

            with st.container(border=True):
                st.subheader(
                    f'{number}. {organism_name}'
                )

                st.markdown(
                    '**생물의 특징·작동 원리 '
                    '— 데이터 요약 원문**'
                )
                st.write(row['summary'])

                st.markdown('**활용할 특징**')
                st.write(
                    '위 원문에서 설명한 구조·작동 방식 중, '
                    '선택한 기능과 관련되는 부분을 참고하세요. '
                    '원문의 세부 원리를 임의로 '
                    '번역·확장하지 않았습니다.'
                )

                st.markdown(
                    '**자료에 제시된 응용 사례**'
                )
                st.write(
                    '이 JSON에는 기술 응용 사례를 구분한 '
                    '항목이 없어 자동으로 확인하지 못했습니다.'
                )

                st.markdown(
                    '**원리를 바탕으로 제안한 활용 예시**'
                )

                direction = RULES.get(
                    selected,
                    ('', '', '', '')
                )[3]

                if direction:
                    st.write(
                        direction
                        + '를 구상할 때 위 생물의 구조를 '
                        '참고해 볼 수 있습니다.'
                    )
                else:
                    st.write(
                        '선택한 기능을 수행하는 설계를 구상할 때 '
                        '위 원문의 구조를 참고해 볼 수 있습니다.'
                    )

                st.caption(
                    '기능에 따른 일반적인 설계 제안이며, '
                    '이 생물로 검증된 제품 사례가 아닙니다. '
                    '실제 적합성은 제작·실험으로 확인해야 합니다.'
                )

                st.link_button(
                    '요약 데이터 출처',
                    JSON_URL
                )

                st.caption(
                    '원본 summary / source_excerpt 목록의 '
                    f'{row["id"] + 1}번째 항목'
                )

                with st.expander(
                    '연결된 문헌 발췌문 (영어 원문)'
                ):
                    st.text(
                        row['excerpt']
                        or '발췌문이 없습니다.'
                    )
                    st.caption(
                        '원본 JSON에는 문헌별 URL이 '
                        '별도 항목으로 제공되지 않습니다.'
                    )

                st.markdown(
                    '**관련 연구 후보 — 논문 CSV 검색**'
                )

                related = (
                    find_papers(
                        papers,
                        selected,
                        row['summary']
                    )
                    if not papers.empty
                    else []
                )

                if not related:
                    if paper_error:
                        st.write(
                            '논문 데이터를 불러오지 못해 '
                            '확인할 수 없습니다.'
                        )
                    else:
                        st.write(
                            '관련 연구를 찾지 못했습니다.'
                        )

                for _, paper, shared in related:
                    url = safe_url(paper['url'])

                    if not url and paper['doi']:
                        url = safe_url(
                            'https://doi.org/'
                            + paper['doi']
                        )

                    st.write(paper['title'])

                    st.caption(
                        '선택한 기능 라벨 일치 · '
                        '원문 공통 단어: '
                        + ', '.join(sorted(shared))
                    )

                    st.caption(
                        '내용상 관련성을 추가로 확인해야 하는 '
                        '후보이며, 위 생물 원리의 직접 근거임을 '
                        '보장하지 않습니다.'
                    )

                    if url:
                        st.link_button('논문 링크', url)

                    st.write(paper['abstract'])

with st.expander('데이터와 검색 방식'):
    st.write(
        f'중복 제거 원리 {len(records):,}개 · '
        f'기능 {len(functions)}개 · '
        f'논문 {len(papers)}개'
    )

    st.write(
        '한국어 자동 분류는 코드에 등록된 기능을 지원하며, '
        '나머지 기능은 직접 선택할 수 있습니다. '
        '선택한 영어 기능의 단어로 찾은 결과는 '
        '관련성이 넓을 수 있습니다.'
    )

    st.write(
        '자료 공개: NASA PeTaL / '
        '생물 전략 자료 기반: AskNature. '
        '이 앱은 NASA 또는 AskNature의 공식 서비스가 아닙니다.'
    )

    st.link_button('생물 원리 JSON', JSON_URL)
    st.link_button('기능 CSV', FUNCTION_URL)
    st.link_button('논문 CSV', PAPER_URL)
