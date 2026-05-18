# 박스오피스 Flask 서버 (server_boxoffice.py)

KOBIS 영화진흥위원회 오픈 API에서 주간 박스오피스 Top 6를 가져와
`movie_metadata.json`의 포스터·평점과 결합해 프론트엔드에 반환하는 가벼운 Flask 서버입니다.

크롤링용 `server.py`와는 별개로 동작합니다.

## 1. 로컬 실행

```bash
# (1) 의존성 설치
pip install -r requirements.txt

# (2) 환경변수 설정
cp .env.example .env
# .env 파일을 열어 KOBIS_API_KEY를 본인 키로 교체

# (3) 서버 실행
python server_boxoffice.py
```

브라우저에서 `http://localhost:5001/api/boxoffice` 접속 시 JSON 응답이 보이면 성공.
`http://localhost:5001/api/health`로 헬스 체크 가능.

## 2. movieCd 매핑 추가 (시연 전 1회 필수)

KOBIS 박스오피스는 매주 바뀌므로 시연 전 한 번 실행해서 각 영화의 movieCd를 확인해야 합니다.

1. 서버 실행 후 `/api/boxoffice` 호출
2. 응답의 각 영화에 있는 `movie_cd` 값을 확인
3. `movie_metadata.json`에 해당 movieCd 키로 항목 추가:
   ```json
   "<실제movieCd>": {
     "rating": "8.5",
     "image": "/images/해당영화포스터.webp"
   }
   ```
4. 포스터 이미지는 React 프로젝트의 `public/images/` 폴더에 미리 넣어둘 것
5. 평점은 KOBIS에서 제공하지 않으므로 네이버 영화 / IMDB 등을 참고해 수동 입력

매핑 누락된 영화는 placeholder 이미지와 'N/A' 평점으로 표시됩니다.

## 3. Render 배포

1. 이 폴더를 GitHub 저장소에 push (`.env`는 .gitignore에 의해 자동 제외)
2. Render 대시보드 → New → Web Service → 해당 저장소 연결
3. 설정값:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn server_boxoffice:app`
   - **Environment Variables**: `KOBIS_API_KEY` 추가
4. 배포 완료 후 발급되는 URL (예: `https://multiflex-boxoffice.onrender.com`)을
   Vercel 프론트엔드 환경변수 `REACT_APP_BOXOFFICE_URL`에 등록

## 4. 캐싱 동작

같은 날짜에 두 번째 요청부터는 KOBIS를 다시 부르지 않고 메모리 캐시에서 응답합니다.
응답 JSON의 `cached: true` 필드로 확인 가능. 서버 재시작 시 캐시는 초기화됩니다.

## 5. 파일 구성

| 파일 | 역할 |
|---|---|
| `server_boxoffice.py` | Flask 서버 본체 |
| `movie_metadata.json` | KOBIS movieCd → 포스터/평점 매핑 (수동 작성) |
| `requirements.txt` | Python 의존성 |
| `.env.example` | 환경변수 예시 (실제 .env는 별도 작성) |
| `.gitignore` | .env와 캐시 파일 제외 |A