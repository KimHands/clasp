"""
분류 평가용 합성 데이터. 모든 이름과 내용은 허구다.
split은 분류 로직을 고치기 전에 정했다. holdout은 임계값과 키워드 조정에 쓰지 않는다.
"""
from dataclasses import dataclass

OS_REPORT = "프로세스 스케줄링과 가상 메모리, 페이지 교체 알고리즘을 비교 분석하였다. 실험 결과를 표로 정리하고 결론을 서술한다. " * 8
SECURITY_REPORT = "웹 서비스 취약점 점검 결과를 보고한다. SQL 삽입과 교차 사이트 스크립팅 사례를 확인했고 조치 방안을 제안한다. " * 8
MEETING = "일시: 3월 4일\n참석자: 가나다, 라마바\n안건: 신규 서비스 일정 조율\n결정 사항: 다음 주까지 요구사항을 확정한다.\n"
CONTRACT = "제1조(목적) 본 계약은 갑과 을의 용역 수행 조건을 정한다.\n제2조(기간) 계약 기간은 6개월로 한다.\n제3조(대금) 대금은 월 단위로 지급한다.\n"
PROPOSAL = "사업 개요와 추진 배경을 설명한다. 목표 시장과 예상 효과, 추진 일정과 소요 예산을 제안한다. " * 6
MANUAL = "# 사용 설명서\n설치 방법과 초기 설정 절차를 안내합니다. 문제가 생기면 아래 순서대로 확인하세요.\n" * 4
THESIS = "This paper studies graph partitioning. We review related work, describe our method, and report experimental results in the final section. " * 6
SLIDES = "발표 순서\n1. 배경\n2. 문제 정의\n3. 시연\n4. 결론\n오늘 세미나에서 발표할 내용입니다. 다음 슬라이드에서 시연합니다.\n" * 5
SLIDES_EN = "Agenda\nMotivation\nLive demo\nNext slide: results\nThank you for attending this keynote presentation.\n" * 6
TALK = "안녕하세요, 오늘 발표를 맡은 발표자입니다. 첫 번째 슬라이드부터 설명드리겠습니다. 질문은 발표 뒤에 받겠습니다.\n" * 5
SEMINAR = "강의 자료\n1주차 세미나 슬라이드\n핵심 정리\n발표 과제 안내\n다음 시간 예고\n" * 6
BUDGET = [["항목", "예산", "집행", "잔액"], ["행사비", 500000, 320000, 180000], ["교통비", 200000, 90000, 110000]]
ATTEND = [["이름", "1주", "2주", "3주"], ["가", "출석", "결석", "출석"], ["나", "출석", "출석", "출석"]]
SETTLE = [["날짜", "내역", "금액"], ["3/1", "식비", 12000], ["3/2", "교통", 3000]]
SENSOR = [["timestamp", "sensor_id", "value"], ["2026-01-01T00:00", "s1", 21.5], ["2026-01-01T00:01", "s1", 21.6]]
SURVEY = [["응답자", "만족도", "재사용의향"], ["A", 5, "예"], ["B", 3, "아니오"]]
CODE_DOC = "def add(a, b):\n    return a + b\n\nclass Stack:\n    def push(self, item):\n        self.items.append(item)\n" * 6
API_NOTE = "함수 시그니처와 클래스 구조, 소스코드 리팩터링 메모. import 순서를 정리하고 알고리즘 구현을 수정했다.\n" * 5
NOTE = "오늘 장 볼 것: 우유, 달걀, 사과. 주말에 친구 만나기.\n"
CATALOG = "배경화면 모음 카탈로그. 풍경 사진과 색감 안내.\n"
RECIPE = "재료를 손질해 냄비에 넣고 약한 불로 20분 끓인다. 소금으로 간을 맞춘다.\n" * 4


@dataclass(frozen=True)
class Item:
    name: str
    kind: str
    content: object
    expected: str | None
    split: str = "tune"


ITEMS = [
    Item("운영체제_기말과제.pdf", "pdf", OS_REPORT, "문서"),
    Item("final_report_v2.pdf", "pdf", SECURITY_REPORT, "문서"),
    Item("회의록_0304.docx", "docx", MEETING, "문서"),
    Item("notes_draft.docx", "docx", OS_REPORT, "문서"),
    Item("용역계약.txt", "txt", CONTRACT, "문서"),
    Item("사업계획_초안.docx", "docx", PROPOSAL, "문서"),
    Item("설치안내.md", "md", MANUAL, "문서"),
    Item("wallpaper_collection.pdf", "pdf", CATALOG, "문서"),
    Item("장보기.txt", "txt", NOTE, "문서"),
    Item("scan_0412.pdf", "pdf", SLIDES, "프레젠테이션"),
    Item("keynote_export.pdf", "pdf", SLIDES_EN, "프레젠테이션"),
    Item("발표대본.docx", "docx", TALK, "프레젠테이션"),
    Item("deck.pptx", "bin", b"PK\x03\x04", "프레젠테이션"),
    Item("2026_예산안.xlsx", "xlsx", BUDGET, "스프레드시트"),
    Item("paper_cup_order.xlsx", "xlsx", SETTLE, "스프레드시트"),
    Item("설문결과.csv", "csv", SURVEY, "스프레드시트"),
    Item("sensor_log.json", "bin", b'{"a": 1}', "데이터"),
    Item("schema_dump.sql", "bin", b"CREATE TABLE t (id INT);", "데이터"),
    Item("main.py", "bin", b"print(1)\n", "코드"),
    Item("report_template.py", "bin", b"print(2)\n", "코드"),
    Item("코드메모.md", "md", API_NOTE, "코드"),
    Item("photo_001.jpg", "bin", b"\xff\xd8\xff\xe0", "이미지"),
    Item("voice_memo.mp3", "bin", b"ID3", "오디오"),
    Item("mystery.xyz", "bin", b"?", None),

    Item("논문초고.pdf", "pdf", THESIS, "문서", "holdout"),
    Item("thesis_final.docx", "docx", THESIS, "문서", "holdout"),
    Item("합의서.docx", "docx", CONTRACT, "문서", "holdout"),
    Item("김치찌개.txt", "txt", RECIPE, "문서", "holdout"),
    Item("guide_to_setup.md", "md", MANUAL, "문서", "holdout"),
    Item("1주차.pdf", "pdf", SEMINAR, "프레젠테이션", "holdout"),
    Item("download (3).pdf", "pdf", SLIDES, "프레젠테이션", "holdout"),
    Item("출석부.xlsx", "xlsx", ATTEND, "스프레드시트", "holdout"),
    Item("정산.csv", "csv", SETTLE, "스프레드시트", "holdout"),
    Item("readings.xml", "bin", b"<a/>", "데이터", "holdout"),
    Item("utils_listing.pdf", "pdf", CODE_DOC, "코드", "holdout"),
    Item("clip.mp4", "bin", b"\x00\x00", "영상", "holdout"),
    Item("backup.zip", "bin", b"PK\x03\x04", "압축", "holdout"),
    Item("unknown.qqq", "bin", b"?", None, "holdout"),
]
