# 기본 확장자

`backend/engines/tier1_rule.py`에서 생성했다. 설정 화면에서 확장자를 더 등록할 수 있다.

| 카테고리 | 확장자 | Tier 1 신뢰도 |
|---|---|---|
| 문서 | pdf, docx, doc, txt, md, hwp, rtf | 0.50 (범용 형식, 내용 분석이 뒤집을 수 있음) |
| 프레젠테이션 | pptx, ppt, key | 0.85 |
| 스프레드시트 | xlsx, xls, csv | 0.85 |
| 데이터 | json, xml, yaml, sql | 0.85 |
| 코드 | py, js, ts, jsx, tsx, java, cpp, c, h, go, rs, html, css | 0.85 |
| 이미지 | jpg, jpeg, png, gif, svg, webp, bmp | 0.85 |
| 영상 | mp4, mov, avi, mkv, webm | 0.85 |
| 오디오 | mp3, wav, flac, aac, ogg | 0.85 |
| 압축 | zip, tar, gz, rar, 7z | 0.85 |
