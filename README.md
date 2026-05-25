team29 - 다이소 vs 올리브영 제품 리뷰 감성분석

[팀원] 경영학과 202643173 문민채, 경영학과 202643270 임은지

[프로젝트 소개]
다이소와 올리브영의 유사 제품군 리뷰 데이터를 수집하여 소비자 반응과 브랜드 인식 차이를 비교·분석하는 프로그램이다. 웹 크롤링, CSV 파일 업로드, 유튜브 댓글 수집 기능을 통해 리뷰 데이터를 확보하며, 형태소 분석 및 감성사전 기반 감성분석을 수행한다. 또한 단어 빈도 분석과 워드클라우드 시각화를 통해 브랜드별 주요 키워드와 소비자 인식 차이를 한눈에 확인할 수 있도록 구성하였다.

[실행방법]

파이썬 터미널을 열고 필요한 라이브러리를 설치한다.
py -m pip install -r requirements.txt 를 입력한다.
py -m streamlit run app.py 를 입력하여 프로그램을 실행한다.
Streamlit 화면에서 브랜드와 수집 방식을 선택한 후 제품명 및 URL 등을 입력하여 리뷰 데이터를 수집한다.
전처리 및 감성분석 버튼을 실행하면 단어 빈도 분석, 워드클라우드, 감성 비율 그래프를 확인할 수 있다.

[유튜브 데이터 API 키 발급 방법]
1. Google Cloud Console 접속
먼저 Google Cloud Console에 접속한다.
검색창에 Google Cloud Console을 검색하거나, Google Cloud Platform 사이트에 접속한 뒤 본인의 Google 계정으로 로그인한다.

2. 새 프로젝트 생성
상단의 프로젝트 선택 메뉴를 클릭한 뒤 새 프로젝트를 선택한다.
프로젝트 이름을 입력한 뒤 만들기 버튼을 누른다.

3. YouTube Data API v3 사용 설정
프로젝트가 생성되면 왼쪽 메뉴에서 API 및 서비스로 이동한다.
그다음 라이브러리 메뉴를 클릭한다.
검색창에 다음과 같이 입력한다.
YouTube Data API v3
검색 결과에서 YouTube Data API v3를 선택한 뒤 사용 버튼을 누른다.
YouTube Data API는 영상 검색, 채널 정보, 댓글, 재생목록 등 유튜브 기능을 애플리케이션에서 사용할 수 있도록 제공되는 API이다.

4. 사용자 인증 정보 만들기
YouTube Data API v3 사용 설정이 끝나면 왼쪽 메뉴에서 API 및 서비스 → 사용자 인증 정보로 이동한다.
상단의 사용자 인증 정보 만들기 버튼을 누른 뒤 API 키를 선택한다.
그러면 자동으로 API 키가 생성된다.

[사용 라이브러리]
streamlit, pandas, requests, beautifulsoup4, selenium, matplotlib, wordcloud, konlpy, JPype1
